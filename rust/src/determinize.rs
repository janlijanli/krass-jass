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
    out: &mut [u64; NUM_SEATS],
    rng: &mut Rng,
) -> bool {
    // Most constrained seat first, which is what keeps the rejection rate low.
    let mut order: Vec<usize> = (0..NUM_SEATS).filter(|&s| counts[s] > 0).collect();
    order.sort_by_key(|&s| ((unseen & !forbidden[s]).count_ones() as i32, s as i32));

    let mut pool = unseen;
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
        let flat = affinity[seat] == [0i8; 4];

        let mut hand = 0u64;
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
                let n = (allowed & SUIT_MASK[suit]).count_ones();
                per_suit[suit] = n * weight(affinity[seat][suit]);
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

            let mut m = allowed & SUIT_MASK[chosen];
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
