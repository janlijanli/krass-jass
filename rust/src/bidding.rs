//! What the bidding said about the hands behind it.
//!
//! Mirror of `krass_jass/bidding.py`; the Python module carries the reasoning and the numbers.
//! In short: Obenabe means aces, Undenufe means the opposite, a shove means neither, and
//! choosing a suit means length in it — all of it forced, so the signal is always present.

use crate::cards::NUM_SEATS;
use crate::tables::{OBENABE, UNDENUFE};

pub const LIMIT: i8 = 2;
const TRUMP_SUIT_PULL: i8 = 2;
const OBENABE_PULL: i8 = 2;
const UNDENUFE_PULL: i8 = -2;
const SHOVE_PULL: i8 = -1;

/// `(suit affinity, rank bias)` per seat. Positive rank bias means "likelier to hold tops".
pub fn infer_from_bid(
    forehand: usize,
    declarer: usize,
    contract: usize,
    seat: usize,
) -> ([[i8; 4]; NUM_SEATS], [i8; NUM_SEATS]) {
    let mut suits = [[0i8; 4]; NUM_SEATS];
    let mut ranks = [0i8; NUM_SEATS];

    // Forehand shoved: nothing worth calling, and the partner then chose the least bad thing
    // rather than something they liked.
    if declarer != forehand && forehand != seat {
        ranks[forehand] = (ranks[forehand] + SHOVE_PULL).max(-LIMIT);
    }

    if declarer == seat {
        return (suits, ranks);
    }

    if contract < 4 {
        suits[declarer][contract] = (suits[declarer][contract] + TRUMP_SUIT_PULL).min(LIMIT);
    } else if contract == OBENABE {
        ranks[declarer] = (ranks[declarer] + OBENABE_PULL).min(LIMIT);
    } else if contract == UNDENUFE {
        ranks[declarer] = (ranks[declarer] + UNDENUFE_PULL).max(-LIMIT);
    }

    (suits, ranks)
}
