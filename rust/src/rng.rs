//! A small, fast, seedable PRNG.
//!
//! Determinism is a project constraint: every game must replay bit-for-bit, and the search
//! is seeded from the engine's derived `decision_seed`. `SplitMix64` is used to expand one
//! seed into independent per-determinization streams so parallel work stays reproducible
//! regardless of how the work is scheduled.

pub struct Rng(u64);

impl Rng {
    pub fn new(seed: u64) -> Self {
        // avoid the xorshift fixed point at zero
        Rng(if seed == 0 { 0x9E3779B97F4A7C15 } else { seed })
    }

    /// SplitMix64 — used to derive independent child streams from one seed.
    pub fn split(seed: u64, index: u64) -> Self {
        let mut z = seed.wrapping_add(index.wrapping_mul(0x9E3779B97F4A7C15));
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
        Rng::new(z ^ (z >> 31))
    }

    #[inline(always)]
    pub fn next_u64(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.0 = x;
        x
    }

    /// Uniform in `[0, n)`. Lemire's multiply-shift — no division, no modulo bias worth
    /// caring about at these magnitudes.
    #[inline(always)]
    pub fn below(&mut self, n: u32) -> u32 {
        ((self.next_u64() as u128 * n as u128) >> 64) as u32
    }
}
