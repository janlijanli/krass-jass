//! Determinization: deal the unseen cards into the other seats at random, consistent with
//! what the seat has *proved* about them.
//!
//! Void tracking is exact inference, not a model: a player who failed to follow suit is
//! provably void in it. `PLAN.md` §3.3 calls this the highest value-per-line feature in the
//! search, and it is the only constraint applied here — the published work found that
//! sampling from a *learned* card distribution did not beat uniform sampling and mostly
//! added variance, so this deliberately stays uniform.

use crate::cards::*;
use crate::rng::Rng;

/// Deal `unseen` into the seats needing cards, respecting known voids.
///
/// `counts[seat]` is how many cards that seat holds, `voids[seat]` a suit bitmask.
/// Returns false if the constraints could not be satisfied, so the caller can retry with a
/// fresh sample rather than silently producing an inconsistent world.
pub fn determinize(
    unseen: u64,
    counts: &[usize; NUM_SEATS],
    voids: &[u8; NUM_SEATS],
    out: &mut [u64; NUM_SEATS],
    rng: &mut Rng,
) -> bool {
    // Most constrained seat first, which is what keeps the rejection rate low.
    let mut order: Vec<usize> = (0..NUM_SEATS).filter(|&s| counts[s] > 0).collect();
    order.sort_by_key(|&s| (voids[s].count_ones() as i32, s as i32));
    order.reverse();

    let mut pool = unseen;
    for &seat in &order {
        let mut allowed = pool;
        for suit in 0..NUM_SUITS {
            if voids[seat] & (1 << suit) != 0 {
                allowed &= !SUIT_MASK[suit];
            }
        }
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
