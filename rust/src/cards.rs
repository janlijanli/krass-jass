//! Card encoding. Identical to `krass_jass/cards.py`: index = suit * 9 + rank, a hand is a
//! 36-bit mask in a u64, and ranks descend in plain order (A = 0 … 6 = 8) so plain-order
//! comparison is a bare integer comparison.
//!
//! The rank constants are kept complete even where unused — they are the encoding contract
//! shared with `krass_jass/cards.py`.
#![allow(dead_code)]

pub const NUM_SUITS: usize = 4;
pub const NUM_RANKS: usize = 9;
pub const NUM_CARDS: usize = NUM_SUITS * NUM_RANKS;
pub const NUM_SEATS: usize = 4;
pub const TRICKS_PER_ROUND: usize = 9;
pub const FULL_DECK: u64 = (1u64 << NUM_CARDS) - 1;

pub const RANK_A: usize = 0;
pub const RANK_K: usize = 1;
pub const RANK_Q: usize = 2;
pub const RANK_J: usize = 3;
pub const RANK_T: usize = 4;
pub const RANK_9: usize = 5;
pub const RANK_8: usize = 6;
pub const RANK_7: usize = 7;
pub const RANK_6: usize = 8;

const fn build_suit_mask() -> [u64; NUM_SUITS] {
    let mut out = [0u64; NUM_SUITS];
    let mut s = 0;
    while s < NUM_SUITS {
        out[s] = ((1u64 << NUM_RANKS) - 1) << (NUM_RANKS * s);
        s += 1;
    }
    out
}

pub const SUIT_MASK: [u64; NUM_SUITS] = build_suit_mask();

const fn build_puur() -> [u64; NUM_SUITS] {
    let mut out = [0u64; NUM_SUITS];
    let mut s = 0;
    while s < NUM_SUITS {
        out[s] = 1u64 << (s * NUM_RANKS + RANK_J);
        s += 1;
    }
    out
}

pub const PUUR_MASK: [u64; NUM_SUITS] = build_puur();

#[inline(always)]
pub fn card_suit(c: usize) -> usize {
    c / NUM_RANKS
}

#[inline(always)]
pub fn card_rank(c: usize) -> usize {
    c % NUM_RANKS
}
