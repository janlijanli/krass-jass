//! Coiffeur: the sheet, its multipliers, and who chooses. Twin of `krass_jass/coiffeur.py`,
//! which carries the prose; `docs/rules-config.md`, "Coiffeur", is the rule text.
//!
//! Eight rows per team — the four suits, Obenabe, Undenufe, two Jokers — plus the extra rows the
//! game is played with (Slalom, Guschti, 3x3; `schedule.rs`), each played once. Forehand chooses
//! or shoves to the next seat; after four shoves forehand must choose. Once a team is done the
//! other chooses alone and may shove to the partner and back, once.
//!
//! Rows have fixed slots whichever are played: 0-5 the contracts, 6-7 the Jokers, 8-11 the
//! extra rows. A slot the game does not play is never open and never written.

use crate::cards::NUM_SEATS;
use crate::config::{team_of, Rules};
use crate::rng::Rng;
use crate::schedule::{for_row, Schedule, FIRST_EXTRA_ROW};
use crate::tables::{contract_name, NUM_CONTRACTS};

/// Every slot on the sheet, played or not.
pub const ALL_ROWS: usize = 12;
pub const JOKER_ROWS: [usize; 2] = [6, 7];
pub const ROW_NAMES: [&str; ALL_ROWS] = [
    "DIAMONDS", "HEARTS", "SPADES", "CLUBS", "OBENABE", "UNDENUFE", "JOKER1", "JOKER2",
    "SLALOM", "GUSCHTI", "TRIO", "MISERE",
];

/// The `Rng::split` index the multipliers are drawn from — clear of every round's deal.
pub const MULTIPLIER_STREAM: u64 = 0xC0FFE00000000001;

/// The slots this game plays, in sheet order.
pub fn active_rows(rules: &Rules) -> Vec<usize> {
    let mut rows: Vec<usize> = (0..FIRST_EXTRA_ROW).collect();
    for (i, &on) in rules.coiffeur_extra_rows.iter().enumerate() {
        if on {
            rows.push(FIRST_EXTRA_ROW + i);
        }
    }
    rows
}

/// What a round's card points write into a row: tens, rounded half up, or in full.
pub fn row_value(points: i32, rules: &Rules) -> i32 {
    if rules.coiffeur_tens { (points + 5).div_euclid(10) } else { points }
}

/// The row multipliers, one per slot, 0 for a slot not played. Random by default: Fisher-Yates
/// over 1..n for the n rows played, on its own stream, exactly as `multipliers` in `coiffeur.py`.
pub fn multipliers(seed: u64, rules: &Rules) -> [i32; ALL_ROWS] {
    let rows = active_rows(rules);
    let mut out = [0i32; ALL_ROWS];
    if !rules.coiffeur_random_multipliers {
        for &row in &rows {
            out[row] = rules.coiffeur_multipliers[row];
        }
        return out;
    }
    let mut rng = Rng::split(seed, MULTIPLIER_STREAM);
    let mut perm: Vec<i32> = (1..=rows.len() as i32).collect();
    for i in (1..rows.len()).rev() {
        let j = rng.below(i as u32 + 1) as usize;
        perm.swap(i, j);
    }
    for (&row, &m) in rows.iter().zip(&perm) {
        out[row] = m;
    }
    out
}

/// What is written where: a contract into its own row or a Joker, or an extra row's game into
/// that row (or a Joker, with `coiffeur_joker_takes_extra`). `contract` is the one the round is
/// counted in — a schedule's first trick's.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Choice {
    pub contract: usize,
    pub row: usize,
    pub schedule: Option<Schedule>,
}

impl Choice {
    fn plain(contract: usize, row: usize) -> Choice {
        Choice { contract, row, schedule: None }
    }

    fn game(schedule: Schedule, row: usize) -> Choice {
        Choice { contract: schedule.count(), row, schedule: Some(schedule) }
    }

    pub fn name(&self) -> String {
        let own = match self.schedule {
            Some(s) => s.name(),
            None => contract_name(self.contract).to_string(),
        };
        if JOKER_ROWS.contains(&self.row) {
            format!("{own}/{}", ROW_NAMES[self.row])
        } else {
            own
        }
    }

    pub fn parse(text: &str) -> Option<Choice> {
        let text = text.trim().to_ascii_uppercase();
        let (name, joker) = match text.split_once('/') {
            Some((n, r)) => {
                let row = JOKER_ROWS.iter().copied().find(|&j| ROW_NAMES[j] == r)?;
                (n.to_string(), Some(row))
            }
            None => (text.clone(), None),
        };
        if Schedule::is_name(&name) {
            let schedule = Schedule::parse(&name)?;
            return Some(Choice::game(schedule, joker.unwrap_or(schedule.row())));
        }
        let contract = (0..NUM_CONTRACTS).find(|&c| contract_name(c) == name)?;
        Some(Choice::plain(contract, joker.unwrap_or(contract)))
    }
}

/// Points written per team and slot; `None` while the row is open. Only `rows` are played.
#[derive(Clone, Debug)]
pub struct Sheet {
    pub rows: [bool; ALL_ROWS],
    pub written: [[Option<i32>; ALL_ROWS]; 2],
}

impl Default for Sheet {
    /// The classic eight rows.
    fn default() -> Self {
        let mut rows = [false; ALL_ROWS];
        rows[..FIRST_EXTRA_ROW].fill(true);
        Sheet { rows, written: [[None; ALL_ROWS]; 2] }
    }
}

impl Sheet {
    pub fn for_game(rules: &Rules) -> Sheet {
        let mut rows = [false; ALL_ROWS];
        for row in active_rows(rules) {
            rows[row] = true;
        }
        Sheet { rows, written: [[None; ALL_ROWS]; 2] }
    }

    pub fn is_open(&self, team: usize, row: usize) -> bool {
        self.rows[row] && self.written[team][row].is_none()
    }

    pub fn finished(&self, team: usize) -> bool {
        (0..ALL_ROWS).all(|row| !self.is_open(team, row))
    }

    pub fn complete(&self) -> bool {
        self.finished(0) && self.finished(1)
    }

    /// Every legal choice, in the order of `Sheet.choices` in Python: own rows (the contracts,
    /// then each extra row's games), then each Joker per contract and, if allowed, per game.
    pub fn choices(&self, team: usize, rules: &Rules) -> Vec<Choice> {
        let mut out: Vec<Choice> = (0..NUM_CONTRACTS)
            .filter(|&row| self.is_open(team, row))
            .map(|row| Choice::plain(row, row))
            .collect();
        for row in FIRST_EXTRA_ROW..ALL_ROWS {
            if self.is_open(team, row) {
                out.extend(for_row(row, rules).into_iter().map(|s| Choice::game(s, row)));
            }
        }
        for row in JOKER_ROWS {
            if self.is_open(team, row) {
                out.extend((0..NUM_CONTRACTS).map(|contract| Choice::plain(contract, row)));
                if rules.coiffeur_joker_takes_extra {
                    for extra in FIRST_EXTRA_ROW..ALL_ROWS {
                        if self.rows[extra] {
                            out.extend(for_row(extra, rules).into_iter().map(|s| Choice::game(s, row)));
                        }
                    }
                }
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
