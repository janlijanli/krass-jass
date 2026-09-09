//! Legal-move generation. A direct port of `krass_jass/legal.py` — the two must agree
//! exactly, and `tests/test_rust_conformance.py` checks that against the Python reference
//! implementation over whole random rounds.

use crate::cards::*;
use crate::tables::TRUMP_HIGHER;

/// Mask of legal cards. `trump` is -1 for Obenabe/Undenufe, `led` is -1 when leading, and
/// `best_trump_strength` is -1 when no trump has been played in the current trick.
///
/// Never returns 0 for a non-empty hand.
#[inline]
pub fn legal_moves(
    hand: u64,
    trump: i32,
    led: i32,
    best_trump_strength: i32,
    strict_undertrump: bool,
    puur_exempt: bool,
) -> u64 {
    if led < 0 {
        return hand; // leading — anything goes
    }
    let led_u = led as usize;

    if trump < 0 {
        // Obenabe / Undenufe: ordinary follow-suit, no trumping
        let follow = hand & SUIT_MASK[led_u];
        return if follow != 0 { follow } else { hand };
    }

    let trump_u = trump as usize;
    let trumps = hand & SUIT_MASK[trump_u];

    if led == trump {
        // trump led: follow with a trump unless the Puur is your only one
        if trumps == 0 {
            return hand;
        }
        if puur_exempt && trumps == PUUR_MASK[trump_u] {
            return hand;
        }
        return trumps;
    }

    // non-trump led: follow, or trump, subject to undertrumping
    let allowed_trumps = if strict_undertrump && best_trump_strength >= 0 && trumps != hand {
        trumps & (TRUMP_HIGHER[best_trump_strength as usize] << (trump_u * NUM_RANKS))
    } else {
        trumps
    };

    let follow = hand & SUIT_MASK[led_u];
    if follow != 0 {
        follow | allowed_trumps
    } else {
        (hand & !SUIT_MASK[trump_u]) | allowed_trumps
    }
}
