//! Determinization: deal the unseen cards into the other seats at random, consistent with
//! what the seat has *proved* about them.
//!
//! Void tracking is exact inference, not a model: a player who failed to follow suit is
//! provably void in it. `PLAN.md` §3.3 calls this the highest value-per-line feature in the
//! search.
//!
//! Constraints arrive as a per-seat mask of cards that seat provably **cannot** hold, not as
//! suit voids. That extra generality is not gratuitous: under the Puur exemption, a player
//! who discards on a trump lead proves their trump holding is a subset of {Puur} — which is
//! a statement about eight specific cards, not about a suit. See `krass_jass/voids.py`.
//!
//! # The affinity prior
//!
//! Sampling is *not* uniform any more. A per-seat, per-suit affinity from
//! `krass_jass/reading.py` tilts which suit a seat is handed next: a seat that discarded
//! Ecken is likelier to be dealt short in Ecken and long in Herz, because that is what the
//! discard convention says and what our own bots play.
//!
//! This deliberately reverses a note that used to stand here — that the published work found
//! a *learned* card distribution no better than uniform and mostly noisier. The difference is
//! what the distribution is made of. That one was fitted to a corpus and applied blind; this
//! one reads a convention the table is playing on purpose, and the weight it applies is
//! bounded four-to-one in either direction, so no world is ever removed. A player who ignores
//! the convention costs the search a little sampling efficiency and nothing else — which is
//! exactly the property a hard constraint would not have. `docs/measurements.md` carries what
//! it is worth.

use crate::cards::*;
use crate::rng::Rng;

/// Weight for one suit, as `2^affinity` in sixteenths: affinity -2..2 maps to 4..64.
///
/// Integer weights, so the sampler stays reproducible across platforms — a float here would
/// make a determinization depend on the order the compiler chose to round in.
fn weight(affinity: i8) -> u32 {
    match affinity.clamp(-2, 2) {
        -2 => 4,
        -1 => 8,
        0 => 16,
        1 => 32,
        _ => 64,
    }
}

/// Ranks 0..4 are ace down to ten; 5..8 are the nine down to the six.
///
/// A bid says more about ranks than about suits — Obenabe means aces, Undenufe means the
/// opposite, a shove means neither — so the sampler needs a pull along the rank axis as well
/// as the suit one. Two bands rather than nine weights: the evidence is "this hand is full of
/// tops" or "this hand has none", not a curve.
const HIGH_BAND: u64 = {
    let mut m = 0u64;
    let mut suit = 0;
    while suit < NUM_SUITS {
        let mut rank = 0;
        while rank < 5 {
            m |= 1u64 << (suit * NUM_RANKS + rank);
            rank += 1;
        }
        suit += 1;
    }
    m
};

/// Deal `unseen` into the seats needing cards, respecting proven constraints.
///
/// `counts[seat]` is how many cards that seat holds; `forbidden[seat]` a mask of cards it
/// provably cannot hold; `affinity[seat][suit]` the soft prior described above, all zeroes
/// for uniform sampling. Returns false if the constraints could not be satisfied, so the
/// caller can retry with a fresh sample rather than silently producing an impossible world.
pub fn determinize(
    unseen: u64,
    counts: &[usize; NUM_SEATS],
    forbidden: &[u64; NUM_SEATS],
    affinity: &[[i8; 4]; NUM_SEATS],
    rank_bias: &[i8; NUM_SEATS],
    out: &mut [u64; NUM_SEATS],
    rng: &mut Rng,
) -> bool {
    // Owned outright rather than accumulated into: the forced phase below writes through
    // `out`, so a caller's leftovers from a previous deal would be dealt a second time.
    *out = [0u64; NUM_SEATS];
    let mut pool = unseen;
    let mut counts = *counts;

    // **Forced cards first.** A card only one seat may hold has to go to that seat, and the
    // sampler has to place it *before* it fills that seat with anything else. Without this
    // the shown Weis of `measurements.md` §5l — three to five cards pinned to one hand —
    // is nearly always lost: the pinned seat draws random allowed cards, the pins are left
    // with nowhere to go, `pool` does not empty and the whole deal is thrown away. At four
    // pinned cards that happens on almost every draw, so the search could run out of worlds
    // entirely and return no move at all.
    //
    // To a fixpoint, because placing a card can fill a seat and thereby force more.
    loop {
        let mut placed = false;
        let mut rest = pool;
        while rest != 0 {
            let card = rest.trailing_zeros() as usize;
            rest &= rest - 1;
            let bit = 1u64 << card;
            let mut home = NUM_SEATS;
            let mut homes = 0;
            for seat in 0..NUM_SEATS {
                if counts[seat] > 0 && forbidden[seat] & bit == 0 {
                    home = seat;
                    homes += 1;
                }
            }
            match homes {
                0 => return false,              // nowhere to put it: no such world exists
                1 => {
                    out[home] |= bit;
                    counts[home] -= 1;
                    pool ^= bit;
                    placed = true;
                }
                _ => {}
            }
        }
        if !placed {
            break;
        }
    }

    // Most constrained seat first, which is what keeps the rejection rate low.
    let mut order: Vec<usize> = (0..NUM_SEATS).filter(|&s| counts[s] > 0).collect();
    order.sort_by_key(|&s| ((pool & !forbidden[s]).count_ones() as i32, s as i32));

    for &seat in &order {
        let allowed_all = pool & !forbidden[seat];
        let mut allowed = allowed_all;
        if (allowed.count_ones() as usize) < counts[seat] {
            return false;
        }
        // A flat prior is the overwhelmingly common case, since the reading measured out at
        // nothing and is off by default. Equal weights make the weighted path *exactly*
        // uniform — `n * 16` per suit, then uniform inside it — so this branch is a
        // shortcut and not a second behaviour. It is not a measured speed-up: benchmark
        // runs vary by ±1.5% and any difference is inside that. It is here because doing
        // arithmetic to arrive at "uniform" in the hot loop is silly, not because a number
        // said so.
        let flat = affinity[seat] == [0i8; 4] && rank_bias[seat] == 0;
        let high_w = weight(rank_bias[seat]);
        let low_w = weight(-rank_bias[seat]);

        let mut hand = out[seat];
        for _ in 0..counts[seat] {
            if flat {
                let n = allowed.count_ones();
                let mut m = allowed;
                for _ in 0..rng.below(n) {
                    m &= m - 1;
                }
                let low = m & m.wrapping_neg();
                hand |= low;
                allowed ^= low;
                pool ^= low;
                continue;
            }

            // Pick the suit first, weighted; then a card uniformly inside it. Doing it in
            // that order is what makes the prior a statement about *length*, which is what
            // a discard is evidence of — weighting individual cards would quietly make it a
            // statement about rank as well, and that is a different claim needing its own
            // measurement.
            let mut total = 0u32;
            let mut per_suit = [0u32; NUM_SUITS];
            for suit in 0..NUM_SUITS {
                let in_suit = allowed & SUIT_MASK[suit];
                let highs = (in_suit & HIGH_BAND).count_ones();
                let lows = (in_suit & !HIGH_BAND).count_ones();
                per_suit[suit] =
                    (highs * high_w + lows * low_w) * weight(affinity[seat][suit]) / 16;
                total += per_suit[suit];
            }
            let mut pick = rng.below(total);
            let mut chosen = NUM_SUITS - 1;
            for suit in 0..NUM_SUITS {
                if pick < per_suit[suit] {
                    chosen = suit;
                    break;
                }
                pick -= per_suit[suit];
            }

            // And the rank band inside it, on the same weights.
            let in_suit = allowed & SUIT_MASK[chosen];
            let highs = (in_suit & HIGH_BAND).count_ones();
            let lows = (in_suit & !HIGH_BAND).count_ones();
            let band = if rng.below(highs * high_w + lows * low_w) < highs * high_w {
                in_suit & HIGH_BAND
            } else {
                in_suit & !HIGH_BAND
            };

            let mut m = band;
            let n = m.count_ones();
            for _ in 0..rng.below(n) {
                m &= m - 1;
            }
            let low = m & m.wrapping_neg();
            hand |= low;
            allowed ^= low;
            pool ^= low;
        }
        out[seat] = hand;
    }
    // every unseen card must have found a home
    pool == 0
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The failure that made the search return **no move at all**, from a real game.
    ///
    /// A shown Weis pins four cards to one seat, so every other seat forbids them. The seat
    /// that must hold them has plenty of other cards it may also hold, and a sampler that
    /// fills it at random almost never happens to include all four — leaving them homeless
    /// and the deal discarded. Every draw failed, the tree got no children, and the caller
    /// raised on an empty candidate list.
    #[test]
    fn cards_with_only_one_possible_home_are_placed_first() {
        let pins = (1u64 << 31) | (1u64 << 32) | (1u64 << 33) | (1u64 << 34);
        let unseen = ((1u64 << 36) - 1) & !0x7Fu64;     // 29 cards, seven in the searching hand
        let counts = [10usize, 0, 10, 9];
        let mut forbidden = [0u64; NUM_SEATS];
        for seat in [1usize, 2, 3] {
            forbidden[seat] = pins;                      // the pins belong to seat 0
        }
        forbidden[0] = SUIT_MASK[1];                     // and seat 0 is void in a suit

        let mut rng = Rng::new(4);
        for _ in 0..200 {
            let mut out = [0u64; NUM_SEATS];
            assert!(
                determinize(unseen, &counts, &forbidden, &[[0i8; 4]; NUM_SEATS],
                            &[0i8; NUM_SEATS], &mut out, &mut rng),
                "a deal exists, so the sampler has to find one",
            );
            assert_eq!(out[0] & pins, pins, "the pinned cards went to the wrong seat");
            let mut union = 0u64;
            for seat in 0..NUM_SEATS {
                assert_eq!(out[seat].count_ones() as usize, counts[seat]);
                assert_eq!(out[seat] & forbidden[seat], 0, "seat {seat} got a forbidden card");
                assert_eq!(union & out[seat], 0, "a card was dealt twice");
                union |= out[seat];
            }
            assert_eq!(union, unseen, "the pool did not empty");
        }
    }

    /// Placing a card can fill a seat, which can force the next card — so one pass is not
    /// enough and the loop has to run to a fixpoint.
    #[test]
    fn forcing_one_card_can_force_the_next() {
        let unseen = 0b111u64;
        let counts = [1usize, 1, 1, 0];
        // Card 0 can only go to seat 0. That fills seat 0, which leaves card 1 only seat 1.
        let forbidden = [0u64, 0b001, 0b011, 0];
        let mut rng = Rng::new(9);
        let mut out = [0u64; NUM_SEATS];
        assert!(determinize(unseen, &counts, &forbidden, &[[0i8; 4]; NUM_SEATS],
                            &[0i8; NUM_SEATS], &mut out, &mut rng));
        assert_eq!(out[0], 0b001);
        assert_eq!(out[1], 0b010);
        assert_eq!(out[2], 0b100);
    }
}
