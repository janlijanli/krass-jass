//! Determinized MCTS.
//!
//! For each determinization: sample a consistent full deal, run a perfect-information UCT
//! search on it, then aggregate per-card statistics across determinizations. This is the
//! half of the search that a rollout-only port would have left in Python — and profiling
//! showed that would have capped the whole exercise at ~2.4x.
//!
//! Tuning defaults follow `PLAN.md` §3.1: ~1000 determinizations x 800 iterations, and an
//! exploration constant around 1.5 (much higher than perfect-information MCTS wants).

#[cfg(feature = "python")]
use rayon::prelude::*;

use crate::announce::{determinize_consistent, Announcements};
use crate::cards::*;
use crate::endgame::solve_root;
use crate::legal::legal_moves;
use crate::rng::Rng;
use crate::leafeval::{evaluate, features, N_FEATURES};
use crate::objective::{reward, Stakes};
use crate::rollout::{pick_random, play_out, Kernel};
use crate::tables::{CARD_VALUES, STRENGTH};

/// The position a search runs from, as seen by one seat.
#[derive(Clone)]
pub struct Position {
    pub seat: usize,
    pub hand: u64,
    /// Cards the searching seat cannot see — the other three hands, combined.
    pub unseen: u64,
    /// Cards played in the current trick, in play order.
    pub trick: Vec<usize>,
    /// Seat that led the current trick.
    pub trick_leader: usize,
    /// Per seat, a mask of cards that seat provably cannot hold.
    pub forbidden: [u64; NUM_SEATS],
    /// Per seat and suit, a soft prior from `reading.rs` and `bidding.py`. Zeroes are uniform.
    pub affinity: [[i8; 4]; NUM_SEATS],
    /// Per seat, a pull towards high cards (positive) or low ones — what a bid says about
    /// ranks. See `krass_jass/bidding.py`.
    pub rank_bias: [i8; NUM_SEATS],
    /// The game around this round. `target: 0` falls back to the share of the round.
    pub stakes: Stakes,
    /// Linear leaf evaluator. Empty means the random playout, which is the baseline.
    pub leaf_weights: Vec<f64>,
    /// Model opponents as opponents. False reproduces the original search, which maximised
    /// the root team's value at *every* node — see `Tree::uct_child`.
    pub adversarial: bool,
    /// What the table was told in the first trick. `Announcements::none()` is the behaviour
    /// every figure before `docs/measurements.md` §5m was measured with.
    pub announcements: Announcements,
}

impl Position {
    fn to_play(&self) -> usize {
        (self.trick_leader + self.trick.len()) & 3
    }

    fn led(&self) -> i32 {
        if self.trick.is_empty() {
            -1
        } else {
            card_suit(self.trick[0]) as i32
        }
    }

    fn best_trump(&self, k: &Kernel) -> i32 {
        if k.trump < 0 || self.trick.is_empty() {
            return -1;
        }
        let strength = &STRENGTH[k.contract][self.led() as usize];
        let mut best = -1;
        for &c in &self.trick {
            if card_suit(c) as i32 == k.trump {
                let ts = strength[c] - 100;
                if ts > best {
                    best = ts;
                }
            }
        }
        best
    }

    pub fn legal(&self, k: &Kernel) -> u64 {
        legal_moves(
            self.hand,
            k.trump,
            self.led(),
            self.best_trump(k),
            k.strict_undertrump,
            k.puur_exempt,
        )
    }
}

struct Node {
    visits: u32,
    total: f64,
    /// (card, child index). Small and linear — a HashMap would be slower at this size.
    children: Vec<(usize, usize)>,
    untried: u64,
    expanded: bool,
}

/// A perfect-information UCT search over one determinization.
struct Tree {
    nodes: Vec<Node>,
    leaf_weights: Vec<f64>,
    k: Kernel,
    exploration: f64,
    stakes: Stakes,
    /// Model the opposition as playing against you rather than with you.
    adversarial: bool,
}

/// Mutable game state carried down one descent.
struct Walk {
    hands: [u64; NUM_SEATS],
    trick: Vec<usize>,
    trick_leader: usize,
    to_play: usize,
    pts: [i32; 2],
    tricks: [usize; 2],
}

impl Tree {
    fn new(
        k: Kernel,
        exploration: f64,
        untried: u64,
        stakes: Stakes,
        adversarial: bool,
        leaf_weights: Vec<f64>,
    ) -> Self {
        Tree {
            leaf_weights,
            nodes: vec![Node {
                visits: 0,
                total: 0.0,
                children: Vec::new(),
                untried,
                expanded: false,
            }],
            k,
            exploration,
            stakes,
            adversarial,
        }
    }

    fn legal_at(&self, w: &Walk) -> u64 {
        let led = if w.trick.is_empty() {
            -1
        } else {
            card_suit(w.trick[0]) as i32
        };
        let mut best_trump = -1;
        if self.k.trump >= 0 && !w.trick.is_empty() {
            let strength = &STRENGTH[self.k.contract][led as usize];
            for &c in &w.trick {
                if card_suit(c) as i32 == self.k.trump {
                    let ts = strength[c] - 100;
                    if ts > best_trump {
                        best_trump = ts;
                    }
                }
            }
        }
        legal_moves(
            w.hands[w.to_play],
            self.k.trump,
            led,
            best_trump,
            self.k.strict_undertrump,
            self.k.puur_exempt,
        )
    }

    /// Apply a card and resolve the trick if it completes.
    fn advance(&self, w: &mut Walk, card: usize) {
        let values = &CARD_VALUES[self.k.contract];
        w.hands[w.to_play] ^= 1u64 << card;
        w.trick.push(card);
        if w.trick.len() == NUM_SEATS {
            let led = card_suit(w.trick[0]);
            let strength = &STRENGTH[self.k.contract][led];
            let mut bi = 0;
            let mut bs = strength[w.trick[0]];
            let mut pts = 0;
            for (i, &c) in w.trick.iter().enumerate() {
                pts += values[c];
                if i > 0 && strength[c] > bs {
                    bs = strength[c];
                    bi = i;
                }
            }
            let winner = (w.trick_leader + bi) & 3;
            w.pts[winner & 1] += pts;
            w.tricks[winner & 1] += 1;
            w.trick_leader = winner;
            w.to_play = winner;
            w.trick.clear();
        } else {
            w.to_play = (w.to_play + 1) & 3;
        }
    }

    /// UCT, from the point of view of whoever is about to play at this node.
    ///
    /// `total` is banked in root-team units throughout, so a seat on the other team wants
    /// `1 - mean` — the reward lives in [0, 1] and the two teams split a round between them.
    /// Without that flip the tree picks, at an opponent's turn, whichever card is best *for
    /// the root team*, and the value that comes back is what happens when the opposition
    /// cooperates. Partners keep the root team's sign: a Jass team shares a score, so a
    /// partner maximising the team value is modelling them correctly, not optimistically.
    fn uct_child(&self, node_idx: usize, to_play: usize, root_team: usize) -> usize {
        let node = &self.nodes[node_idx];
        let log_v = ((node.visits + 1) as f64).ln();
        let ours = !self.adversarial || (to_play & 1) == root_team;
        let mut best = usize::MAX;
        let mut best_score = f64::NEG_INFINITY;
        for &(_, ci) in &node.children {
            let c = &self.nodes[ci];
            let score = if c.visits == 0 {
                f64::INFINITY
            } else {
                let mean = c.total / c.visits as f64;
                let mean = if ours { mean } else { 1.0 - mean };
                mean + self.exploration * (log_v / c.visits as f64).sqrt()
            };
            if score > best_score {
                best_score = score;
                best = ci;
            }
        }
        best
    }

    fn iterate(&mut self, w: &mut Walk, rng: &mut Rng, root_team: usize) -> usize {
        let mut path = vec![0usize];
        let mut node_idx = 0usize;
        let mut root_card = usize::MAX;

        loop {
            if !self.nodes[node_idx].expanded {
                self.nodes[node_idx].untried = self.legal_at(w);
                self.nodes[node_idx].expanded = true;
            }
            let untried = self.nodes[node_idx].untried;

            if untried != 0 {
                // expand
                let card = pick_random(untried, rng);
                self.nodes[node_idx].untried &= !(1u64 << card);
                let child = self.nodes.len();
                self.nodes.push(Node {
                    visits: 0,
                    total: 0.0,
                    children: Vec::new(),
                    untried: 0,
                    expanded: false,
                });
                self.nodes[node_idx].children.push((card, child));
                if node_idx == 0 {
                    root_card = card;
                }
                self.advance(w, card);
                path.push(child);
                break;
            }

            if self.nodes[node_idx].children.is_empty() {
                break; // terminal
            }

            let child = self.uct_child(node_idx, w.to_play, root_team);
            let card = self.nodes[node_idx]
                .children
                .iter()
                .find(|&&(_, ci)| ci == child)
                .unwrap()
                .0;
            if node_idx == 0 {
                root_card = card;
            }
            self.advance(w, card);
            path.push(child);
            node_idx = child;
        }

        // --- evaluate the leaf ---
        //
        // Note there is deliberately no exact solve here. See `endgame::solve_root`: at
        // ~3ms a five-card solve is far too expensive to run per leaf, and the endgame is
        // handled by replacing the whole search instead.
        let result = if self.leaf_weights.is_empty() {
            // The baseline: finish any partial trick, then hand off to the kernel and play
            // the round out at random. One sample of a very noisy quantity.
            while !w.trick.is_empty() {
                let legal = self.legal_at(w);
                let card = pick_random(legal, rng);
                self.advance(w, card);
            }
            let (a, b) = play_out(&mut w.hands, w.to_play, &self.k, rng);
            w.pts[0] += a;
            w.pts[1] += b;
            reward(w.pts[root_team], w.pts[1 - root_team], root_team, &self.stakes)
        } else {
            // The static estimate. Fitted to the *mean* of the playout above, so this is a
            // variance-reduction experiment and not a change of target. See leafeval.rs.
            let mut feats = [0.0f64; N_FEATURES];
            features(
                &w.hands, &w.trick, w.trick_leader, w.to_play, &w.tricks, &self.k,
                root_team, &mut feats,
            );
            evaluate(&self.leaf_weights, &feats)
        };
        for &n in &path {
            self.nodes[n].visits += 1;
            self.nodes[n].total += result;
        }
        root_card
    }
}

/// Per-candidate statistics, the shape the decision trace in `PLAN.md` §6 expects.
pub struct Candidate {
    pub card: usize,
    pub visits: u64,
    pub mean_score: f64,
    pub determinizations_selecting: u32,
}

/// Run DMCTS and return one entry per legal move, best first.
pub fn dmcts(
    pos: &Position,
    k: &Kernel,
    determinizations: usize,
    iterations: usize,
    exploration: f64,
    seed: u64,
    threads: usize,
    endgame_cards: u32,
) -> Vec<Candidate> {
    let root_legal = pos.legal(k);
    let root_team = pos.seat & 1;

    // How many cards each seat still holds. The searching seat's hand is known; the others
    // are inferred from the position in the trick — seats that have already played this
    // trick hold one fewer.
    let base = pos.hand.count_ones() as usize;
    let mut counts = [0usize; NUM_SEATS];
    for s in 0..NUM_SEATS {
        if s == pos.seat {
            continue;
        }
        let played_this_trick = pos
            .trick
            .iter()
            .enumerate()
            .any(|(i, _)| (pos.trick_leader + i) & 3 == s);
        counts[s] = if played_this_trick { base - 1 } else { base };
    }

    // Once the round is small enough, the search is *replaced* by an exact solve per
    // determinization: strictly better than anything MCTS would return, and cheaper.
    let max_hand = pos.hand.count_ones();
    let endgame = endgame_cards > 0 && max_hand <= endgame_cards && max_hand > 0;

    let run_one = |d: usize| -> (Vec<(usize, u64, f64)>, usize) {
        let mut rng = Rng::split(seed, d as u64);
        let mut hands = [0u64; NUM_SEATS];
        hands[pos.seat] = pos.hand;

        // Rejection-sample a world consistent with the proven voids, and — inside that —
        // with the Weis values the table called. See `announce.rs` for why the second one
        // is a preference with a cap rather than a constraint.
        let mut ok = false;
        for _ in 0..64 {
            let mut dealt = [0u64; NUM_SEATS];
            if determinize_consistent(
                pos.unseen, &counts, &pos.forbidden, &pos.affinity, &pos.rank_bias,
                &pos.announcements, pos.seat, pos.hand, &mut dealt, &mut rng,
            ) {
                for s in 0..NUM_SEATS {
                    if s != pos.seat {
                        hands[s] = dealt[s];
                    }
                }
                ok = true;
                break;
            }
        }
        if !ok {
            return (Vec::new(), usize::MAX);
        }

        if endgame {
            let mut hands_arr = hands;
            let exact = solve_root(&mut hands_arr, &pos.trick, pos.trick_leader, k);

            // solve_root returns team-0 points; convert to the searching team's share of
            // everything still on the table.
            let values = &CARD_VALUES[k.contract];
            let mut remaining = k.last_trick_bonus;
            for &h in hands.iter() {
                let mut m = h;
                while m != 0 {
                    let low = m & m.wrapping_neg();
                    m ^= low;
                    remaining += values[low.trailing_zeros() as usize];
                }
            }
            for &c in &pos.trick {
                remaining += values[c];
            }
            let denom = if remaining > 0 { remaining as f64 } else { 1.0 };

            let mut best_card = usize::MAX;
            let mut best_score = f64::NEG_INFINITY;
            let out: Vec<(usize, u64, f64)> = exact
                .into_iter()
                .map(|(card, team0)| {
                    let mine = if root_team == 0 { team0 } else { remaining - team0 };
                    let score = mine as f64 / denom;
                    if score > best_score {
                        best_score = score;
                        best_card = card;
                    }
                    // One "visit", but it is a certainty rather than a sample.
                    (card, 1u64, score)
                })
                .collect();
            return (out, best_card);
        }

        let mut tree =
            Tree::new(*k, exploration, root_legal, pos.stakes, pos.adversarial,
                      pos.leaf_weights.clone());
        for _ in 0..iterations {
            let mut w = Walk {
                hands,
                trick: pos.trick.clone(),
                trick_leader: pos.trick_leader,
                to_play: pos.to_play(),
                pts: [0, 0],
                tricks: [0, 0],
            };
            tree.iterate(&mut w, &mut rng, root_team);
        }

        let stats: Vec<(usize, u64, f64)> = tree.nodes[0]
            .children
            .iter()
            .map(|&(card, ci)| {
                let n = &tree.nodes[ci];
                (card, n.visits as u64, n.total)
            })
            .collect();
        // A determinization "selects" its most-visited root move — the standard DMCTS
        // aggregation (PLAN.md §3.2), not the highest mean, which is noisy at low visits.
        let selected = stats
            .iter()
            .max_by_key(|&&(_, v, _)| v)
            .map(|&(c, _, _)| c)
            .unwrap_or(usize::MAX);
        (stats, selected)
    };

    // Determinizations are independent, which is what makes this scale linearly. Each gets
    // its own seed stream, so results do not depend on how the work was scheduled.
    // Parallel determinizations need rayon, which does not exist on wasm32 — and browsers
    // only get threads with SharedArrayBuffer plus COOP/COEP headers, which static hosts
    // like GitHub Pages cannot set. Single-threaded is the wasm path.
    #[cfg(feature = "python")]
    let per_det: Vec<(Vec<(usize, u64, f64)>, usize)> = if threads > 1 {
        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(threads)
            .build()
            .expect("thread pool");
        pool.install(|| (0..determinizations).into_par_iter().map(run_one).collect())
    } else {
        (0..determinizations).map(run_one).collect()
    };
    #[cfg(not(feature = "python"))]
    let per_det: Vec<(Vec<(usize, u64, f64)>, usize)> = {
        let _ = threads;
        (0..determinizations).map(run_one).collect()
    };

    let mut visits = [0u64; NUM_CARDS];
    let mut totals = [0f64; NUM_CARDS];
    let mut selecting = [0u32; NUM_CARDS];
    for (stats, selected) in &per_det {
        for &(card, v, t) in stats {
            visits[card] += v;
            totals[card] += t;
        }
        if *selected != usize::MAX {
            selecting[*selected] += 1;
        }
    }

    let mut out: Vec<Candidate> = (0..NUM_CARDS)
        .filter(|&c| root_legal & (1u64 << c) != 0)
        .map(|c| Candidate {
            card: c,
            visits: visits[c],
            mean_score: if visits[c] > 0 {
                totals[c] / visits[c] as f64
            } else {
                0.0
            },
            determinizations_selecting: selecting[c],
        })
        .collect();
    // Aggregate across determinizations by selection count, then mean score — PLAN.md §3.2.
    out.sort_by(|a, b| {
        b.determinizations_selecting
            .cmp(&a.determinizations_selecting)
            .then(
                b.mean_score
                    .partial_cmp(&a.mean_score)
                    .unwrap_or(std::cmp::Ordering::Equal),
            )
    });
    out
}
