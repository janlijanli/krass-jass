//! The rollout kernel and trick resolution.
//!
//! This is the code the whole Rust port exists for. `docs/plan-review.md` §1 measured the
//! Python version at ~72k rollouts/sec; the search on top of it ran at 35k iterations/sec,
//! with 73% of time in here. Note that porting *only* this would have been worth ~2.4x —
//! the tree in `search.rs` had to come with it.

use crate::cards::*;
use crate::legal::legal_moves;
use crate::tables::{CARD_VALUES, STRENGTH};
use crate::rng::Rng;

/// Everything the kernel needs, flattened once outside the loop.
#[derive(Clone, Copy)]
pub struct Kernel {
    pub contract: usize,
    pub trump: i32,
    pub strict_undertrump: bool,
    pub puur_exempt: bool,
    pub last_trick_bonus: i32,
    pub match_bonus: i32,
}

impl Kernel {
    pub fn new(
        contract: usize,
        strict_undertrump: bool,
        puur_exempt: bool,
        last_trick_bonus: i32,
        match_bonus: i32,
    ) -> Self {
        Kernel {
            contract,
            trump: if contract < 4 { contract as i32 } else { -1 },
            strict_undertrump,
            puur_exempt,
            last_trick_bonus,
            match_bonus,
        }
    }
}

/// Uniform pick over the set bits of `mask`. Returns the card index.
#[inline(always)]
pub fn pick_random(mask: u64, rng: &mut Rng) -> usize {
    let n = mask.count_ones();
    let mut m = mask;
    let skip = rng.below(n);
    for _ in 0..skip {
        m &= m - 1;
    }
    m.trailing_zeros() as usize
}

/// Play out at random until the hands are empty. Returns team points.
///
/// Precondition, as in the Python kernel: the position is at a trick boundary, so every
/// hand holds the same number of cards. The match bonus is only awarded when the playout
/// covered a whole round — from a partial position the kernel cannot know who took the
/// earlier tricks.
pub fn play_out(hands: &mut [u64; NUM_SEATS], mut leader: usize, k: &Kernel, rng: &mut Rng) -> (i32, i32) {
    let values = &CARD_VALUES[k.contract];
    let strength_by_led = &STRENGTH[k.contract];

    let n_tricks = hands[leader].count_ones() as usize;
    if n_tricks == 0 {
        return (0, 0);
    }

    let mut pts = [0i32; 2];
    let mut tricks = [0usize; 2];

    for _ in 0..n_tricks {
        let mut led: i32 = -1;
        let mut best_trump: i32 = -1;
        let mut strength: &[i32; NUM_CARDS] = &strength_by_led[0];
        let mut trick_pts = 0i32;
        let mut best_seat = leader;
        let mut best_str = -1i32;

        for i in 0..NUM_SEATS {
            let seat = (leader + i) & 3;
            let hand = hands[seat];
            let legal = legal_moves(
                hand,
                k.trump,
                led,
                best_trump,
                k.strict_undertrump,
                k.puur_exempt,
            );
            let c = pick_random(legal, rng);

            hands[seat] = hand ^ (1u64 << c);
            trick_pts += values[c];

            if i == 0 {
                led = card_suit(c) as i32;
                strength = &strength_by_led[led as usize];
                best_str = strength[c];
            } else {
                let s = strength[c];
                if s > best_str {
                    best_str = s;
                    best_seat = seat;
                }
            }
            if k.trump >= 0 && card_suit(c) as i32 == k.trump {
                let ts = strength[c] - 100;
                if ts > best_trump {
                    best_trump = ts;
                }
            }
        }

        let team = best_seat & 1;
        pts[team] += trick_pts;
        tricks[team] += 1;
        leader = best_seat;
    }

    pts[leader & 1] += k.last_trick_bonus;
    if k.match_bonus != 0 && n_tricks == TRICKS_PER_ROUND {
        for t in 0..2 {
            if tricks[t] == TRICKS_PER_ROUND {
                pts[t] += k.match_bonus;
            }
        }
    }
    (pts[0], pts[1])
}
