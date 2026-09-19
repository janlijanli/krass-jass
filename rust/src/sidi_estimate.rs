//! Sidi Barrani: how likely is a bid to be made, seen from one seat?
//!
//! The owner's idea for doubling (2026-09-19): estimate what the hands at the table will
//! take, from your own cards and everything the auction said, and double when the declarers'
//! number is out of reach. Done here the way the search itself sees the table:
//!
//! 1. deal the cards this seat cannot see into the other hands, uniformly;
//! 2. weight each deal by how well it agrees with the auction — `sidi_read.rs`, the same graded
//!    belief the search uses, so a bid is evidence and never a filter;
//! 3. play each deal to the end with the play model, every seat choosing from its own hand
//!    in that deal, and write it as the rules do (`Round`, Match included).
//!
//! The weighted share of deals in which the declarers reach their bid is the estimate. It is a
//! rough one — the play model plays like an average bot, not like the search — but it is an
//! estimate of the right thing, which the stopper count it replaces was not.

use crate::cards::NUM_SEATS;
use crate::config::Rules;
use crate::determinize::determinize;
use crate::playmodel::{model, PlayCtx};
use crate::rng::Rng;
use crate::round::Round;
use crate::sidi_read::{auction_log_likelihood, Bid};

const FULL_DECK: u64 = (1u64 << 36) - 1;

/// Where the hand stands and what is being asked.
pub struct Question<'a> {
    pub seat: usize,
    /// This seat's cards still in hand.
    pub hand: u64,
    /// Every card played so far this hand, `(seat, card)` in order — empty during the auction,
    /// the lead when asked after it.
    pub history: &'a [(usize, usize)],
    pub leader: usize,
    pub contract: usize,
    pub declarer: usize,
    pub bid: i32,
    pub auction: &'a [Bid],
    /// Weight on the auction's likelihood, as `sidi_alpha` in the search.
    pub alpha: f32,
}

/// `(P(the declarers reach the bid), the declarers' expected points)` over `samples` deals.
pub fn make_probability(q: &Question, samples: usize, seed: u64) -> (f64, f64) {
    let mut rng = Rng::new(seed ^ 0x51D1_BA44_A7E5_0001);
    let mut played = [0u64; NUM_SEATS];
    for &(s, c) in q.history {
        played[s & 3] |= 1u64 << c;
    }
    let seen = q.hand | played.iter().fold(0, |a, p| a | p);
    let unseen = FULL_DECK & !seen;
    let mut counts = [0usize; NUM_SEATS];
    for s in 0..NUM_SEATS {
        if s != q.seat {
            counts[s] = 9 - played[s].count_ones() as usize;
        }
    }
    let rules = Rules::sidi();
    let m = model();
    let declarers = q.declarer & 1;

    let (mut w_sum, mut w_made, mut w_points) = (0.0f64, 0.0f64, 0.0f64);
    let mut logw = Vec::with_capacity(samples);
    let mut outcomes = Vec::with_capacity(samples);
    for _ in 0..samples {
        let mut rest = [0u64; NUM_SEATS];
        if !determinize(unseen, &counts, &[0; NUM_SEATS], &[[0; 4]; NUM_SEATS], &[0; NUM_SEATS],
                        &mut rest, &mut rng) {
            continue;
        }
        rest[q.seat] = q.hand;
        let mut dealt = rest;
        for s in 0..NUM_SEATS {
            dealt[s] |= played[s];
        }
        let lw = q.alpha * auction_log_likelihood(&dealt, q.auction, q.seat);

        let mut round = Round::new(q.contract, dealt, q.leader, rules);
        let mut ok = true;
        for &(_, c) in q.history {
            ok &= round.play(c).is_ok();
        }
        if !ok {
            continue;
        }
        while !round.done() {
            let s = round.to_play();
            let legal = round.legal_moves(s);
            let card = if legal.count_ones() == 1 {
                legal.trailing_zeros() as usize
            } else {
                let live = round.hands.iter().fold(0u64, |a, h| a | h);
                let trick = round.trick.clone();
                let ctx = PlayCtx::new(round.hands[s], live, &trick, round.leader, s,
                                       q.contract, q.declarer);
                m.sample(&ctx, legal, 1.0, &mut rng)
            };
            if round.play(card).is_err() {
                ok = false;
                break;
            }
        }
        if !ok {
            continue;
        }
        let points = round.score([0, 0], [0, 0]).total()[declarers];
        logw.push(lw as f64);
        outcomes.push(points);
    }
    if outcomes.is_empty() {
        return (0.5, 0.0);
    }
    let max = logw.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    for (lw, &points) in logw.iter().zip(&outcomes) {
        let w = (lw - max).exp();
        w_sum += w;
        w_points += w * points as f64;
        if points >= q.bid {
            w_made += w;
        }
    }
    (w_made / w_sum, w_points / w_sum)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn card(suit: usize, rank: usize) -> usize {
        suit * 9 + rank
    }

    fn hand(cards: &[usize]) -> u64 {
        cards.iter().fold(0, |a, &c| a | 1u64 << c)
    }

    #[test]
    fn holding_every_trump_that_matters_makes_a_high_bid_unlikely() {
        // Seat 0 holds the hearts Bauer, Nell, ace and king; seat 1 bid hearts 120.
        let mine = hand(&[card(1, 3), card(1, 5), card(1, 0), card(1, 1),
                          card(0, 0), card(2, 0), card(3, 0), card(0, 8), card(2, 8)]);
        let auction = [Bid { seat: 1, contract: 1, value: 120 }];
        let q = Question {
            seat: 0, hand: mine, history: &[], leader: 1, contract: 1, declarer: 1, bid: 120,
            auction: &auction, alpha: 1.0,
        };
        let (p, points) = make_probability(&q, 200, 7);
        assert!(p < 0.2, "p = {p}, declarers' points {points}");
    }

    #[test]
    fn a_modest_bid_against_a_weak_hand_is_likely_made() {
        // Seat 0 holds nothing of note; seat 1 bid hearts 50.
        let mine = hand(&[card(0, 8), card(0, 7), card(0, 6), card(2, 8), card(2, 7),
                          card(2, 6), card(3, 8), card(3, 7), card(3, 6)]);
        let auction = [Bid { seat: 1, contract: 1, value: 50 }];
        let q = Question {
            seat: 0, hand: mine, history: &[], leader: 1, contract: 1, declarer: 1, bid: 50,
            auction: &auction, alpha: 1.0,
        };
        let (p, _) = make_probability(&q, 200, 7);
        assert!(p > 0.8, "p = {p}");
    }

    #[test]
    fn the_estimate_is_reproducible_for_a_seed() {
        let mine = hand(&[card(1, 3), card(0, 0), card(0, 1), card(2, 0), card(2, 1),
                          card(3, 0), card(3, 1), card(0, 8), card(2, 8)]);
        let auction = [Bid { seat: 3, contract: 2, value: 90 }];
        let q = Question {
            seat: 0, hand: mine, history: &[], leader: 3, contract: 2, declarer: 3, bid: 90,
            auction: &auction, alpha: 1.0,
        };
        assert_eq!(make_probability(&q, 100, 3), make_probability(&q, 100, 3));
    }
}
