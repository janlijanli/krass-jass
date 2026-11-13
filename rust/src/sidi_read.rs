//! Reading a Sidi Barrani auction: what each bid says about the bidder's hand, and how much to
//! believe it.
//!
//! The bidding language is in `docs/sidi-plan.md`. A trump bid's **parity** names the card —
//! odd tens the Bauer, even tens the Nell without the Bauer — and its **size** the number of
//! other trumps (50 = Bauer + one, 80 = Nell + three). Obenabe / Undenufe count aces / sixes.
//!
//! None of it is a fact, and how far it is believed follows the owner's account of how the
//! language is used (2026-09-19):
//!
//! - a seat's **first** bid is the most literal: parity and count both believed;
//! - after that, parity still holds, but the count is a judgement call and believed weakly —
//!   seventy raised to ninety says "the Bauer" first and "three more" only maybe;
//! - a **jump** of forty or more over the standing bid (sixty to a hundred and ten) is a strong
//!   statement again, count included;
//! - supporting a partner's Obenabe / Undenufe adds ten per ace / six, and that count is believed.
//!
//! Bids are also placed tactically — a hundred and twenty instead of a hundred and ten to keep the
//! opponents under — which is one more reason every claim is a *weight* on a world and never a
//! filter. A world that contradicts a bid is looked at less, not removed: a human bids as they
//! like, and a sound belief must survive that (`CLAUDE.md`, beliefs are weights).
//!
//! **Each bid is read in its bidder's style** (`Bid::style`, public: a pair says what it plays).
//! The above is the counting style. In «Gspürsch mi, füehlsch mi» (`sidi_bidding.rs`, `FEEL`) the
//! height says nothing — the opponents push it as much as the bidder — and the claim is a floor:
//! what the seat's bids in the contract have *said* so far is the least strength it holds there.
//! A first bid in a contract and a jump are believed, a repeat is a judgement call, a raise of
//! the partner's contract says the fit card, and parity is a faint hint on a jump only.

use crate::cards::{card_rank, card_suit, NUM_SEATS};
use crate::sidi_bidding::{feel_fit, feel_said, feel_strength, feel_weights, FEEL, FEEL_FLOOR};
use crate::tables::NUM_CONTRACTS;

const RANK_A: usize = 0;
const RANK_J: usize = 3;
const RANK_9: usize = 5;
const RANK_6: usize = 8;
const OBENABE: usize = 4;

/// Log-weight a contradicted parity costs a world.
const PARITY: f32 = 2.0;
/// Per trump (ace, six) the count is off by, for a believed count and for a judgement call.
const COUNT_STRONG: f32 = 0.7;
const COUNT_WEAK: f32 = 0.2;
/// A raise this far over the standing bid is a strong statement.
const JUMP: i32 = 40;
/// «Gspürsch mi»: a raise of the partner's contract without the fit card.
const FEEL_FIT: f32 = 1.0;
/// «Gspürsch mi»: parity is a hint only — a quarter of what the counting style gives it.
const FEEL_PARITY: f32 = 0.5;

/// One bid from the auction: seat, contract index, value. Passes and doubles carry no claim.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Bid {
    pub seat: usize,
    pub contract: usize,
    pub value: i32,
    /// The bidder's style: `sidi_bidding::COUNT` or `FEEL`.
    pub style: u8,
}

/// The auction's bids as they cross from Python — `(seat, contract, value)` — each stamped with
/// its bidder's style. `styles` is one entry a seat; missing, everyone counts.
pub fn bids_from(auction: Vec<(usize, usize, i32)>, styles: Option<&[u8]>) -> Vec<Bid> {
    auction
        .into_iter()
        .map(|(seat, contract, value)| Bid {
            seat: seat & 3,
            contract,
            value,
            style: styles.and_then(|s| s.get(seat & 3).copied()).unwrap_or(crate::sidi_bidding::COUNT),
        })
        .collect()
}

impl Bid {
    /// A bid in the counting style, the default.
    pub fn count(seat: usize, contract: usize, value: i32) -> Self {
        Bid { seat, contract, value, style: crate::sidi_bidding::COUNT }
    }
}

fn count_suit(hand: u64, suit: usize) -> (bool, bool, i32) {
    let mut bauer = false;
    let mut nell = false;
    let mut n = 0;
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

/// log-weight of one bid given the bidder's *dealt* hand in a world.
fn claim(hand: u64, bid: &Bid, first: bool, jump: i32, partner_before: Option<i32>) -> f32 {
    // 157 and 257 are about the whole hand's points, not about a card; they claim nothing here.
    if bid.value > 150 || bid.value % 10 != 0 {
        return 0.0;
    }
    let strong = first || jump >= JUMP;
    if bid.contract >= 4 {
        let rank = if bid.contract == OBENABE { RANK_A } else { RANK_6 };
        let held = count_rank(hand, rank);
        let (claimed, believed) = match partner_before {
            // Supporting a partner: ten per ace / six on top of their bid.
            Some(theirs) => ((bid.value - theirs) / 10, true),
            None => ((bid.value - 30) / 10, strong),
        };
        let per = if believed { COUNT_STRONG } else { COUNT_WEAK };
        return -per * (held - claimed).abs() as f32;
    }
    let (bauer, nell, n) = count_suit(hand, bid.contract);
    let odd = bid.value % 20 == 10;
    let mut lw = 0.0;
    if odd && !bauer {
        lw -= PARITY;
    }
    if !odd {
        if bauer {
            lw -= PARITY; // with the Bauer the bid would have been odd
        } else if !nell {
            lw -= PARITY / 2.0; // a long suit may be bid even without the Nell
        }
    }
    let claimed = if odd { (bid.value - 30) / 20 } else { (bid.value - 20) / 20 };
    let per = if strong { COUNT_STRONG } else { COUNT_WEAK };
    lw - per * ((n - 1) - claimed).abs() as f32
}

/// log-weight of one «Gspürsch mi» bid given the bidder's dealt hand: `said` is what the seat's
/// bids in the contract have shown up to and including this one, `first` whether it had not bid
/// the contract before, `raise` whether the partner had, `step` the distance to the standing bid.
fn feel_claim(hand: u64, bid: &Bid, said: i32, first: bool, raise: bool, step: i32) -> f32 {
    if bid.value > 150 || bid.value % 10 != 0 || bid.contract >= NUM_CONTRACTS {
        return 0.0;
    }
    let jump = step >= 20;
    let per = if first || jump { COUNT_STRONG } else { COUNT_WEAK };
    let mut lw = -per * (said - feel_strength(hand, bid.contract)).max(0) as f32;
    if first && raise && !feel_fit(hand, bid.contract) {
        lw -= FEEL_FIT;
    }
    if first && bid.contract < 4 {
        let (bauer, _, n) = count_suit(hand, bid.contract);
        if !raise {
            // A suit is not named as one's own on fewer than three cards.
            lw -= COUNT_STRONG * (feel_weights().min_trumps - n).max(0) as f32;
        }
        // Of the two jumps the Bauer takes the odd one: an odd +30 without it, or an even +20
        // with it, is against the hint. A +20 that is odd anyway says nothing.
        let odd = bid.value % 20 == 10;
        if (odd && step == 30 && !bauer) || (!odd && step == 20 && bauer) {
            lw -= FEEL_PARITY;
        }
    }
    lw
}

/// log P(the auction | the dealt hands in this world), for every seat but `root`.
pub fn auction_log_likelihood(dealt: &[u64; NUM_SEATS], auction: &[Bid], root: usize) -> f32 {
    let mut acc = 0.0;
    let mut standing = 0;
    let mut has_bid = [false; NUM_SEATS];
    // «Gspürsch mi»: what each seat has shown in each contract, as the bidder itself counts it.
    let mut shown = [[0i32; NUM_CONTRACTS]; NUM_SEATS];
    for (i, bid) in auction.iter().enumerate() {
        let partner = (bid.seat + 2) % NUM_SEATS;
        let partner_before = auction[..i]
            .iter()
            .rev()
            .find(|b| b.seat == partner && b.contract == bid.contract)
            .map(|b| b.value);
        if bid.style == FEEL && bid.contract < NUM_CONTRACTS {
            let step = bid.value - standing.max(FEEL_FLOOR);
            let before = shown[bid.seat][bid.contract];
            let raise = partner_before.is_some();
            let said = feel_said(before, raise, step);
            shown[bid.seat][bid.contract] = said;
            if bid.seat != root {
                acc += feel_claim(dealt[bid.seat], bid, said, before == 0, raise, step);
            }
        } else if bid.seat != root {
            // A seat's first bid is its most literal, unless it is answering its partner.
            let first = !has_bid[bid.seat] && partner_before.is_none();
            acc += claim(dealt[bid.seat], bid, first, bid.value - standing, partner_before);
        }
        has_bid[bid.seat] = true;
        standing = bid.value;
    }
    acc
}

#[cfg(test)]
mod tests {
    use super::*;

    fn card(suit: usize, rank: usize) -> u64 {
        1u64 << (suit * 9 + rank)
    }

    #[test]
    fn a_felt_bid_is_a_floor_and_its_height_says_nothing() {
        // Hearts 40, felt: three hearts and strength three or more. Bauer + Nell + one is that;
        // three small hearts are not; and a hand far stronger is no worse than the first.
        let bid = Bid { seat: 1, contract: 1, value: 40, style: FEEL };
        let enough = card(1, RANK_J) | card(1, RANK_9) | card(1, 7);
        let more = enough | card(1, 0) | card(1, 1) | card(2, 0);
        let weak = card(1, 6) | card(1, 7) | card(1, 8);
        let mut hands = [0u64; 4];
        let mut ll = |h: u64, b: Bid| {
            hands[1] = h;
            auction_log_likelihood(&hands, &[b], 0)
        };
        assert_eq!(ll(enough, bid), 0.0);
        assert_eq!(ll(more, bid), 0.0);
        assert!(ll(weak, bid) < 0.0);
        // Counted, the same forty says "the Nell and one more, no Bauer" — another claim.
        assert!(ll(enough, Bid::count(1, 1, 40)) < 0.0);
    }

    #[test]
    fn a_felt_raise_says_the_fit() {
        let auction = [
            Bid { seat: 1, contract: 2, value: 40, style: FEEL },
            Bid { seat: 3, contract: 2, value: 50, style: FEEL },
        ];
        let mut hands = [0u64; 4];
        hands[1] = card(2, RANK_J) | card(2, RANK_9) | card(2, 7);
        hands[3] = card(2, 0) | card(2, 1) | card(2, 2) | card(0, 0);
        let fits = auction_log_likelihood(&hands, &auction, 0);
        hands[3] = card(2, 0) | card(0, 0) | card(1, 0);
        let misfit = auction_log_likelihood(&hands, &auction, 0);
        assert_eq!(fits, 0.0);
        assert!(misfit <= -FEEL_FIT, "{misfit}");
    }

    #[test]
    fn an_opening_believes_parity_and_count() {
        // Hearts 70: the Bauer and two more.
        let bid = Bid::count(1, 1, 70);
        let truth = card(1, RANK_J) | card(1, 0) | card(1, 8);
        let short = card(1, RANK_J) | card(1, 0);
        let no_bauer = card(1, RANK_9) | card(1, 0) | card(1, 8);
        let mut hands = [0u64; 4];
        let mut ll = |h: u64| {
            hands[1] = h;
            auction_log_likelihood(&hands, &[bid], 0)
        };
        let (t, s, n) = (ll(truth), ll(short), ll(no_bauer));
        assert_eq!(t, 0.0);
        assert!(s < t && n < s, "{t} {s} {n}");
    }

    #[test]
    fn a_small_raise_says_the_bauer_but_barely_the_count() {
        // Spades 70 from seat 1, the opponents' 80, then seat 1 again at 90.
        let auction = [
            Bid::count(1, 2, 70),
            Bid::count(2, 0, 80),
            Bid::count(1, 2, 90),
        ];
        let two_more = card(2, RANK_J) | card(2, 0) | card(2, 8);
        let three_more = two_more | card(2, 7);
        let mut hands = [0u64; 4];
        hands[2] = card(0, RANK_9) | card(0, 0) | card(0, 1) | card(0, 2);
        hands[1] = two_more;
        let a = auction_log_likelihood(&hands, &auction, 0);
        hands[1] = three_more;
        let b = auction_log_likelihood(&hands, &auction, 0);
        // The opening said two more, the raise said three: the opening wins, but only by the
        // difference between a believed count and a judgement call.
        assert!(a > b && a - b < COUNT_STRONG, "{a} {b}");
    }

    #[test]
    fn a_big_jump_is_believed() {
        let auction = [
            Bid::count(2, 3, 60),
            Bid::count(1, 1, 110),
        ];
        let four_more = card(1, RANK_J) | card(1, 0) | card(1, 1) | card(1, 2) | card(1, 4);
        let two_more = card(1, RANK_J) | card(1, 0) | card(1, 1);
        let mut hands = [0u64; 4];
        hands[1] = four_more;
        let a = auction_log_likelihood(&hands, &auction, 0);
        hands[1] = two_more;
        let b = auction_log_likelihood(&hands, &auction, 0);
        assert!(a - b >= 2.0 * COUNT_STRONG - 1e-6, "{a} {b}");
    }

    #[test]
    fn the_searching_seat_reads_nothing_about_itself() {
        let hands = [0u64; 4];
        let auction = [Bid::count(0, 1, 110)];
        assert_eq!(auction_log_likelihood(&hands, &auction, 0), 0.0);
    }
}
