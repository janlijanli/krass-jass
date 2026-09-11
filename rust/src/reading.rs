//! Reading the table: what a seat's discards suggest about the suits it holds.
//!
//! Mirror of `krass_jass/reading.py`; the Python module carries the reasoning. The rule that
//! matters in both: a void is a fact and removes worlds, a signal is a suggestion and may only
//! make worlds likelier. Nothing here can make a world impossible.

use crate::cards::{card_suit, NUM_SEATS};

/// How far the reading may push a suit either way. The sampler turns `n` into `2^n`, so this
/// is a factor of four and never a zero.
pub const LIMIT: i8 = 2;
const STEP: i8 = 1;

/// The other suit of the same colour: `♦0 ↔ ♥1`, `♠2 ↔ ♣3`.
pub fn sister(suit: usize) -> usize {
    suit ^ 1
}

fn fold(affinity: &mut [[i8; 4]; NUM_SEATS], leader: usize, cards: &[usize], trump: i32) {
    let Some(&first) = cards.first() else { return };
    let led = card_suit(first);
    for (i, &card) in cards.iter().enumerate() {
        if i == 0 {
            continue; // a lead is a choice, not a discard
        }
        let seat = (leader + i) % NUM_SEATS;
        let suit = card_suit(card);
        if suit == led || (trump >= 0 && suit == trump as usize) {
            continue; // followed, or trumped — neither is a discard
        }
        affinity[seat][suit] = (affinity[seat][suit] - STEP).max(-LIMIT);
        let want = sister(suit);
        affinity[seat][want] = (affinity[seat][want] + STEP).min(LIMIT);
    }
}

/// Per-seat, per-suit weighting of what the discards suggest.
///
/// Reads every seat's discards, not only the partner's: the convention is played in the open.
pub fn infer_affinity(
    tricks: &[(usize, Vec<usize>)],
    current_trick: &[usize],
    current_leader: usize,
    trump: i32,
) -> [[i8; 4]; NUM_SEATS] {
    let mut affinity = [[0i8; 4]; NUM_SEATS];
    for (leader, cards) in tricks {
        fold(&mut affinity, *leader, cards, trump);
    }
    fold(&mut affinity, current_leader, current_trick, trump);
    affinity
}
