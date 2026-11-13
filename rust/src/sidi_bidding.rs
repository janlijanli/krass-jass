//! The first Sidi Barrani bidder: the owner's bidding language, spoken literally. Twin of
//! `krass_jass/sidi_bidding.py`, which carries the reasoning; `tests/test_sidi_bidding.py`
//! holds the two to the same call over random auctions.
//!
//! Odd tens the Bauer and k more trumps (30 + 20k), even tens the Nell without the Bauer
//! (20 + 20k); Obenabe / Undenufe 30 + 10 per ace / six. A support names the supporter's own
//! card by its parity. A seat that already named the contract its partner now holds passes.
//!
//! That is the style `COUNT`. `FEEL` — «Gspürsch mi, füehlsch mi» — is the second half of the
//! file: a bid is the cheapest step, and the message is which contract and how often.

use crate::auction::Call;
use crate::cards::{card_rank, card_suit, NUM_SEATS};
use crate::tables::NUM_CONTRACTS;

const RANK_A: usize = 0;
const RANK_K: usize = 1;
const RANK_J: usize = 3;
const RANK_9: usize = 5;
const RANK_7: usize = 7;
const RANK_6: usize = 8;
/// The bidding styles, numbered as `krass_jass.sidi_bidding.STYLES` orders them.
pub const COUNT: u8 = 0;
pub const FEEL: u8 = 1;
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

/// One call. `double` overrides the stopper count when the caller has a better answer; `style`
/// is the language this seat speaks (doubling is the same in both).
pub fn choose_call(
    hand: u64, auction: &[(usize, Call)], seat: usize, double: Option<bool>, style: u8,
) -> Call {
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
    }
    if style == FEEL {
        return feel_call(hand, auction, seat);
    }
    if let Some((bidder, contract, _)) = high {
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

// -- «Gspürsch mi, füehlsch mi» --------------------------------------------------------------
//
// Twin of the second half of `krass_jass/sidi_bidding.py`, which carries the reasoning. The
// numbers are compiled in from the JSON both read.

const FEEL_JSON: &str = include_str!("../../krass_jass/data/sidi_feel.json");

pub struct FeelWeights {
    pub open: i32,
    pub raise: i32,
    pub jump: i32,
    pub lid_base: i32,
    pub min_trumps: i32,
    pub bauer: i32,
    pub nell: i32,
    pub trump_ace: i32,
    pub long_from: i32,
    pub side_ace: i32,
    pub top: i32,
    pub second: i32,
}

pub fn feel_weights() -> &'static FeelWeights {
    use std::sync::OnceLock;
    static CELL: OnceLock<FeelWeights> = OnceLock::new();
    CELL.get_or_init(|| {
        let n = |key: &str| {
            crate::trump::number_after(FEEL_JSON, key).expect("sidi_feel.json: key missing") as i32
        };
        FeelWeights {
            open: n("open"),
            raise: n("raise"),
            jump: n("jump"),
            lid_base: n("lid_base"),
            min_trumps: n("min_trumps"),
            bauer: n("bauer"),
            nell: n("nell"),
            trump_ace: n("trump_ace"),
            long_from: n("long_from"),
            side_ace: n("side_ace"),
            top: n("top"),
            second: n("second"),
        }
    })
}

fn has(hand: u64, suit: usize, rank: usize) -> bool {
    hand & (1u64 << (suit * 9 + rank)) != 0
}

/// What the hand is worth in `contract`, in the points the style counts in.
pub fn feel_strength(hand: u64, contract: usize) -> i32 {
    let w = feel_weights();
    if contract >= 4 {
        let (top, second) = if contract == OBENABE { (RANK_A, RANK_K) } else { (RANK_6, RANK_7) };
        let mut total = 0;
        for suit in 0..4 {
            if has(hand, suit, top) {
                total += w.top + if has(hand, suit, second) { w.second } else { 0 };
            }
        }
        return total;
    }
    let (bauer, nell, n) = trumps(hand, contract);
    let mut total = w.bauer * bauer as i32 + w.nell * nell as i32 + (n - w.long_from + 1).max(0);
    for suit in 0..4 {
        if has(hand, suit, RANK_A) {
            total += if suit == contract { w.trump_ace } else { w.side_ace };
        }
    }
    total
}

/// Enough to say "it fits" to a partner's contract.
pub fn feel_fit(hand: u64, contract: usize) -> bool {
    if contract >= 4 {
        return slalom_count(hand, contract) >= 1;
    }
    let (bauer, nell, n) = trumps(hand, contract);
    bauer || nell || n >= 3
}

/// The step a bid makes over the standing one; an opening counts from 30.
pub const FEEL_FLOOR: i32 = 30;

/// What one bid adds to what its seat has shown in the contract: `before` is what the seat had
/// shown there (0 for nothing), `partner_named` whether the partner bid the contract earlier.
pub fn feel_said(before: i32, partner_named: bool, step: i32) -> i32 {
    let w = feel_weights();
    let said = if before > 0 {
        before + 1
    } else if partner_named {
        w.raise
    } else {
        w.open
    };
    if step >= 20 { said + w.jump } else { said }
}

/// The strength `seat` has shown so far, per contract (0 where it has not bid).
pub fn feel_shown(auction: &[(usize, Call)], seat: usize) -> [i32; NUM_CONTRACTS] {
    let partner = (seat + 2) % NUM_SEATS;
    let mut shown = [0; NUM_CONTRACTS];
    let mut partners = [false; NUM_CONTRACTS];
    let mut standing = FEEL_FLOOR;
    for &(s, c) in auction {
        let Call::Bid { contract, value } = c else { continue };
        if contract < NUM_CONTRACTS {
            if s == seat {
                shown[contract] = feel_said(shown[contract], partners[contract], value - standing);
            } else if s == partner {
                partners[contract] = true;
            }
        }
        standing = value;
    }
    shown
}

fn feel_value(
    hand: u64, contract: usize, mine: &[i32; NUM_CONTRACTS], partners: &[i32; NUM_CONTRACTS],
    standing: i32,
) -> Option<i32> {
    let w = feel_weights();
    let strength = feel_strength(hand, contract);
    let first = mine[contract] == 0;
    let trump = contract < 4;
    let need = if !first {
        mine[contract] + 1
    } else if partners[contract] > 0 {
        if !feel_fit(hand, contract) {
            return None;
        }
        w.raise
    } else {
        if trump && trumps(hand, contract).2 < w.min_trumps {
            return None;
        }
        w.open
    };
    if strength < need {
        return None;
    }
    let lid = CAP.min(w.lid_base + 10 * (strength + partners[contract]));
    let plain = standing + 10;
    if plain > lid {
        return None;
    }
    if strength >= need + w.jump {
        let mut jump = standing + 20;
        if trump && first && trumps(hand, contract).0 && (jump / 10) % 2 == 0 {
            jump += 10; // the Bauer: the odd one of the two jumps, if the lid allows it
        }
        if jump > lid {
            jump = standing + 20;
        }
        if jump <= lid {
            return Some(jump);
        }
    }
    Some(plain)
}

fn feel_call(hand: u64, auction: &[(usize, Call)], seat: usize) -> Call {
    let partner = (seat + 2) % NUM_SEATS;
    let high = auction.iter().rev().find_map(|&(s, c)| match c {
        Call::Bid { value, .. } => Some((s, value)),
        _ => None,
    });
    let standing = high.map_or(FEEL_FLOOR, |h| h.1);
    let mine = feel_shown(auction, seat);
    let partners = feel_shown(auction, partner);
    let theirs = |k: usize| {
        auction.iter().any(|&(s, c)| {
            (s + NUM_SEATS - seat) % 2 == 1 && matches!(c, Call::Bid { contract, .. } if contract == k)
        })
    };
    let value = |k: usize| {
        if theirs(k) { None } else { feel_value(hand, k, &mine, &partners, standing) }
    };

    // The partner's latest contract first: agreeing is what the auction is for.
    let latest = auction.iter().rev().find_map(|&(s, c)| match c {
        Call::Bid { contract, .. } if s == partner && contract < NUM_CONTRACTS => Some(contract),
        _ => None,
    });
    if let Some(contract) = latest {
        if let Some(value) = value(contract) {
            return Call::Bid { contract, value };
        }
        if high.map_or(false, |h| h.0 == partner) && feel_fit(hand, contract) {
            return Call::Pass; // it fits and all is said: leave the partner in it
        }
    }
    // Otherwise this seat's own best game; the stronger wins, the lower contract on a tie.
    let mut best: Option<(i32, usize, i32)> = None;
    for contract in 0..NUM_CONTRACTS {
        if Some(contract) == latest {
            continue;
        }
        let Some(v) = value(contract) else { continue };
        let strength = feel_strength(hand, contract);
        if best.map_or(true, |b| strength > b.0) {
            best = Some((strength, contract, v));
        }
    }
    match best {
        Some((_, contract, value)) => Call::Bid { contract, value },
        None => Call::Pass,
    }
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

    #[test]
    fn feeling_the_way_bids_the_cheapest_step() {
        // Bauer, Nell and a third heart: strength 3, opened at 40 — not at the 70 it counts to.
        let opener = hand(&[(1, RANK_J), (1, RANK_9), (1, 7), (0, 6), (2, 6), (3, 6)]);
        assert_eq!(choose_call(opener, &[], 0, None, FEEL), Call::Bid { contract: 1, value: 40 });
        assert_eq!(choose_call(opener, &[], 0, None, COUNT), Call::Bid { contract: 1, value: 70 });
        // The partner has the ace of hearts and two more, and a side ace: it fits, one step up.
        let partner = hand(&[(1, 0), (1, 1), (1, 2), (2, 0)]);
        let auction = [(0, Call::Bid { contract: 1, value: 40 }), (1, Call::Pass)];
        assert_eq!(choose_call(partner, &auction, 2, None, FEEL), Call::Bid { contract: 1, value: 50 });
    }

    #[test]
    fn a_jump_says_much_more() {
        // Bauer, Nell, ace and a fourth trump, a side ace: strength 6, two over an opening.
        let strong = hand(&[(2, RANK_J), (2, RANK_9), (2, 0), (2, 7), (0, 0)]);
        assert_eq!(choose_call(strong, &[], 0, None, FEEL), Call::Bid { contract: 2, value: 50 });
        let auction = [(0, Call::Bid { contract: 2, value: 50 })];
        assert_eq!(feel_shown(&auction, 0)[2], feel_weights().open + feel_weights().jump);
    }
}
