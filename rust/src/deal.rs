//! The shared deal.
//!
//! A game seed must produce the same deal in every implementation, or "any game replays
//! bit-for-bit" is only true within one language. CPython's Mersenne Twister seeded from a
//! string cannot be reproduced in Rust, so the algorithm itself is specified here and
//! mirrored exactly in `krass_jass/deal.py`:
//!
//!   1. stream = SplitMix64(seed, round)
//!   2. Fisher-Yates over 36 cards, descending, index = Lemire multiply-shift
//!   3. cards 0..9 to seat 0, 9..18 to seat 1, and so on
//!
//! `tests/test_game_port.py` asserts the two produce identical hands. Change one, change
//! both, or replay quietly stops meaning anything.

use crate::cards::NUM_SEATS;
use crate::rng::Rng;

pub fn deal(seed: u64, round: u32) -> [u64; NUM_SEATS] {
    let mut rng = Rng::split(seed, round as u64);
    let mut deck: [u8; 36] = core::array::from_fn(|i| i as u8);
    for i in (1..36).rev() {
        let j = rng.below(i as u32 + 1) as usize;
        deck.swap(i, j);
    }
    let mut hands = [0u64; NUM_SEATS];
    for (i, &card) in deck.iter().enumerate() {
        hands[i / 9] |= 1u64 << card;
    }
    hands
}
