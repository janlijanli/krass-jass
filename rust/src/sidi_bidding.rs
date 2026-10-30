//! The first Sidi Barrani bidder: the owner's bidding language, spoken literally. Twin of
//! `krass_jass/sidi_bidding.py`, which carries the reasoning; `tests/test_sidi_bidding.py`
//! holds the two to the same call over random auctions.
//!
//! Odd tens the Bauer and k more trumps (30 + 20k), even tens the Nell without the Bauer
//! (20 + 20k); Obenabe / Undenufe 30 + 10 per ace / six. A support names the supporter's own
//! card by its parity. A seat that already named the contract its partner now holds passes.

use crate::auction::Call;
use crate::cards::{card_rank, card_suit, NUM_SEATS};
use crate::tables::NUM_CONTRACTS;

const RANK_A: usize = 0;
const RANK_J: usize = 3;
const RANK_9: usize = 5;
const RANK_6: usize = 8;
const OBENABE: usize = 4;
const UNDENUFE: usize = 5;
/// The language stops at 150; 157 and 257 are not spoken by it.
const CAP: i32 = 150;

fn trumps(hand: u64, suit: usize) -> (bool, bool, i32) {
    let (mut bauer, mut nell, mut n) = (false, false, 0);
    let mut m = hand;
    while m != 0 {
        let c = m.trailing_zeros() as usize;
        m &= m - 1;
        if card_suit(c) == suit {
            n += 1;
            bauer |= card_rank(c) == RANK_J;
            nell |= card_rank(c) == RANK_9;
        }
    }
    (bauer, nell, n)
}

fn count_rank(hand: u64, rank: usize) -> i32 {
    let mut n = 0;
    let mut m = hand;
    while m != 0 {
        let c = m.trailing_zeros() as usize;
        m &= m - 1;
        n += (card_rank(c) == rank) as i32;
    }
    n
}

fn slalom_count(hand: u64, contract: usize) -> i32 {
    count_rank(hand, if contract == OBENABE { RANK_A } else { RANK_6 })
}

/// What the language says for this suit as trump, or None for "say nothing".
pub fn trump_value(hand: u64, suit: usize) -> Option<i32> {
    let (bauer, nell, n) = trumps(hand, suit);
    let more = n - 1;
    if bauer && more >= 1 {
        Some(30 + 20 * more)
    } else if (nell && more >= 1) || n >= 5 {
        Some(20 + 20 * more)
    } else {
        None
    }
}

/// The strongest thing this hand can say on its own.
pub fn opening(hand: u64) -> Option<(usize, i32)> {
    let mut best: Option<(usize, i32)> = None;
    for suit in 0..4 {
        if let Some(v) = trump_value(hand, suit) {
            if best.map_or(true, |b| v > b.1) {
                best = Some((suit, v));
            }
        }
    }
    for contract in [OBENABE, UNDENUFE] {
        let count = slalom_count(hand, contract);
        if count >= 3 {
            let v = 30 + 10 * count;
            if best.map_or(true, |b| v > b.1) {
                best = Some((contract, v));
            }
        }
    }
    best
}

/// The smallest value of the right parity that is at least `least` and beats `floor`.
fn with_parity(least: i32, odd: bool, floor: i32) -> i32 {
    let mut value = least.max(floor + 10);
    if ((value / 10) % 2 == 1) != odd {
        value += 10;
    }
    value
}

/// What to bid on a partner's `contract value`, or None for no support.
pub fn support(hand: u64, contract: usize, value: i32, floor: i32) -> Option<i32> {
    if contract >= 4 {
        let count = slalom_count(hand, contract);
        return (count > 0).then_some(value + 10 * count);
    }
    let (bauer, nell, n) = trumps(hand, contract);
    let floor = floor.max(value);
    if value % 20 == 10 {
        // Odd tens: the partner has the Bauer.
        ((nell && n >= 2) || n >= 3).then(|| with_parity(20 + 20 * (n - 1), false, floor))
    } else {
        // Even tens: the partner has the Nell.
        bauer.then(|| with_parity(30 + 20 * (n - 1), true, floor))
    }
}

/// The stopper count: the rule-based answer to "double?".
pub fn may_double(hand: u64, contract: usize, value: i32) -> bool {
    if contract >= 4 {
        return slalom_count(hand, contract) >= 2 && value >= 90;
    }
    let (bauer, nell, n) = trumps(hand, contract);
    let stoppers = 2 * bauer as i32 + nell as i32 + (n >= 3) as i32;
    (stoppers >= 3 && value >= 90) || (stoppers >= 2 && value >= 120)
}

/// One call. `double` overrides the stopper count when the caller has a better answer.
pub fn choose_call(hand: u64, auction: &[(usize, Call)], seat: usize, double: Option<bool>) -> Call {
    let high = auction.iter().rev().find_map(|&(s, c)| match c {
        Call::Bid { contract, value } => Some((s, contract, value)),
        _ => None,
    });
    let floor = high.map_or(0, |h| h.2);
    let partner = (seat + 2) % NUM_SEATS;

    if let Some((bidder, contract, value)) = high {
        if (bidder + NUM_SEATS - seat) % 2 == 1
            && double.unwrap_or_else(|| may_double(hand, contract, value))
        {
            return Call::Double;
        }
        if bidder == partner {
            let named = auction.iter().any(|&(s, c)| {
                s == seat && matches!(c, Call::Bid { contract: k, .. } if k == contract)
            });
            if named {
                return Call::Pass;
            }
        }
    }

    // Support first, then the seat's own opening; the higher wins, the earlier on a tie.
    let mut options: Vec<(usize, i32)> = Vec::with_capacity(2);
    let partners_bid = auction.iter().rev().find_map(|&(s, c)| match c {
        Call::Bid { contract, value } if s == partner => Some((contract, value)),
        _ => None,
    });
    if let Some((contract, value)) = partners_bid {
        if let Some(raised) = support(hand, contract, value, floor) {
            options.push((contract, raised));
        }
    }
    if let Some(own) = opening(hand) {
        options.push(own);
    }
    options.sort_by_key(|&(_, v)| std::cmp::Reverse(v));
    // Never outbid the opponents in a contract they named: with their trumps, wait for the knock.
    let theirs = |k: usize| {
        auction.iter().any(|&(s, c)| {
            (s + NUM_SEATS - seat) % 2 == 1 && matches!(c, Call::Bid { contract, .. } if contract == k)
        })
    };
    for (contract, value) in options {
        let value = value.min(CAP);
        if value > floor && contract < NUM_CONTRACTS && !theirs(contract) {
            return Call::Bid { contract, value };
        }
    }
    Call::Pass
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hand(cards: &[(usize, usize)]) -> u64 {
        cards.iter().fold(0, |a, &(s, r)| a | 1u64 << (s * 9 + r))
    }

    #[test]
    fn the_language_as_the_owner_gave_it() {
        assert_eq!(trump_value(hand(&[(1, RANK_J), (1, 7)]), 1), Some(50));
        assert_eq!(trump_value(hand(&[(1, RANK_9), (1, 0), (1, 1), (1, 7)]), 1), Some(80));
        assert_eq!(trump_value(hand(&[(1, 0), (1, 1), (1, 2)]), 1), None);
    }

    #[test]
    fn a_support_names_the_supporters_card() {
        assert_eq!(support(hand(&[(1, RANK_9), (1, 7)]), 1, 50, 50), Some(60));
        assert_eq!(support(hand(&[(1, RANK_J), (1, 7)]), 1, 60, 80), Some(90));
        assert_eq!(support(hand(&[(1, RANK_9)]), 1, 50, 50), None);
    }
}
