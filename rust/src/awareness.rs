//! What a player at the table can work out from the cards face up.
//!
//! Mirror of `krass_jass/awareness.py`; the Python module carries the reasoning. Everything
//! here is public information — the arguments are the played cards plus the asking seat's
//! own hand — so it feeds the display without telling a player anything they could not have
//! counted themselves.

use crate::cards::{card_suit, NUM_SEATS};
use crate::tables::STRENGTH;

/// Seat the cards on the table currently go to, with the trick still in progress.
///
/// Strengths are banded (trump above led suit above the rest), so one maximum decides it at
/// any length — the same comparison `Round::resolve_trick` makes when the fourth card lands.
pub fn trick_taker(cards: &[usize], leader: usize, contract: usize) -> Option<usize> {
    let first = *cards.first()?;
    let strength = &STRENGTH[contract][card_suit(first)];
    let mut best = 0usize;
    for i in 1..cards.len() {
        if strength[cards[i]] > strength[cards[best]] {
            best = i;
        }
    }
    Some((leader + best) % NUM_SEATS)
}
