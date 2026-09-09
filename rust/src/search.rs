//! Determinized MCTS.
//!
//! For each determinization: sample a consistent full deal, run a perfect-information UCT
//! search on it, then aggregate per-card statistics across determinizations. This is the
//! half of the search that a rollout-only port would have left in Python — and profiling
//! showed that would have capped the whole exercise at ~2.4x.
//!
//! Tuning defaults follow `PLAN.md` §3.1: ~1000 determinizations x 800 iterations, and an
//! exploration constant around 1.5 (much higher than perfect-information MCTS wants).

use rayon::prelude::*;

use crate::cards::*;
use crate::determinize::determinize;
use crate::legal::legal_moves;
use crate::rng::Rng;
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
    /// Suit bitmask of proven voids, per seat.
    pub voids: [u8; NUM_SEATS],
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
    k: Kernel,
    exploration: f64,
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
    fn new(k: Kernel, exploration: f64, untried: u64) -> Self {
        Tree {
            nodes: vec![Node {
                visits: 0,
                total: 0.0,
                children: Vec::new(),
                untried,
                expanded: false,
            }],
            k,
            exploration,
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

    fn uct_child(&self, node_idx: usize) -> usize {
        let node = &self.nodes[node_idx];
        let log_v = ((node.visits + 1) as f64).ln();
        let mut best = usize::MAX;
        let mut best_score = f64::NEG_INFINITY;
        for &(_, ci) in &node.children {
            let c = &self.nodes[ci];
            let score = if c.visits == 0 {
                f64::INFINITY
            } else {
                c.total / c.visits as f64 + self.exploration * (log_v / c.visits as f64).sqrt()
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

            let child = self.uct_child(node_idx);
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

        // --- rollout: finish any partial trick, then hand off to the kernel ---
        while !w.trick.is_empty() {
            let legal = self.legal_at(w);
            let card = pick_random(legal, rng);
            self.advance(w, card);
        }
        let (a, b) = play_out(&mut w.hands, w.to_play, &self.k, rng);
        w.pts[0] += a;
        w.pts[1] += b;

        // Score from the searching team's point of view, normalised to [0, 1].
        let total = (w.pts[0] + w.pts[1]).max(1) as f64;
        let result = w.pts[root_team] as f64 / total;
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

    let run_one = |d: usize| -> Vec<(usize, u64, f64)> {
        let mut rng = Rng::split(seed, d as u64);
        let mut hands = [0u64; NUM_SEATS];
        hands[pos.seat] = pos.hand;

        // Rejection-sample a world consistent with the proven voids.
        let mut ok = false;
        for _ in 0..64 {
            let mut dealt = [0u64; NUM_SEATS];
            if determinize(pos.unseen, &counts, &pos.voids, &mut dealt, &mut rng) {
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
            return Vec::new();
        }

        let mut tree = Tree::new(*k, exploration, root_legal);
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

        tree.nodes[0]
            .children
            .iter()
            .map(|&(card, ci)| {
                let n = &tree.nodes[ci];
                (card, n.visits as u64, n.total)
            })
            .collect()
    };

    // Determinizations are independent, which is what makes this scale linearly. Each gets
    // its own seed stream, so results do not depend on how the work was scheduled.
    let per_det: Vec<Vec<(usize, u64, f64)>> = if threads > 1 {
        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(threads)
            .build()
            .expect("thread pool");
        pool.install(|| (0..determinizations).into_par_iter().map(run_one).collect())
    } else {
        (0..determinizations).map(run_one).collect()
    };

    let mut visits = [0u64; NUM_CARDS];
    let mut totals = [0f64; NUM_CARDS];
    let mut selecting = [0u32; NUM_CARDS];
    for det in &per_det {
        let mut best_card = usize::MAX;
        let mut best_visits = 0u64;
        for &(card, v, t) in det {
            visits[card] += v;
            totals[card] += t;
            if v > best_visits {
                best_visits = v;
                best_card = card;
            }
        }
        if best_card != usize::MAX {
            selecting[best_card] += 1;
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
    // Aggregate across determinizations by selection count, then visits — PLAN.md §3.2.
    out.sort_by(|a, b| {
        b.determinizations_selecting
            .cmp(&a.determinizations_selecting)
            .then(b.visits.cmp(&a.visits))
    });
    out
}
