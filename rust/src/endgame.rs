//! Exact endgame solver.
//!
//! With few enough cards left, a perfect-information alpha-beta solve is cheap and *exact*,
//! so the last tricks of every determinization stop being a random guess. `PLAN.md` §1.3
//! calls this out: bolt it on and the endgame becomes optimal for free. It is also why
//! published bot differences shrink late in the round.
//!
//! Inside DMCTS this replaces the random playout once the position is small enough. The
//! perfect-information assumption is exactly right there — a determinization *is* a
//! perfect-information world.

use crate::cards::*;
use crate::legal::legal_moves;
use crate::rollout::Kernel;
use crate::tables::{CARD_VALUES, STRENGTH, SUIT_ORDER};

/// Scratch state for one solve. Reused across nodes so the search allocates nothing.
pub struct Solver<'a> {
    k: &'a Kernel,
    trick: [usize; NUM_SEATS],
    pub nodes: u64,
}

impl<'a> Solver<'a> {
    pub fn new(k: &'a Kernel) -> Self {
        Solver {
            k,
            trick: [0; NUM_SEATS],
            nodes: 0,
        }
    }

    /// Exact points team 0 takes from here to the end of the round.
    ///
    /// `trick` is the cards already played in the current trick, in play order from
    /// `leader`. Includes the last-trick bonus; excludes the match bonus, which a partial
    /// position cannot determine (same rule as the rollout kernel).
    pub fn solve(
        &mut self,
        hands: &mut [u64; NUM_SEATS],
        trick: &[usize],
        leader: usize,
        alpha: i32,
        beta: i32,
    ) -> i32 {
        let len = trick.len();
        self.trick[..len].copy_from_slice(trick);
        let to_play = (leader + len) & 3;
        self.ab(hands, len, leader, to_play, alpha, beta)
    }

    fn ab(
        &mut self,
        hands: &mut [u64; NUM_SEATS],
        trick_len: usize,
        leader: usize,
        to_play: usize,
        mut alpha: i32,
        mut beta: i32,
    ) -> i32 {
        self.nodes += 1;

        if trick_len == 0 && hands.iter().all(|&h| h == 0) {
            return 0;
        }

        let values = &CARD_VALUES[self.k.contract];
        let led: i32 = if trick_len == 0 {
            -1
        } else {
            card_suit(self.trick[0]) as i32
        };

        let mut best_trump = -1i32;
        if self.k.trump >= 0 && trick_len > 0 {
            let strength = &STRENGTH[self.k.contract][led as usize];
            for i in 0..trick_len {
                let c = self.trick[i];
                if card_suit(c) as i32 == self.k.trump {
                    let ts = strength[c] - 100;
                    if ts > best_trump {
                        best_trump = ts;
                    }
                }
            }
        }

        let legal = legal_moves(
            hands[to_play],
            self.k.trump,
            led,
            best_trump,
            self.k.strict_undertrump,
            self.k.puur_exempt,
        );

        // Equivalence reduction. Two cards are interchangeable when they are adjacent in
        // the ranking *among the cards still out* AND carry the same point value; playing
        // either leads to the same position, differing only in which of two
        // indistinguishable cards sits in the trick.
        //
        // The value condition is the Jass-specific part and it is not optional. In a
        // trick-count game like Bridge, rank adjacency alone implies equivalence — here it
        // does not, because the 10 and the 9 are adjacent and worth 10 and 0. Dropping the
        // value check makes the solver fast and wrong.
        let remaining_all = hands[0] | hands[1] | hands[2] | hands[3];
        let mut candidates = legal;
        {
            let order = &SUIT_ORDER[self.k.contract];
            let mut suit = 0;
            while suit < NUM_SUITS {
                if legal & SUIT_MASK[suit] != 0 {
                    let mut prev_value = i32::MIN;
                    let mut prev_was_candidate = false;
                    for &c in order[suit].iter() {
                        let bit = 1u64 << c;
                        if remaining_all & bit == 0 {
                            continue; // already played — does not break adjacency
                        }
                        if legal & bit != 0 {
                            if prev_was_candidate && values[c] == prev_value {
                                candidates &= !bit;
                            }
                            prev_was_candidate = true;
                            prev_value = values[c];
                        } else {
                            prev_was_candidate = false;
                            prev_value = i32::MIN;
                        }
                    }
                }
                suit += 1;
            }
        }

        // Team 0 maximises the team-0 total; team 1 minimises it.
        let maximizing = to_play & 1 == 0;
        let mut best = if maximizing { i32::MIN } else { i32::MAX };

        let mut remaining = candidates;
        while remaining != 0 {
            let low = remaining & remaining.wrapping_neg();
            remaining ^= low;
            let card = low.trailing_zeros() as usize;

            hands[to_play] ^= low;
            self.trick[trick_len] = card;

            let value = if trick_len + 1 == NUM_SEATS {
                // trick complete — score it and continue from the winner
                let led_s = card_suit(self.trick[0]);
                let strength = &STRENGTH[self.k.contract][led_s];
                let mut bi = 0usize;
                let mut bs = strength[self.trick[0]];
                let mut pts = 0i32;
                for i in 0..NUM_SEATS {
                    let c = self.trick[i];
                    pts += values[c];
                    if i > 0 && strength[c] > bs {
                        bs = strength[c];
                        bi = i;
                    }
                }
                let winner = (leader + bi) & 3;
                let done = hands.iter().all(|&h| h == 0);
                if done {
                    pts += self.k.last_trick_bonus;
                }
                let gained = if winner & 1 == 0 { pts } else { 0 };
                let saved = self.trick;
                let sub = if done {
                    0
                } else {
                    self.ab(hands, 0, winner, winner, alpha - gained, beta - gained)
                };
                self.trick = saved;
                gained + sub
            } else {
                let saved = self.trick;
                let v = self.ab(hands, trick_len + 1, leader, (to_play + 1) & 3, alpha, beta);
                self.trick = saved;
                v
            };

            hands[to_play] ^= low;

            if maximizing {
                if value > best {
                    best = value;
                }
                if best > alpha {
                    alpha = best;
                }
            } else {
                if value < best {
                    best = value;
                }
                if best < beta {
                    beta = best;
                }
            }
            if alpha >= beta {
                break; // cutoff
            }
        }

        best
    }
}

/// Exact value of every legal move at the root, as `(card, team_0_points)`.
///
/// This is how the solver is actually used: once the round reaches the endgame the search
/// is *replaced*, not decorated. Solving at every MCTS leaf was the obvious design and it
/// is the wrong one — a five-card solve costs ~3ms, so at 800k leaf evaluations it would
/// cost forty minutes a move. One solve per determinization costs milliseconds and is
/// exact, which is strictly better than anything the search would have produced.
pub fn solve_root(
    hands: &mut [u64; NUM_SEATS],
    trick: &[usize],
    leader: usize,
    k: &Kernel,
) -> Vec<(usize, i32)> {
    let len = trick.len();
    let to_play = (leader + len) & 3;

    let led: i32 = if len == 0 {
        -1
    } else {
        card_suit(trick[0]) as i32
    };
    let mut best_trump = -1i32;
    if k.trump >= 0 && len > 0 {
        let strength = &STRENGTH[k.contract][led as usize];
        for &c in trick.iter() {
            if card_suit(c) as i32 == k.trump {
                let ts = strength[c] - 100;
                if ts > best_trump {
                    best_trump = ts;
                }
            }
        }
    }
    let legal = legal_moves(
        hands[to_play],
        k.trump,
        led,
        best_trump,
        k.strict_undertrump,
        k.puur_exempt,
    );

    let values = &CARD_VALUES[k.contract];
    let mut out = Vec::new();
    let mut work = trick.to_vec();
    let mut m = legal;
    while m != 0 {
        let low = m & m.wrapping_neg();
        m ^= low;
        let card = low.trailing_zeros() as usize;

        hands[to_play] ^= low;
        work.push(card);

        let value = if work.len() == NUM_SEATS {
            let led_s = card_suit(work[0]);
            let strength = &STRENGTH[k.contract][led_s];
            let mut bi = 0usize;
            let mut bs = strength[work[0]];
            let mut pts = 0i32;
            for (i, &c) in work.iter().enumerate() {
                pts += values[c];
                if i > 0 && strength[c] > bs {
                    bs = strength[c];
                    bi = i;
                }
            }
            let winner = (leader + bi) & 3;
            let done = hands.iter().all(|&h| h == 0);
            if done {
                pts += k.last_trick_bonus;
            }
            let gained = if winner & 1 == 0 { pts } else { 0 };
            let sub = if done {
                0
            } else {
                let mut s = Solver::new(k);
                s.solve(hands, &[], winner, i32::MIN / 2, i32::MAX / 2)
            };
            gained + sub
        } else {
            let mut s = Solver::new(k);
            s.solve(hands, &work, leader, i32::MIN / 2, i32::MAX / 2)
        };

        work.pop();
        hands[to_play] ^= low;
        out.push((card, value));
    }
    out
}

/// Convenience wrapper with open bounds.
pub fn solve_exact(
    hands: &mut [u64; NUM_SEATS],
    trick: &[usize],
    leader: usize,
    k: &Kernel,
) -> (i32, u64) {
    let mut s = Solver::new(k);
    let v = s.solve(hands, trick, leader, i32::MIN / 2, i32::MAX / 2);
    (v, s.nodes)
}
