//! Rule-based Coiffeur choice: which row to fill with this hand, or shove. Twin of
//! `krass_jass/coiffeur_select.py`, which carries the prose; `docs/coiffeur-plan.md` the fits.
//!
//! Each choice is worth `multiplier x (own - keep)`: `own` the game's expected points for this
//! hand (`a + b x edge`, per game), `keep` what the row is expected to fetch if kept, raised by
//! its option value while the team's column is still full. The weights are compiled in from
//! the same JSON the Python side reads (`krass_jass/data/coiffeur_weights.json`). Only the
//! fitted form is here: the shipped file has it, and the untrained fallback is Python's alone.

use crate::coiffeur::{Choice, ROW_NAMES, ALL_ROWS};
use crate::playmodel::number;
use crate::schedule::{Schedule, UNNAMED};
use crate::tables::{NUM_CONTRACTS, OBENABE, UNDENUFE};
use crate::trump::{score_obenabe, score_suit_as_trump, score_undenufe, weights as trump_weights};

const WEIGHTS_JSON: &str = include_str!("../../krass_jass/data/coiffeur_weights.json");

pub struct Weights {
    /// Per game name (`Schedule::name` or the contract's), the line `a + b x edge`.
    value_map: Vec<(String, f64, f64)>,
    points_reserve: [f64; ALL_ROWS],
    spread: [f64; ALL_ROWS],
    lift_a: f64,
    lift_b: f64,
    tau: f64,
    tau_n: f64,
}

/// The text of the object that follows `"key"`, braces balanced.
fn object<'a>(text: &'a str, key: &str) -> &'a str {
    let at = text.find(&format!("\"{key}\"")).expect("coiffeur weights key missing");
    let start = text[at..].find('{').expect("object expected") + at;
    let mut depth = 0;
    for (i, c) in text[start..].char_indices() {
        match c {
            '{' => depth += 1,
            '}' => {
                depth -= 1;
                if depth == 0 {
                    return &text[start..start + i + 1];
                }
            }
            _ => {}
        }
    }
    panic!("unterminated object");
}

/// `"name": [a, b]` pairs of an object, in file order.
fn pairs(block: &str) -> Vec<(String, f64, f64)> {
    let mut out = Vec::new();
    let mut rest = block;
    while let Some(q) = rest.find('"') {
        let after = &rest[q + 1..];
        let end = after.find('"').expect("unterminated key");
        let name = &after[..end];
        let tail = &after[end + 1..];
        let open = tail.find('[').expect("pair expected");
        let close = tail.find(']').expect("unterminated pair");
        let nums: Vec<f64> = tail[open + 1..close].split(',').map(|s| s.trim().parse().unwrap()).collect();
        out.push((name.to_string(), nums[0], nums[1]));
        rest = &tail[close + 1..];
    }
    out
}

fn per_row(block: &str) -> [f64; ALL_ROWS] {
    ROW_NAMES.map(|name| number(block, name).expect("row missing"))
}

pub fn weights() -> &'static Weights {
    use std::sync::OnceLock;
    static CELL: OnceLock<Weights> = OnceLock::new();
    CELL.get_or_init(|| {
        let text = WEIGHTS_JSON;
        let value = |key: &str| object(object(text, key), "value");
        let option = value("option_value");
        Weights {
            value_map: pairs(&value("value_map")[1..]),
            points_reserve: per_row(value("points_reserve")),
            spread: per_row(object(option, "spread")),
            lift_a: number(option, "a").unwrap(),
            lift_b: number(option, "b").unwrap(),
            tau: number(object(text, "shove_threshold"), "value").unwrap(),
            tau_n: number(option, "tau_n").unwrap(),
        }
    })
}

impl Weights {
    fn line(&self, game: &str) -> (f64, f64) {
        // A 4/5 Guschti is priced as the 5/4 one: only that was simulated.
        let game = game.replace("GUSCHTI4_", "GUSCHTI_");
        let (_, a, b) = self.value_map.iter().find(|(n, _, _)| *n == game).expect("game not priced");
        (*a, *b)
    }
}

/// The hand's edge per contract, as the Schieber scores it at multiplier one.
pub fn edges(hand: u64) -> [f64; NUM_CONTRACTS] {
    let w = trump_weights();
    let mut out = [0.0; NUM_CONTRACTS];
    for (suit, slot) in out.iter_mut().enumerate().take(4) {
        *slot = score_suit_as_trump(hand, suit, w);
    }
    out[OBENABE] = score_obenabe(hand, w);
    out[UNDENUFE] = score_undenufe(hand, w);
    out.map(|s| s - w.baseline)
}

/// The edge in one game: see `game_edge` in Python.
pub fn game_edge(edge: &[f64; NUM_CONTRACTS], contract: usize, schedule: Option<Schedule>) -> f64 {
    match schedule {
        None => edge[contract],
        Some(s) if s.misere() => -edge[contract],
        Some(s) if s.led() => edge[..4].iter().copied().fold(f64::NEG_INFINITY, f64::max),
        Some(s) => {
            let named: Vec<usize> = s.tricks().into_iter().filter(|&c| c != UNNAMED).collect();
            named.iter().map(|&c| edge[c]).sum::<f64>() / named.len() as f64
        }
    }
}

fn game_name(choice: &Choice) -> String {
    match choice.schedule {
        Some(s) => s.name(),
        None => crate::tables::contract_name(choice.contract).to_string(),
    }
}

/// How full the team's column still is: 0 with one row open, 1 with all twelve.
fn open_share(choices: &[Choice]) -> f64 {
    let mut rows = [false; ALL_ROWS];
    for c in choices {
        rows[c.row] = true;
    }
    (rows.iter().filter(|&&r| r).count() as f64 - 1.0) / 11.0
}

/// `multiplier x (own - keep)` for every choice, in order.
pub fn value_choices(hand: u64, choices: &[Choice], multipliers: &[i32; ALL_ROWS]) -> Vec<f64> {
    let w = weights();
    let edge = edges(hand);
    let share = open_share(choices);
    let lift = if share > 0.0 { w.lift_a * share.powf(w.lift_b) } else { 0.0 };
    choices
        .iter()
        .map(|choice| {
            let e = game_edge(&edge, choice.contract, choice.schedule);
            let (a, b) = w.line(&game_name(choice));
            let own = a + b * e;
            let mut keep = w.points_reserve[choice.row];
            if lift != 0.0 {
                keep += lift * w.spread[choice.row];
            }
            multipliers[choice.row] as f64 * (own - keep)
        })
        .collect()
}

/// The best choice, or `None` to shove when that is allowed and nothing is worth the row.
pub fn choose(hand: u64, choices: &[Choice], can_shove: bool, multipliers: &[i32; ALL_ROWS]) -> Option<Choice> {
    let w = weights();
    let values = value_choices(hand, choices, multipliers);
    // Ties go to the lower row, then the lower contract, then the earlier choice — Python's `max`.
    let key = |i: usize| (values[i], -(choices[i].row as i64), -(choices[i].contract as i64));
    let mut best = 0;
    for i in 1..choices.len() {
        if key(i) > key(best) {
            best = i;
        }
    }
    let threshold = w.tau + w.tau_n * open_share(choices);
    if can_shove && choices.len() > 1 && values[best] < threshold {
        return None;
    }
    Some(choices[best])
}

/// 3x3: the block to name — the contract the remaining cards are best at.
pub fn choose_block(hand: u64, options: &[usize]) -> usize {
    let edge = edges(hand);
    let mut best = options[0];
    for &c in &options[1..] {
        if edge[c] > edge[best] {
            best = c;
        }
    }
    best
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::coiffeur::Sheet;
    use crate::config::Rules;

    #[test]
    fn the_shipped_weights_parse_and_every_game_is_priced() {
        let rules = Rules::coiffeur();
        let w = weights();
        assert!(w.points_reserve.iter().all(|&r| r > 0.0) && w.tau > 0.0);
        let choices = Sheet::for_game(&rules).choices(0, &rules);
        let mults = crate::coiffeur::multipliers(7, &rules);
        assert_eq!(value_choices(0x1FF, &choices, &mults).len(), choices.len());
        assert!(choose(0x1FF, &choices, false, &mults).is_some());
    }
}
