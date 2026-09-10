//! Determinization: deal the unseen cards into the other seats at random, consistent with
//! what the seat has *proved* about them.
//!
//! Void tracking is exact inference, not a model: a player who failed to follow suit is
//! provably void in it. `PLAN.md` §3.3 calls this the highest value-per-line feature in the
//! search, and it is the only constraint applied here — the published work found that
//! sampling from a *learned* card distribution did not beat uniform sampling and mostly
//! added variance, so this deliberately stays uniform.
//!
//! Constraints arrive as a per-seat mask of cards that seat provably **cannot** hold, not as
//! suit voids. That extra generality is not gratuitous: under the Puur exemption, a player
//! who discards on a trump lead proves their trump holding is a subset of {Puur} — which is
//! a statement about eight specific cards, not about a suit. See `krass_jass/voids.py`.

use crate::cards::*;
use crate::rng::Rng;

/// Deal `unseen` into the seats needing cards, respecting proven constraints.
///
/// `counts[seat]` is how many cards that seat holds; `forbidden[seat]` a mask of cards it
/// provably cannot hold. Returns false if the constraints could not be satisfied, so the
/// caller can retry with a fresh sample rather than silently producing an impossible world.
pub fn determinize(
    unseen: u64,
    counts: &[usize; NUM_SEATS],
    forbidden: &[u64; NUM_SEATS],
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
        let mut hand = 0u64;
        for _ in 0..counts[seat] {
            let n = allowed.count_ones();
            let mut m = allowed;
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
