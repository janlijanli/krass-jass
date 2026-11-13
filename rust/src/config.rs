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
    /// "Müessi": the Ecken 10 opens a game's first round and must choose, no shove. Twin of
    /// `ecken_ten_muss` in `rules.py`; off in the measurement preset only.
    pub ecken_ten_muss: bool,
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
    /// Sidi Barrani instead of the Schieber: the auction, the stake, the game end.
    /// `docs/rules-config.md`, "Sidi Barrani".
    pub sidi: bool,
    /// The bid ladder, lowest first. 157 is every card point, 257 is Match.
    pub sidi_bids: [i32; SIDI_BIDS],
    /// The opponents may still double after the lead, until the second card is down.
    pub sidi_double_after_lead: bool,
    /// A double during the auction ends it.
    pub sidi_double_ends_auction: bool,
    /// The bidding style each seat speaks: `sidi_bidding::COUNT` (the default) or `FEEL`. A
    /// table convention, not a rule — every call stays legal — and public: a pair says what it
    /// plays. Twin of `RulesConfig.sidi_bid_styles`.
    pub sidi_bid_styles: [u8; 4],
    /// Coiffeur instead of the Schieber: the sheet, its rows and multipliers, the game end.
    /// `docs/rules-config.md`, "Coiffeur"; `coiffeur.rs`.
    pub coiffeur: bool,
    /// Deal the row multipliers out at random from the game seed (default) or use the table.
    pub coiffeur_random_multipliers: bool,
    /// Slot order: diamonds, hearts, spades, clubs, Obenabe, Undenufe, Chance, Tutti, Slalom,
    /// Guschti, 3x3, Misère, Mitte. A slot not played is not read, nor the Chance's.
    pub coiffeur_multipliers: [i32; crate::coiffeur::ALL_ROWS],
    /// The Chance row's multiplier, random or not.
    pub coiffeur_chance_multiplier: i32,
    /// Also credit the defenders with their card points, times the row's multiplier.
    pub coiffeur_score_opponents: bool,
    /// Write card points in tens, rounded half up, and multiply those.
    pub coiffeur_tens: bool,
    /// The extra rows played: Tutti, Slalom, Guschti, 3x3, Misère, Mitte (`schedule.rs`).
    pub coiffeur_extra_rows: [bool; crate::schedule::EXTRA_ROWS.len()],
    /// Guschti also as four tricks then five.
    pub coiffeur_guschti_45: bool,
    /// The Chance may also take an extra row's game, not only one of the six contracts.
    pub coiffeur_chance_takes_extra: bool,
    /// A match is a stroke in the sheet's Match category worth this much, never multiplied; the
    /// row gets the card points. `None`: the match bonus counts into the row. See `rules.py`.
    pub coiffeur_match_stroke: Option<i32>,
    /// The table's discard convention: the colour pair (*Farbpaar*) instead of "throw the
    /// weakest". Not a rule — nothing the engine checks — but agreed at the table, so it lives
    /// here. Twin of `discard_signal == "sister"` in `rules.py`; `convention.rs`.
    pub discard_sister: bool,
}

pub const SIDI_BIDS: usize = 14;

pub const CLAIM_STOECK: u8 = 0;
pub const CLAIM_WEIS: u8 = 1;
pub const CLAIM_STICH: u8 = 2;

impl Default for Rules {
    fn default() -> Self {
        Rules {
            // DIAMONDS, HEARTS, SPADES, CLUBS, OBENABE, UNDENUFE
            multipliers: [1, 2, 1, 2, 3, 4],
            allow_zurueckschieben: false,
            ecken_ten_muss: true,
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
            sidi: false,
            sidi_bids: [40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 157, 257],
            sidi_double_after_lead: true,
            sidi_double_ends_auction: true,
            sidi_bid_styles: [0; 4],
            coiffeur: false,
            coiffeur_random_multipliers: true,
            coiffeur_multipliers: [4, 2, 3, 1, 5, 6, 0, 7, 8, 9, 10, 11, 12],
            coiffeur_chance_multiplier: 13,
            coiffeur_score_opponents: false,
            coiffeur_tens: true,
            coiffeur_extra_rows: [true; crate::schedule::EXTRA_ROWS.len()],
            coiffeur_guschti_45: false,
            coiffeur_chance_takes_extra: true,
            coiffeur_match_stroke: Some(10),
            discard_sister: false,
        }
    }
}

impl Rules {
    /// Sidi Barrani as the owner plays it: every contract x1, no Weis, no Stöck, to 2000.
    /// Twin of `SIDI` in `krass_jass/rules.py`.
    pub fn sidi() -> Self {
        Rules {
            sidi: true,
            multipliers: [1; NUM_CONTRACTS],
            weis_enabled: false,
            stoeck_enabled: false,
            target_score: 2000,
            ..Rules::default()
        }
    }

    /// Coiffeur: each team plays every row once, no Weis, no Stöck, no target. The contract
    /// multipliers are ones because the row carries the multiplier. Twin of `COIFFEUR`.
    pub fn coiffeur() -> Self {
        Rules {
            coiffeur: true,
            multipliers: [1; NUM_CONTRACTS],
            weis_enabled: false,
            stoeck_enabled: false,
            target_score: 0,
            ..Rules::default()
        }
    }

    pub fn multiplier(&self, contract: usize) -> i32 {
        self.multipliers[contract]
    }
}

#[inline(always)]
pub fn team_of(seat: usize) -> usize {
    seat & 1
}
