//! Coiffeur: the sheet, its multipliers, and who chooses. Twin of `krass_jass/coiffeur.py`,
//! which carries the prose; `docs/rules-config.md`, "Coiffeur", is the rule text.
//!
//! Eight rows per team — the four suits, Obenabe, Undenufe, two Jokers — each played once.
//! Forehand chooses or shoves to the next seat; after four shoves forehand must choose. Once a
//! team is done the other chooses alone and may shove to the partner and back, once.

use crate::cards::NUM_SEATS;
use crate::config::{team_of, Rules};
use crate::rng::Rng;
use crate::tables::{contract_name, NUM_CONTRACTS};

pub const ROWS: usize = 8;
pub const JOKER_ROWS: [usize; 2] = [6, 7];
pub const ROW_NAMES: [&str; ROWS] =
    ["DIAMONDS", "HEARTS", "SPADES", "CLUBS", "OBENABE", "UNDENUFE", "JOKER1", "JOKER2"];

/// The `Rng::split` index the multipliers are drawn from — clear of every round's deal.
pub const MULTIPLIER_STREAM: u64 = 0xC0FFE00000000001;

/// What a round's card points write into a row: tens, rounded half up, or in full.
pub fn row_value(points: i32, rules: &Rules) -> i32 {
    if rules.coiffeur_tens { (points + 5).div_euclid(10) } else { points }
}

/// The row multipliers, in row order. Random by default: Fisher-Yates over 1..8 on its own
/// stream, exactly as `multipliers` in `coiffeur.py`.
pub fn multipliers(seed: u64, rules: &Rules) -> [i32; ROWS] {
    if !rules.coiffeur_random_multipliers {
        return rules.coiffeur_multipliers;
    }
    let mut rng = Rng::split(seed, MULTIPLIER_STREAM);
    let mut out: [i32; ROWS] = core::array::from_fn(|i| i as i32 + 1);
    for i in (1..ROWS).rev() {
        let j = rng.below(i as u32 + 1) as usize;
        out.swap(i, j);
    }
    out
}

/// A contract written into a row: its own, or a Joker.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Choice {
    pub contract: usize,
    pub row: usize,
}

impl Choice {
    pub fn name(&self) -> String {
        if self.row == self.contract {
            contract_name(self.contract).to_string()
        } else {
            format!("{}/{}", contract_name(self.contract), ROW_NAMES[self.row])
        }
    }

    pub fn parse(text: &str) -> Option<Choice> {
        let text = text.trim().to_ascii_uppercase();
        let (name, row) = match text.split_once('/') {
            Some((n, r)) => (n.to_string(), Some(r.to_string())),
            None => (text.clone(), None),
        };
        let contract = (0..NUM_CONTRACTS).find(|&c| contract_name(c) == name)?;
        match row {
            None => Some(Choice { contract, row: contract }),
            Some(r) => {
                let row = JOKER_ROWS.iter().copied().find(|&j| ROW_NAMES[j] == r)?;
                Some(Choice { contract, row })
            }
        }
    }
}

/// Card points written per team and row; `None` while the row is open.
#[derive(Clone, Debug, Default)]
pub struct Sheet {
    pub written: [[Option<i32>; ROWS]; 2],
}

impl Sheet {
    pub fn is_open(&self, team: usize, row: usize) -> bool {
        self.written[team][row].is_none()
    }

    pub fn finished(&self, team: usize) -> bool {
        self.written[team].iter().all(|w| w.is_some())
    }

    pub fn complete(&self) -> bool {
        self.finished(0) && self.finished(1)
    }

    /// Every legal choice, own rows first, then each Joker per contract — the order of
    /// `Sheet.choices` in Python.
    pub fn choices(&self, team: usize) -> Vec<Choice> {
        let mut out: Vec<Choice> = (0..NUM_CONTRACTS)
            .filter(|&row| self.is_open(team, row))
            .map(|row| Choice { contract: row, row })
            .collect();
        for row in JOKER_ROWS {
            if self.is_open(team, row) {
                out.extend((0..NUM_CONTRACTS).map(|contract| Choice { contract, row }));
            }
        }
        out
    }

    fn one_done(&self) -> bool {
        self.finished(0) || self.finished(1)
    }
}

/// Forehand, unless its team is done: then the next seat of the team still choosing.
pub fn first_chooser(forehand: usize, sheet: &Sheet) -> usize {
    let mut seat = forehand;
    while sheet.finished(team_of(seat)) {
        seat = (seat + 1) % NUM_SEATS;
    }
    seat
}

pub fn shove_step(sheet: &Sheet) -> usize {
    if sheet.one_done() { 2 } else { 1 }
}

pub fn max_shoves(sheet: &Sheet) -> u32 {
    if sheet.one_done() { 2 } else { NUM_SEATS as u32 }
}

#[derive(Debug, PartialEq, Eq)]
pub enum ChooseError {
    NotYourTurn,
    MustChoose,
    RowNotOpen,
}
