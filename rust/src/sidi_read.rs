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

use crate::cards::{card_rank, card_suit, NUM_SEATS};

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

/// One bid from the auction: seat, contract index, value. Passes and doubles carry no claim.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Bid {
    pub seat: usize,
    pub contract: usize,
    pub value: i32,
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

/// log P(the auction | the dealt hands in this world), for every seat but `root`.
pub fn auction_log_likelihood(dealt: &[u64; NUM_SEATS], auction: &[Bid], root: usize) -> f32 {
    let mut acc = 0.0;
    let mut standing = 0;
    let mut has_bid = [false; NUM_SEATS];
    for (i, bid) in auction.iter().enumerate() {
        let partner = (bid.seat + 2) % NUM_SEATS;
        let partner_before = auction[..i]
            .iter()
            .rev()
            .find(|b| b.seat == partner && b.contract == bid.contract)
            .map(|b| b.value);
        if bid.seat != root {
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
    fn an_opening_believes_parity_and_count() {
        // Hearts 70: the Bauer and two more.
        let bid = Bid { seat: 1, contract: 1, value: 70 };
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
            Bid { seat: 1, contract: 2, value: 70 },
            Bid { seat: 2, contract: 0, value: 80 },
            Bid { seat: 1, contract: 2, value: 90 },
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
            Bid { seat: 2, contract: 3, value: 60 },
            Bid { seat: 1, contract: 1, value: 110 },
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
        let auction = [Bid { seat: 0, contract: 1, value: 110 }];
        assert_eq!(auction_log_likelihood(&hands, &auction, 0), 0.0);
    }
}
