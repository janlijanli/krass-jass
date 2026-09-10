//! Rule variants. The Rust twin of `krass_jass/rules.py`.
//!
//! Same principle: every disputed point is a field with a written-down default, and nothing
//! elsewhere hardcodes a variant. `docs/rules-config.md` is the prose, and it governs both
//! implementations.

use crate::tables::NUM_CONTRACTS;

#[derive(Clone, Copy, Debug)]
pub struct Rules {
    /// Indexed by contract. Schilten + Schellen (spades + diamonds) are the cheap pair.
    pub multipliers: [i32; NUM_CONTRACTS],
    pub allow_zurueckschieben: bool,
    pub strict_undertrump: bool,
    pub puur_exempt: bool,
    pub last_trick_bonus: i32,
    pub match_bonus: i32,
    pub weis_enabled: bool,
    pub weis_large: bool,
    pub weis_four_nines: bool,
    pub weis_four_beats_sequence: bool,
    pub weis_manual: bool,
    pub stoeck_enabled: bool,
    /// 0 means "no target" — a single round.
    pub target_score: i32,
    /// Claim order as indices: 0 = stoeck, 1 = weis, 2 = stich.
    pub claim_order: [u8; 3],
}

pub const CLAIM_STOECK: u8 = 0;
pub const CLAIM_WEIS: u8 = 1;
pub const CLAIM_STICH: u8 = 2;

impl Default for Rules {
    fn default() -> Self {
        Rules {
            // DIAMONDS, HEARTS, SPADES, CLUBS, OBENABE, UNDENUFE
            multipliers: [1, 2, 1, 2, 3, 4],
            allow_zurueckschieben: false,
            strict_undertrump: true,
            puur_exempt: true,
            last_trick_bonus: 5,
            match_bonus: 100,
            weis_enabled: true,
            weis_large: false,
            weis_four_nines: true,
            weis_four_beats_sequence: true,
            weis_manual: false,
            stoeck_enabled: true,
            target_score: 3000,
            claim_order: [CLAIM_STOECK, CLAIM_WEIS, CLAIM_STICH],
        }
    }
}

impl Rules {
    pub fn multiplier(&self, contract: usize) -> i32 {
        self.multipliers[contract]
    }
}

#[inline(always)]
pub fn team_of(seat: usize) -> usize {
    seat & 1
}
