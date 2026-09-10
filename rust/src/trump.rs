//! Rule-based trump selection. Twin of `krass_jass/trump.py`.
//!
//! The weights are **compiled in from the same JSON** that the Python side reads
//! (`krass_jass/data/trump_weights.json`), because wasm has no filesystem. `include_str!`
//! keeps one source of truth: editing the JSON changes both implementations, and a
//! conformance test fails if they ever drift.
//!
//! The multiplier trap is the same one as in Python. It scales the round for *both* teams,
//! so it multiplies your **edge**, not your score — contracts are compared on
//! `(score - baseline) * multiplier`. Undenufe at ×4 with a mediocre hand is a bad idea,
//! not a good one worth four times as much.

use crate::cards::{card_rank, NUM_RANKS, NUM_SUITS, SUIT_MASK};
use crate::config::Rules;
use crate::tables::{NUM_CONTRACTS, OBENABE, UNDENUFE};

pub const SHOVE: usize = usize::MAX;

/// The weights file, parsed once at startup. Not a full JSON parser — it reads the exact
/// shape of the file it ships with, and a conformance test proves it agrees with Python.
const WEIGHTS_JSON: &str = include_str!("../../krass_jass/data/trump_weights.json");

pub struct Weights {
    pub trump_rank: [f64; NUM_RANKS],
    pub trump_length: [f64; NUM_RANKS + 1],
    pub side_suit: [f64; NUM_RANKS],
    pub obenabe: [f64; NUM_RANKS],
    pub undenufe: [f64; NUM_RANKS],
    pub void_bonus: f64,
    pub singleton_bonus: f64,
    pub top_run_per_card: f64,
    pub baseline: f64,
    pub shove_threshold: f64,
}

const RANK_KEYS: [&str; NUM_RANKS] = ["A", "K", "Q", "J", "T", "9", "8", "7", "6"];

fn find_object<'a>(text: &'a str, key: &str) -> &'a str {
    let at = text.find(&format!("\"{key}\"")).expect("weights key missing");
    let start = text[at..].find('{').expect("object expected") + at;
    let end = text[start..].find('}').expect("unterminated object") + start;
    &text[start..end]
}

fn number_after(block: &str, key: &str) -> Option<f64> {
    let at = block.find(&format!("\"{key}\""))?;
    let rest = &block[at + key.len() + 2..];
    let colon = rest.find(':')?;
    let tail = &rest[colon + 1..];
    let mut chars = tail.char_indices().skip_while(|(_, c)| c.is_whitespace());
    let (begin, _) = chars.next()?;
    let end = tail[begin..]
        .find(|c: char| c != '-' && c != '.' && !c.is_ascii_digit())
        .map(|i| begin + i)
        .unwrap_or(tail.len());
    tail[begin..end].trim().parse().ok()
}

fn rank_table(block: &str) -> [f64; NUM_RANKS] {
    let mut out = [0.0; NUM_RANKS];
    for (i, key) in RANK_KEYS.iter().enumerate() {
        out[i] = number_after(block, key).unwrap_or(0.0);
    }
    out
}

pub fn weights() -> &'static Weights {
    use std::sync::OnceLock;
    static CELL: OnceLock<Weights> = OnceLock::new();
    CELL.get_or_init(|| {
        let text = WEIGHTS_JSON;
        let length_block = find_object(text, "trump_length_bonus");
        let mut trump_length = [0.0; NUM_RANKS + 1];
        for (i, slot) in trump_length.iter_mut().enumerate() {
            *slot = number_after(length_block, &i.to_string()).unwrap_or(0.0);
        }
        let voids = find_object(text, "side_void_bonus");
        Weights {
            trump_rank: rank_table(find_object(text, "trump_rank_weights")),
            trump_length,
            side_suit: rank_table(find_object(text, "side_suit_weights")),
            obenabe: rank_table(find_object(text, "obenabe_weights")),
            undenufe: rank_table(find_object(text, "undenufe_weights")),
            void_bonus: number_after(voids, "void").unwrap_or(0.0),
            singleton_bonus: number_after(voids, "singleton").unwrap_or(0.0),
            top_run_per_card: number_after(find_object(text, "no_trump_top_run_bonus"), "per_card")
                .unwrap_or(0.0),
            baseline: number_after(find_object(text, "baseline"), "value").unwrap_or(0.0),
            shove_threshold: number_after(find_object(text, "shove_threshold"), "value")
                .unwrap_or(0.0),
        }
    })
}

fn suit_cards(hand: u64, suit: usize) -> Vec<usize> {
    let mut out = Vec::new();
    let mut mask = hand & SUIT_MASK[suit];
    while mask != 0 {
        let low = mask & mask.wrapping_neg();
        out.push(low.trailing_zeros() as usize);
        mask ^= low;
    }
    out
}

pub fn score_suit_as_trump(hand: u64, suit: usize, w: &Weights) -> f64 {
    let trumps = suit_cards(hand, suit);
    let mut score: f64 = trumps.iter().map(|&c| w.trump_rank[card_rank(c)]).sum();
    score += w.trump_length[trumps.len()];

    for other in 0..NUM_SUITS {
        if other == suit {
            continue;
        }
        let cards = suit_cards(hand, other);
        score += cards.iter().map(|&c| w.side_suit[card_rank(c)]).sum::<f64>();
        // Short side suits are ruffing chances, but only with trumps to ruff with.
        if trumps.len() >= 3 {
            if cards.is_empty() {
                score += w.void_bonus;
            } else if cards.len() == 1 {
                score += w.singleton_bonus;
            }
        }
    }
    score
}

fn top_run_bonus(hand: u64, w: &Weights, reverse: bool) -> f64 {
    let mut bonus = 0.0;
    for suit in 0..NUM_SUITS {
        let held: Vec<usize> = suit_cards(hand, suit).into_iter().map(card_rank).collect();
        let order: Vec<usize> = if reverse {
            (0..NUM_RANKS).rev().collect()
        } else {
            (0..NUM_RANKS).collect()
        };
        for r in order {
            if held.contains(&r) {
                bonus += w.top_run_per_card;
            } else {
                break;
            }
        }
    }
    bonus
}

pub fn score_obenabe(hand: u64, w: &Weights) -> f64 {
    let mut score = 0.0;
    for suit in 0..NUM_SUITS {
        score += suit_cards(hand, suit).iter().map(|&c| w.obenabe[card_rank(c)]).sum::<f64>();
    }
    score + top_run_bonus(hand, w, false)
}

pub fn score_undenufe(hand: u64, w: &Weights) -> f64 {
    let mut score = 0.0;
    for suit in 0..NUM_SUITS {
        score += suit_cards(hand, suit).iter().map(|&c| w.undenufe[card_rank(c)]).sum::<f64>();
    }
    score + top_run_bonus(hand, w, true)
}

/// Edge-times-stakes score for every contract. Higher is better.
pub fn score_all(hand: u64, rules: &Rules) -> [f64; NUM_CONTRACTS] {
    let w = weights();
    let mut out = [0.0; NUM_CONTRACTS];
    for suit in 0..NUM_SUITS {
        out[suit] = score_suit_as_trump(hand, suit, w);
    }
    out[OBENABE] = score_obenabe(hand, w);
    out[UNDENUFE] = score_undenufe(hand, w);
    for (contract, slot) in out.iter_mut().enumerate() {
        *slot = (*slot - w.baseline) * rules.multiplier(contract) as f64;
    }
    out
}

/// Pick a contract, or `SHOVE`. Never shoves off forehand, or the bidding would not
/// terminate.
pub fn select_trump(hand: u64, is_forehand: bool, rules: &Rules) -> usize {
    let scores = score_all(hand, rules);
    let mut best = 0usize;
    for contract in 1..NUM_CONTRACTS {
        // Ties go to the lower contract index, matching Python's `(score, -index)` key.
        if scores[contract] > scores[best] {
            best = contract;
        }
    }
    if is_forehand && scores[best] < weights().shove_threshold {
        return SHOVE;
    }
    best
}
