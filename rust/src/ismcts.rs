//! Information Set MCTS — one tree, many worlds.
//!
//! `search.rs` builds a fresh tree for each imagined deal, solves it as a perfect-information
//! game, and votes. That is PIMC, and its ceiling is **strategy fusion**: the searching player
//! effectively decides a different card for every world it imagines, then holds an election.
//! A real player cannot do that. They must pick one card that serves every world they cannot
//! tell apart.
//!
//! ISMCTS encodes that constraint in the data structure. There is **one** tree, shared across
//! every determinization. A node is reached by a sequence of played cards — which is public in
//! a trick-taking game, so a node *is* an information set — and it holds one set of statistics
//! and therefore one policy, whatever world the current iteration sampled.
//!
//! `docs/measurements.md` §5g argued this should come before a learned value rather than
//! after: the value cannot be swapped into a voting search, so the aggregation has to change
//! first.
//!
//! # The subtlety that makes it correct
//!
//! Different worlds make different moves legal. A card only playable when the sampled hand
//! contains it will be tried rarely, and comparing its visit count against the parent's total
//! visits would punish it for worlds in which it was never an option. So each child counts how
//! often it was **available**, and UCT divides by that instead — the "subset-armed bandit"
//! correction, and the one thing that separates a working ISMCTS from a broken one.
//!
//! The endgame solver is deliberately not wired in here; `dmcts` replaces the whole search
//! with an exact solve when few enough cards remain, and the comparison between the two
//! algorithms is cleaner with it off on both sides.

use crate::cards::{card_suit, NUM_SEATS};
use crate::determinize::determinize;
use crate::legal::legal_moves;
use crate::objective::reward;
use crate::rng::Rng;
use crate::rollout::{pick_random, play_out, Kernel};
use crate::search::{Candidate, Position};
use crate::tables::{CARD_VALUES, STRENGTH};

struct Node {
    visits: u32,
    /// How many iterations reached the parent with this card legal. UCT's denominator.
    available: u32,
    total: f64,
    children: Vec<(usize, usize)>,
}

struct Walk {
    hands: [u64; NUM_SEATS],
    trick: Vec<usize>,
    trick_leader: usize,
    to_play: usize,
    pts: [i32; 2],
    tricks: [usize; 2],
}

fn led(trick: &[usize]) -> i32 {
    trick.first().map_or(-1, |&c| card_suit(c) as i32)
}

fn best_trump(trick: &[usize], k: &Kernel) -> i32 {
    if k.trump < 0 || trick.is_empty() {
        return -1;
    }
    let strength = &STRENGTH[k.contract][led(trick) as usize];
    let mut best = -1;
    for &c in trick {
        if card_suit(c) as i32 == k.trump {
            best = best.max(strength[c] - 100);
        }
    }
    best
}

fn legal_at(w: &Walk, k: &Kernel) -> u64 {
    legal_moves(
        w.hands[w.to_play],
        k.trump,
        led(&w.trick),
        best_trump(&w.trick, k),
        k.strict_undertrump,
        k.puur_exempt,
    )
}

fn advance(w: &mut Walk, card: usize, k: &Kernel) {
    let values = &CARD_VALUES[k.contract];
    w.hands[w.to_play] ^= 1u64 << card;
    w.trick.push(card);
    if w.trick.len() == NUM_SEATS {
        let strength = &STRENGTH[k.contract][card_suit(w.trick[0])];
        let mut best = 0;
        let mut pts = 0;
        for (i, &c) in w.trick.iter().enumerate() {
            pts += values[c];
            if strength[c] > strength[w.trick[best]] {
                best = i;
            }
        }
        let winner = (w.trick_leader + best) & 3;
        w.pts[winner & 1] += pts;
        w.tricks[winner & 1] += 1;
        w.trick_leader = winner;
        w.to_play = winner;
        w.trick.clear();
    } else {
        w.to_play = (w.to_play + 1) & 3;
    }
}

/// Run ISMCTS and return one entry per legal move, best first.
///
/// `determinizations_selecting` is filled with the visit count so the tuple keeps the shape
/// `dmcts` returns — there are no per-world votes here, which is the point.
/// `resample_every` iterations share one imagined world before a new one is drawn.
///
/// One world per iteration is textbook ISMCTS and it is what makes the search expensive:
/// drawing a world costs far more than an iteration does, so 2,400 iterations means 2,400
/// deals where the determinized search needs 40. Natively that is a 2x tax; under wasm, where
/// the 64-bit bit arithmetic in `determinize` is much dearer, it was 40x — 80 ms a move.
///
/// Sharing a world across a few iterations trades world diversity for iterations. It is still
/// far more diverse than a tree-per-world vote, and the tree is still shared, so the property
/// that matters — one policy per information set — is untouched.
pub fn ismcts(
    pos: &Position,
    k: &Kernel,
    iterations: usize,
    exploration: f64,
    seed: u64,
    resample_every: usize,
) -> Vec<Candidate> {
    let root_legal = pos.legal(k);
    let root_team = pos.seat & 1;
    if root_legal == 0 {
        return Vec::new();
    }

    let base = pos.hand.count_ones() as usize;
    let mut counts = [0usize; NUM_SEATS];
    for s in 0..NUM_SEATS {
        if s == pos.seat {
            continue;
        }
        let played = pos
            .trick
            .iter()
            .enumerate()
            .any(|(i, _)| (pos.trick_leader + i) & 3 == s);
        counts[s] = if played { base - 1 } else { base };
    }

    let mut rng = Rng::new(seed | 1);
    let mut nodes: Vec<Node> = vec![Node {
        visits: 0,
        available: 0,
        total: 0.0,
        children: Vec::new(),
    }];

    let every = resample_every.max(1);
    let mut dealt = [0u64; NUM_SEATS];
    let mut have_world = false;

    for iter in 0..iterations {
        // A fresh world every `every` iterations, and always the *same* tree. The shared tree
        // is the difference from a determinized search; the resampling rate is only a cost.
        if iter % every == 0 || !have_world {
            if !determinize(
                pos.unseen, &counts, &pos.forbidden, &pos.affinity, &pos.rank_bias,
                &mut dealt, &mut rng,
            ) {
                continue;
            }
            dealt[pos.seat] = pos.hand;
            have_world = true;
        }

        let mut w = Walk {
            hands: dealt,
            trick: pos.trick.clone(),
            trick_leader: pos.trick_leader,
            to_play: pos.seat,
            pts: [0, 0],
            tricks: [0, 0],
        };

        let mut path = vec![0usize];
        let mut node = 0usize;
        let mut root_card = usize::MAX;

        loop {
            let legal = legal_at(&w, k);
            if legal == 0 {
                break;
            }

            // Everything legal in *this* world was available to be chosen, whether or not it
            // has been tried before. Counting availability rather than parent visits is what
            // keeps a card that is rarely dealt from looking unpopular.
            let mut untried = legal;
            // Collected first, because the loop below mutates the children it just read and
            // the borrow checker is right to object to doing both at once — but on the stack.
            // A `Vec` here is allocated at every node of every descent, which is ~20,000
            // allocations per move: barely visible natively and brutal under wasm's allocator,
            // where it cost 77 ms a move against a native 3.6 ms.
            //
            // A node has at most one child per distinct card, so 36 is the hard bound.
            let mut present = [(0usize, 0usize); 36];
            let mut n_present = 0usize;
            for &(card, child) in &nodes[node].children {
                if legal & (1u64 << card) != 0 {
                    present[n_present] = (card, child);
                    n_present += 1;
                }
            }
            for &(card, child) in &present[..n_present] {
                nodes[child].available += 1;
                untried &= !(1u64 << card);
            }

            let card = if untried != 0 {
                let card = pick_random(untried, &mut rng);
                let child = nodes.len();
                nodes.push(Node { visits: 0, available: 1, total: 0.0, children: Vec::new() });
                nodes[node].children.push((card, child));
                path.push(child);
                node = child;
                if path.len() == 2 {
                    root_card = card;
                }
                advance(&mut w, card, k);
                break; // expanded: stop descending and evaluate
            } else {
                let ours = (w.to_play & 1) == root_team;
                let mut best = usize::MAX;
                let mut best_card = usize::MAX;
                let mut best_score = f64::NEG_INFINITY;
                for &(card, child) in &present[..n_present] {
                    let c = &nodes[child];
                    let mean = c.total / c.visits.max(1) as f64;
                    let mean = if ours { mean } else { 1.0 - mean };
                    let score = mean
                        + exploration
                            * ((c.available.max(1) as f64).ln() / c.visits.max(1) as f64).sqrt();
                    if score > best_score {
                        best_score = score;
                        best = child;
                        best_card = card;
                    }
                }
                if best == usize::MAX {
                    break;
                }
                path.push(best);
                node = best;
                if path.len() == 2 {
                    root_card = best_card;
                }
                best_card
            };
            advance(&mut w, card, k);
        }

        // Finish the round at random and score it, exactly as the determinized search does.
        while !w.trick.is_empty() {
            let legal = legal_at(&w, k);
            if legal == 0 {
                break;
            }
            let card = pick_random(legal, &mut rng);
            advance(&mut w, card, k);
        }
        let (a, b) = play_out(&mut w.hands, w.to_play, k, &mut rng);
        w.pts[0] += a;
        w.pts[1] += b;
        let result = reward(w.pts[root_team], w.pts[1 - root_team], root_team, &pos.stakes);

        for &n in &path {
            nodes[n].visits += 1;
            nodes[n].total += result;
        }
        let _ = root_card;
    }

    let mut out: Vec<Candidate> = nodes[0]
        .children
        .iter()
        .map(|&(card, child)| {
            let c = &nodes[child];
            Candidate {
                card,
                visits: c.visits as u64,
                mean_score: if c.visits > 0 { c.total / c.visits as f64 } else { 0.0 },
                determinizations_selecting: c.visits,
            }
        })
        .collect();
    // Most visited, then value — the standard robust choice, and there is no vote to take.
    out.sort_by(|a, b| {
        b.visits
            .cmp(&a.visits)
            .then(b.mean_score.partial_cmp(&a.mean_score).unwrap_or(std::cmp::Ordering::Equal))
    });
    out
}
