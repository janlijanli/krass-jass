//! A learned prior over moves, from the information set.
//!
//! `docs/measurements.md` §5i put hand-written best-play knowledge into the selection rule —
//! the correct place for it, since a prior steers which moves are *searched* without biasing
//! what a position is *worth*. It measured nothing, and at high weight it measured worse: at
//! 2,400 iterations the search already knows "draw trumps, cash the boss, do not over-trump"
//! better than a rule distilled from prose does. That is the ladder's oldest result restated
//! — greedy scores the same as random.
//!
//! What was never tested is a prior **learned from play** rather than written from prose. The
//! slot is already built and shown to work; only the thing filling it changes.
//!
//! # The model, and why the first one failed
//!
//! First attempt: 36 logits from one-hot card features, a weight row per card. It measured
//! **1.2819 cross-entropy against uniform's 1.2861** — a third of a percent — because a linear
//! model over one-hot features cannot represent a *conjunction*. "This seven is now the best
//! card left because the six has gone" is a product of two features, and there are no products
//! in a linear model. Top-1 agreement reached 39% against a random 31%, so there was signal;
//! it simply could not be shaped into a useful distribution.
//!
//! So the features are of the **(state, card) pair** with one shared weight vector — the
//! standard parameterisation for scoring actions, and the one that makes the conjunctions
//! explicit: is this card the boss, would it take the trick, is my partner winning. Which is
//! precisely what the hand-written prior in `ismcts.rs` computes by guesswork. The learned
//! version fits the same shape from the search's own play, so the comparison is clean: same
//! knowledge, weights measured instead of invented.
//!
//! It is also cheaper. Sixteen features per legal move is a handful of multiply-adds, against
//! a 127x36 matrix — so this one is computed per visit and needs no caching.

use crate::cards::{card_suit, NUM_CARDS, SUIT_MASK};
use crate::leafeval::top_live;
use crate::tables::{CARD_VALUES, STRENGTH};

pub const N_POLICY_FEATURES: usize = 16;

/// Features of one candidate card in one position. All of it is available inside the search.
#[allow(clippy::too_many_arguments)]
pub fn card_features(
    card: usize,
    hand: u64,
    live: u64,
    trick: &[usize],
    contract: usize,
    trump: i32,
    partner_winning: bool,
    opponent_winning: bool,
    out: &mut [f32; N_POLICY_FEATURES],
) {
    let suit = card_suit(card);
    let values = &CARD_VALUES[contract];
    let is_trump = trump >= 0 && suit == trump as usize;
    let is_boss = top_live(live, suit, contract) == 1u64 << card;
    let value = values[card] as f32 / 11.0;
    let my_trumps = if trump >= 0 {
        (hand & SUIT_MASK[trump as usize]).count_ones() as f32 / 9.0
    } else {
        0.0
    };
    let takes = match trick.first() {
        Some(&first) => {
            let st = &STRENGTH[contract][card_suit(first)];
            let best = trick.iter().map(|&c| st[c]).max().unwrap_or(0);
            if st[card] > best { 1.0 } else { 0.0 }
        }
        None => 0.0,
    };

    out[0] = 1.0;
    out[1] = if is_trump { 1.0 } else { 0.0 };
    out[2] = value;
    out[3] = if is_boss { 1.0 } else { 0.0 };
    out[4] = (card % 9) as f32 / 8.0;
    out[5] = (hand & SUIT_MASK[suit]).count_ones() as f32 / 9.0;
    out[6] = if trick.is_empty() { 1.0 } else { 0.0 };
    out[7] = if partner_winning { 1.0 } else { 0.0 };
    out[8] = if opponent_winning { 1.0 } else { 0.0 };
    out[9] = takes;
    out[10] = out[1] * out[8];              // ruffing an opponent's trick
    out[11] = out[1] * out[7];              // trumping your own partner's
    out[12] = value * out[7];               // schmieren
    out[13] = value * out[8];               // feeding them
    out[14] = my_trumps * out[1] * out[6];  // leading trump when you hold length
    out[15] = out[3] * out[6];              // leading a boss card
}

/// Logits for the legal moves, softmaxed into a distribution over them.
pub fn learned_prior(
    weights: &[f32],
    hand: u64,
    live: u64,
    trick: &[usize],
    contract: usize,
    trump: i32,
    partner_winning: bool,
    opponent_winning: bool,
    legal: u64,
    out: &mut [f32; NUM_CARDS],
) {
    out.fill(0.0);
    let mut feats = [0.0f32; N_POLICY_FEATURES];
    let mut max = f32::NEG_INFINITY;
    let mut rest = legal;
    while rest != 0 {
        let card = rest.trailing_zeros() as usize;
        rest &= rest - 1;
        card_features(card, hand, live, trick, contract, trump,
                      partner_winning, opponent_winning, &mut feats);
        let mut acc = 0.0f32;
        for i in 0..N_POLICY_FEATURES {
            acc += weights[i] * feats[i];
        }
        out[card] = acc;
        max = max.max(acc);
    }
    let mut sum = 0.0f32;
    let mut rest = legal;
    while rest != 0 {
        let card = rest.trailing_zeros() as usize;
        rest &= rest - 1;
        out[card] = (out[card] - max).exp();
        sum += out[card];
    }
    if sum > 0.0 {
        let mut rest = legal;
        while rest != 0 {
            let card = rest.trailing_zeros() as usize;
            rest &= rest - 1;
            out[card] /= sum;
        }
    }
}
