//! Rounds whose card order changes from trick to trick. Twin of `krass_jass/schedule.py`, which
//! carries the prose; `docs/rules-config.md`, "Coiffeur — the extra rows", is the rule text.
//!
//! A schedule is the contract in force for each of the nine tricks. Every card order in it is
//! one of the six the engine already has, so legality, trick winners and values are the existing
//! tables indexed per trick. The round is **counted** in the first trick's contract.
//!
//! A 3x3's second and third blocks are named during the round by the leaders of tricks 4 and 7,
//! so until then their tricks hold `UNNAMED`. A Tutti's tricks are named by their lead card — the
//! suit led is trump — so until each is led it holds `LED`, and the round is counted in the suit
//! of its very first card.

use crate::config::Rules;
use crate::scoring::TRICKS_PER_ROUND;
use crate::tables::contract_name;

const OBENABE: usize = 4;
const UNDENUFE: usize = 5;

/// The extra rows' sheet slots and names, after the six contracts and the Chance (`coiffeur.rs`).
pub const EXTRA_ROWS: [&str; 5] = ["TUTTI", "SLALOM", "GUSCHTI", "TRIO", "MISERE"];
pub const FIRST_EXTRA_ROW: usize = 7;
/// A 3x3's blocks start at these tricks; the leader of each names it.
pub const TRIO_BLOCKS: [usize; 3] = [0, 3, 6];
/// A trick whose 3x3 block has not been named yet.
pub const UNNAMED: usize = usize::MAX;
/// A Tutti trick not led yet: its contract is the trump of the suit led to it.
pub const LED: usize = usize::MAX - 1;
/// What a Tutti is counted in before its first card (`TUTTI_PLACEHOLDER` in Python).
pub const TUTTI_PLACEHOLDER: usize = OBENABE;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Schedule {
    /// Obenabe and Undenufe alternate, starting with `first`.
    Slalom { first: usize },
    /// `n` tricks of `first`, then the rest the other way.
    Guschti { first: usize, n: usize },
    /// 3x3: the first block in `first`; the other two are named during the round.
    Trio { first: usize },
    /// Misère: nine tricks of `contract`, and each team is credited with what the other took.
    Misere { contract: usize },
    /// Tutti: the suit led to each trick is trump for it.
    Tutti,
}

fn other(c: usize) -> usize {
    if c == OBENABE { UNDENUFE } else { OBENABE }
}

impl Schedule {
    pub fn tricks(&self) -> [usize; TRICKS_PER_ROUND] {
        let mut out = [0usize; TRICKS_PER_ROUND];
        for (i, slot) in out.iter_mut().enumerate() {
            *slot = match *self {
                Schedule::Slalom { first } => if i % 2 == 0 { first } else { other(first) },
                Schedule::Guschti { first, n } => if i < n { first } else { other(first) },
                Schedule::Trio { first } => if i < 3 { first } else { UNNAMED },
                Schedule::Misere { contract } => contract,
                Schedule::Tutti => LED,
            };
        }
        out
    }

    /// The contract the round's card points are counted in: the first trick's. A Tutti's is not
    /// known until the first card; until then, the placeholder.
    pub fn count(&self) -> usize {
        if self.led() { TUTTI_PLACEHOLDER } else { self.tricks()[0] }
    }

    /// Tutti: each trick is named by its lead card.
    pub fn led(&self) -> bool {
        matches!(self, Schedule::Tutti)
    }

    /// The sheet slot of the extra row this schedule belongs in.
    pub fn row(&self) -> usize {
        FIRST_EXTRA_ROW
            + match self {
                Schedule::Tutti => 0,
                Schedule::Slalom { .. } => 1,
                Schedule::Guschti { .. } => 2,
                Schedule::Trio { .. } => 3,
                Schedule::Misere { .. } => 4,
            }
    }

    pub fn misere(&self) -> bool {
        matches!(self, Schedule::Misere { .. })
    }

    pub fn name(&self) -> String {
        match *self {
            Schedule::Slalom { first } => format!("SLALOM_{}", contract_name(first)),
            Schedule::Guschti { first, n } => {
                let prefix = if n == 5 { "GUSCHTI" } else { "GUSCHTI4" };
                format!("{prefix}_{}", contract_name(first))
            }
            Schedule::Trio { first } => format!("TRIO_{}", contract_name(first)),
            Schedule::Misere { contract } => format!("MISERE_{}", contract_name(contract)),
            Schedule::Tutti => "TUTTI".to_string(),
        }
    }

    pub fn parse(text: &str) -> Option<Schedule> {
        let upper = text.trim().to_ascii_uppercase();
        let parts: Vec<&str> = upper.split('_').collect();
        let contract = |name: &str| (0..6).find(|&c| contract_name(c) == name);
        match parts.as_slice() {
            ["SLALOM", c] => contract(c).filter(|&c| c >= 4).map(|first| Schedule::Slalom { first }),
            ["GUSCHTI", c] => {
                contract(c).filter(|&c| c >= 4).map(|first| Schedule::Guschti { first, n: 5 })
            }
            ["GUSCHTI4", c] => {
                contract(c).filter(|&c| c >= 4).map(|first| Schedule::Guschti { first, n: 4 })
            }
            ["TRIO", c] => contract(c).map(|first| Schedule::Trio { first }),
            ["TUTTI"] => Some(Schedule::Tutti),
            ["MISERE", c] => {
                contract(c).filter(|&c| c >= 4).map(|contract| Schedule::Misere { contract })
            }
            _ => None,
        }
    }

    pub fn is_name(text: &str) -> bool {
        let upper = text.trim().to_ascii_uppercase();
        matches!(
            upper.split('_').next(),
            Some("TUTTI" | "SLALOM" | "GUSCHTI" | "GUSCHTI4" | "TRIO" | "MISERE")
        )
    }
}

/// Every schedule a player may choose for an extra row, in the order of `for_row` in Python.
pub fn for_row(row: usize, rules: &Rules) -> Vec<Schedule> {
    match row - FIRST_EXTRA_ROW {
        0 => vec![Schedule::Tutti],
        1 => vec![Schedule::Slalom { first: OBENABE }, Schedule::Slalom { first: UNDENUFE }],
        2 => {
            let mut out = vec![
                Schedule::Guschti { first: OBENABE, n: 5 },
                Schedule::Guschti { first: UNDENUFE, n: 5 },
            ];
            if rules.coiffeur_guschti_45 {
                out.push(Schedule::Guschti { first: OBENABE, n: 4 });
                out.push(Schedule::Guschti { first: UNDENUFE, n: 4 });
            }
            out
        }
        3 => (0..6).map(|first| Schedule::Trio { first }).collect(),
        _ => vec![Schedule::Misere { contract: OBENABE }, Schedule::Misere { contract: UNDENUFE }],
    }
}

/// What the leader of trick `at` may name for a 3x3's block, in contract order. Any contract,
/// except that the three blocks must include a trump suit and Obenabe or Undenufe — so the third
/// is forced when the first two left one out. Mirror of `block_options` in `schedule.py`.
pub fn block_options(tricks: &[usize; TRICKS_PER_ROUND], at: usize) -> Vec<usize> {
    if !TRIO_BLOCKS[1..].contains(&at) || tricks[at] != UNNAMED {
        return Vec::new();
    }
    if at == TRIO_BLOCKS[2] {
        let named = [tricks[TRIO_BLOCKS[0]], tricks[TRIO_BLOCKS[1]]];
        if named.iter().all(|&c| c >= 4) {
            return (0..4).collect();
        }
        if named.iter().all(|&c| c < 4) {
            return vec![OBENABE, UNDENUFE];
        }
    }
    (0..6).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_round_trip_and_tricks_are_as_named() {
        let rules = Rules { coiffeur_guschti_45: true, ..Rules::coiffeur() };
        for row in FIRST_EXTRA_ROW..FIRST_EXTRA_ROW + EXTRA_ROWS.len() {
            for s in for_row(row, &rules) {
                assert_eq!(Schedule::parse(&s.name()), Some(s));
                assert_eq!(s.row(), row);
            }
        }
        assert_eq!(Schedule::Slalom { first: 5 }.tricks(), [5, 4, 5, 4, 5, 4, 5, 4, 5]);
        assert_eq!(Schedule::Guschti { first: 4, n: 5 }.tricks(), [4, 4, 4, 4, 4, 5, 5, 5, 5]);
        let trio = Schedule::parse("TRIO_HEARTS").unwrap();
        assert_eq!(trio.tricks()[..4], [1, 1, 1, UNNAMED]);
        assert_eq!(trio.count(), 1);
        let mut t = trio.tricks();
        assert_eq!(block_options(&t, 3), (0..6).collect::<Vec<_>>());
        t[3..6].fill(2);
        assert_eq!(block_options(&t, 6), vec![4, 5]);
        assert_eq!(Schedule::parse("SLALOM_HEARTS"), None);
        assert_eq!(Schedule::parse("MISERE_HEARTS"), None);
        assert!(Schedule::parse("MISERE_UNDENUFE").unwrap().misere());
        let tutti = Schedule::parse("TUTTI").unwrap();
        assert!(tutti.led() && tutti.tricks() == [LED; TRICKS_PER_ROUND]);
        assert_eq!(tutti.count(), TUTTI_PLACEHOLDER);
    }
}
