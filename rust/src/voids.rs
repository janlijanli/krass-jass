//! Void inference. Twin of `krass_jass/voids.py`.
//!
//! Exact inference, not a model. Two Jass-specific traps live here, and both would produce a
//! bot that quietly reasons about impossible worlds rather than anything that looks broken:
//!
//! 1. **Trumping proves nothing.** You may always trump in Jass, so a trump on a side-suit
//!    lead says nothing about whether the player could have followed.
//! 2. **A discard on a trump lead does not prove no trumps.** Under the Puur exemption the
//!    proof is only "their trump holding is a subset of {Puur}" — a statement about eight
//!    specific cards, which is why constraints are card masks rather than suit voids.

use crate::cards::{card_suit, NUM_SEATS, PUUR_MASK, SUIT_MASK};
use crate::config::Rules;

fn apply_trick(forbidden: &mut [u64; NUM_SEATS], leader: usize, cards: &[usize], trump: i32, rules: &Rules) {
    if cards.is_empty() {
        return;
    }
    let led = card_suit(cards[0]);

    for (i, &card) in cards.iter().enumerate() {
        if i == 0 {
            continue; // the lead proves nothing
        }
        let seat = (leader + i) % NUM_SEATS;
        let suit = card_suit(card);
        if suit == led {
            continue; // followed suit — no information
        }

        if trump < 0 {
            forbidden[seat] |= SUIT_MASK[led]; // plain follow-suit contract
            continue;
        }
        let trump_u = trump as usize;

        if led == trump_u {
            // Trump led and not followed. No trump — except possibly exactly the Puur.
            forbidden[seat] |= if rules.puur_exempt {
                SUIT_MASK[trump_u] & !PUUR_MASK[trump_u]
            } else {
                SUIT_MASK[trump_u]
            };
            continue;
        }
        if suit == trump_u {
            continue; // they trumped, which is always legal and proves nothing
        }
        forbidden[seat] |= SUIT_MASK[led];
    }
}

/// Per-seat mask of cards each seat provably cannot hold.
///
/// A constraint proven at any point stays true: a player who held none of a suit then cannot
/// have acquired one since.
pub fn infer_forbidden(
    tricks: &[(usize, Vec<usize>)],
    current_trick: &[usize],
    current_leader: usize,
    trump: i32,
    rules: &Rules,
) -> [u64; NUM_SEATS] {
    let mut forbidden = [0u64; NUM_SEATS];
    for (leader, cards) in tricks {
        apply_trick(&mut forbidden, *leader, cards, trump, rules);
    }
    apply_trick(&mut forbidden, current_leader, current_trick, trump, rules);
    forbidden
}
