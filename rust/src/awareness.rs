//! What a player at the table can work out from the cards face up.
//!
//! Mirror of `krass_jass/awareness.py`; the Python module carries the reasoning. Everything
//! here is public information — the arguments are the played cards plus the asking seat's
//! own hand — so it feeds the display without telling a player anything they could not have
//! counted themselves.

use crate::cards::{card_suit, NUM_SEATS, PUUR_MASK, SUIT_MASK};
use crate::config::Rules;
use crate::tables::{CARD_VALUES, STRENGTH};
use crate::voids::infer_forbidden;

/// A seat's trump holding, as far as the cards face up prove it.
pub const UNKNOWN: u8 = 0;
/// Provably holds no trump except possibly the Puur.
pub const ONLY_PUUR: u8 = 1;
/// Provably holds no trump at all.
pub const NO_TRUMP: u8 = 2;

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

/// How much trump is still out, and who is proven not to hold any.
pub struct TrumpRead {
    /// Trumps in the other three hands — every trump is face up, in `hand`, or theirs.
    pub out: Option<u32>,
    pub voids: [u8; NUM_SEATS],
}

pub fn trump_read(
    tricks: &[(usize, Vec<usize>)],
    current_trick: &[usize],
    current_leader: usize,
    seat: usize,
    hand: u64,
    trump: i32,
    rules: &Rules,
) -> TrumpRead {
    if trump < 0 {
        return TrumpRead { out: None, voids: [UNKNOWN; NUM_SEATS] };
    }
    let trump_u = trump as usize;

    let mut seen = hand;
    for (_, cards) in tricks {
        for &card in cards {
            seen |= 1u64 << card;
        }
    }
    for &card in current_trick {
        seen |= 1u64 << card;
    }

    let unseen = SUIT_MASK[trump_u] & !seen;
    let forbidden = infer_forbidden(tricks, current_trick, current_leader, trump, rules);

    let mut voids = [UNKNOWN; NUM_SEATS];
    for other in 0..NUM_SEATS {
        if other == seat {
            continue;
        }
        // What is left after removing every trump that is face up, in my own hand, or ruled
        // out for them by the play. Nothing about *their* hand is read here.
        let possible = unseen & !forbidden[other];
        voids[other] = if possible == 0 {
            NO_TRUMP
        } else if possible & !PUUR_MASK[trump_u] == 0 {
            // The Puur is the one trump a player may hold back on a trump lead, so it is the
            // one card the discard did not rule out. Once it has been played this branch is
            // unreachable: the card is in `seen`, and the read hardens to NO_TRUMP.
            ONLY_PUUR
        } else {
            UNKNOWN
        };
    }

    TrumpRead { out: Some(unseen.count_ones()), voids }
}
