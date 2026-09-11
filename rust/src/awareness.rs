//! What a player at the table can work out from the cards face up.
//!
//! Mirror of `krass_jass/awareness.py`; the Python module carries the reasoning. Everything
//! here is public information — the arguments are the played cards plus the asking seat's
//! own hand — so it feeds the display without telling a player anything they could not have
//! counted themselves.

use crate::cards::{card_suit, NUM_SEATS, SUIT_MASK};
use crate::tables::{CARD_VALUES, STRENGTH};

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

/// Card points lying on the table.
pub fn trick_points(cards: &[usize], contract: usize) -> i32 {
    let values = &CARD_VALUES[contract];
    cards.iter().map(|&c| values[c]).sum()
}

/// Trumps in the other three hands.
///
/// Every trump is either face up, in `hand`, or in somebody else's, so subtracting the first
/// two is exact — not an estimate, and not a read on anybody's cards.
///
/// Which seat is *out* of trump is deliberately not here; see the Python module's note.
pub fn trumps_out(
    tricks: &[(usize, Vec<usize>)],
    current_trick: &[usize],
    hand: u64,
    trump: i32,
) -> Option<u32> {
    if trump < 0 {
        return None;
    }
    let mut seen = hand;
    for (_, cards) in tricks {
        for &card in cards {
            seen |= 1u64 << card;
        }
    }
    for &card in current_trick {
        seen |= 1u64 << card;
    }
    Some((SUIT_MASK[trump as usize] & !seen).count_ones())
}
