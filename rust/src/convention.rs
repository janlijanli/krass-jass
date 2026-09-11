//! Table conventions — the ordering applied to moves the search rated the same.
//!
//! Mirror of `krass_jass/convention.py`; the Python module carries the reasoning. The rule
//! that matters in both: this never takes a move the search preferred, only reorders the ones
//! it could not separate.

use crate::cards::{card_list, card_suit, NUM_SEATS, SUIT_MASK};
use crate::search::Candidate;
use crate::tables::{CARD_VALUES, STRENGTH};

const VOTE_SLACK: f64 = 0.05;
const SCORE_SLACK: f64 = 0.01;

/// The other suit of the same colour — `♦0 ↔ ♥1`, `♠2 ↔ ♣3`.
pub fn sister(suit: usize) -> usize {
    suit ^ 1
}

/// The strongest card of `suit` not yet played, as a single-bit mask. Strength, not rank:
/// Undenufe runs the other way.
fn top_live(live: u64, suit: usize, contract: usize) -> u64 {
    let cards = live & SUIT_MASK[suit];
    if cards == 0 {
        return 0;
    }
    let strength = &STRENGTH[contract][suit];
    let best = card_list(cards)
        .into_iter()
        .max_by_key(|&c| strength[c])
        .expect("non-empty");
    1u64 << best
}

/// The side suit this hand would like led to it.
pub fn wanted_suit(hand: u64, unseen: u64, trump: i32, contract: usize) -> i32 {
    let live = hand | unseen;
    let mut best: i32 = -1;
    let mut best_score = -1.0f64;
    for suit in 0..4usize {
        if trump >= 0 && suit == trump as usize {
            continue;
        }
        let mine = hand & SUIT_MASK[suit];
        if mine == 0 {
            continue;
        }
        let mut score = 0.1 * mine.count_ones() as f64;
        if top_live(live, suit, contract) & hand != 0 {
            score += 2.0;
        }
        if score > best_score {
            best = suit as i32;
            best_score = score;
        }
    }
    best
}

/// Whether both opponents are *proven* to hold no trump.
pub fn opponents_out_of_trump(
    forbidden: &[u64; NUM_SEATS],
    seen: u64,
    seat: usize,
    trump: i32,
) -> bool {
    if trump < 0 {
        return false;
    }
    let unseen_trumps = SUIT_MASK[trump as usize] & !seen;
    (0..NUM_SEATS)
        .filter(|other| (other + NUM_SEATS - seat) % 2 == 1)
        .all(|other| unseen_trumps & !forbidden[other] == 0)
}

/// The card to play, given what the search returned.
pub fn choose(
    candidates: &[Candidate],
    hand: u64,
    unseen: u64,
    seen: u64,
    trick: &[usize],
    seat: usize,
    trump: i32,
    contract: usize,
    forbidden: &[u64; NUM_SEATS],
) -> Option<usize> {
    let best = candidates.first()?;
    let fallback = best.card;

    // Every determinization votes for exactly one move, so the votes sum to the budget.
    let total: u32 = candidates.iter().map(|c| c.determinizations_selecting).sum();
    let slack = ((VOTE_SLACK * total.max(1) as f64).round() as u32).max(1);
    let cards: Vec<usize> = candidates
        .iter()
        .filter(|c| {
            c.determinizations_selecting + slack >= best.determinizations_selecting
                && c.mean_score >= best.mean_score - SCORE_SLACK
        })
        .map(|c| c.card)
        .collect();
    if cards.len() < 2 {
        return Some(fallback);
    }

    let values = &CARD_VALUES[contract];
    let live = hand | unseen;

    // Leading with the opponents out of trump: a top card is a trick, so take it.
    if trick.is_empty() && opponents_out_of_trump(forbidden, seen, seat, trump) {
        if let Some(&win) = cards
            .iter()
            .filter(|&&c| top_live(live, card_suit(c), contract) == 1u64 << c)
            .max_by_key(|&&c| (values[c], -(c as i64)))
        {
            return Some(win);
        }
    }

    // Discarding: neither following the led suit nor trumping, so the card is a message.
    if let Some(&first) = trick.first() {
        let led = card_suit(first);
        let throws: Vec<usize> = cards
            .iter()
            .copied()
            .filter(|&c| {
                let suit = card_suit(c);
                suit != led
                    && (trump < 0 || suit != trump as usize)
                    // Never throw a card that is still the best of its suit.
                    && top_live(live, suit, contract) != 1u64 << c
            })
            .collect();
        if !throws.is_empty() {
            let want = wanted_suit(hand, unseen, trump, contract);
            let ask = if want >= 0 { sister(want as usize) as i32 } else { -1 };
            // `-c` is the *lowest rank*: indices run ace-first inside a suit.
            let pick = throws
                .into_iter()
                .min_by_key(|&c| (card_suit(c) as i32 != ask, values[c], -(c as i64)))
                .expect("non-empty");
            return Some(pick);
        }
    }

    Some(fallback)
}
