//! A static estimate of what a leaf is worth, in place of a random playout.
//!
//! The leaf evaluator decides the value of every imagined world, and it is currently **one
//! random playout** — a single sample of a quantity with enormous variance.
//! `docs/measurements.md` §5e says the only changes that can pay are the ones that move what
//! a world is *worth*; this is that, and `docs/value-net-plan.md` §Phase 0 is this file.
//!
//! # What it is fitted to, and why that is the interesting choice
//!
//! Not "the true value of the position" — **the expected value of the random playout**. That
//! makes this a pure variance-reduction experiment: same estimand, one sample replaced by a
//! noiseless estimate of its mean. Nothing about the search's target changes, so if it moves
//! anything, rollout noise was the reason.
//!
//! §3a found the search collapsing below ~30 iterations per world (240x10 scored 47.56%,
//! 600x4 scored 41.41%). If that floor is there because the tree needs many rollouts merely
//! to average out noise, a noiseless evaluator should lower it. That is the falsifiable part.
//!
//! Accuracy beyond the playout's own mean — labelling from stronger continuations — is a
//! second experiment stacked on this one, and only worth running if this one moves.
//!
//! # Features
//!
//! Everything is oriented to the searching team and scaled to roughly [0, 1], because a
//! linear model has no way to learn a scale. All of it is cheap bitboard arithmetic: the
//! evaluator has to beat 0.40 µs to be worth having at equal iterations.

use crate::cards::{card_suit, NUM_SEATS, NUM_SUITS, SUIT_MASK};
use crate::rollout::Kernel;
use crate::tables::{CARD_VALUES, STRENGTH};

pub const N_FEATURES: usize = 14;

/// The strongest unplayed card of `suit`, as a single-bit mask. Strength, not rank, so
/// Undenufe reads the right way round — a seven that is now the best card left is the whole
/// reason this feature exists.
pub fn top_live(live: u64, suit: usize, contract: usize) -> u64 {
    let cards = live & SUIT_MASK[suit];
    if cards == 0 {
        return 0;
    }
    let strength = &STRENGTH[contract][suit];
    let mut best = cards.trailing_zeros() as usize;
    let mut rest = cards & (cards - 1);
    while rest != 0 {
        let c = rest.trailing_zeros() as usize;
        if strength[c] > strength[best] {
            best = c;
        }
        rest &= rest - 1;
    }
    1u64 << best
}

/// Feature vector for a leaf, from `root_team`'s point of view.
#[allow(clippy::too_many_arguments)]
pub fn features(
    hands: &[u64; NUM_SEATS],
    trick: &[usize],
    trick_leader: usize,
    to_play: usize,
    tricks: &[usize; 2],
    k: &Kernel,
    root_team: usize,
    out: &mut [f64; N_FEATURES],
) {
    let contract = k.contract;
    let values = &CARD_VALUES[contract];
    let trump: i32 = if contract < 4 { contract as i32 } else { -1 };

    let live = hands[0] | hands[1] | hands[2] | hands[3];
    let mut pts = [0.0f64; 2];
    let mut trumps = [0.0f64; 2];
    let mut boss = [0.0f64; 2];
    let mut cards_left = 0.0f64;

    for seat in 0..NUM_SEATS {
        let team = seat & 1;
        let h = hands[seat];
        cards_left += h.count_ones() as f64;
        let mut rest = h;
        while rest != 0 {
            let c = rest.trailing_zeros() as usize;
            pts[team] += values[c] as f64;
            rest &= rest - 1;
        }
        if trump >= 0 {
            trumps[team] += (h & SUIT_MASK[trump as usize]).count_ones() as f64;
        }
    }
    // Who holds the best card left in each suit. A boss card is a trick you can take when you
    // choose to, which is worth more than its face value and is invisible to card points.
    for suit in 0..NUM_SUITS {
        let top = top_live(live, suit, contract);
        if top == 0 {
            continue;
        }
        for seat in 0..NUM_SEATS {
            if hands[seat] & top != 0 {
                boss[seat & 1] += 1.0;
            }
        }
    }

    // The partial trick: what is on the table and whether it is currently ours.
    let mut table_pts = 0.0f64;
    let mut table_ours = 0.0f64;
    if let Some(&first) = trick.first() {
        let strength = &STRENGTH[contract][card_suit(first)];
        let mut best = 0usize;
        for (i, &c) in trick.iter().enumerate() {
            table_pts += values[c] as f64;
            if strength[c] > strength[trick[best]] {
                best = i;
            }
        }
        let winner = (trick_leader + best) % NUM_SEATS;
        table_ours = if winner & 1 == root_team { 1.0 } else { 0.0 };
    }

    let us = root_team;
    let them = 1 - root_team;
    out[0] = 1.0;
    out[1] = cards_left / 36.0;
    out[2] = pts[us] / 157.0;
    out[3] = pts[them] / 157.0;
    out[4] = trumps[us] / 9.0;
    out[5] = trumps[them] / 9.0;
    out[6] = boss[us] / 4.0;
    out[7] = boss[them] / 4.0;
    out[8] = if to_play & 1 == root_team { 1.0 } else { 0.0 };
    out[9] = table_pts / 30.0;
    out[10] = table_ours;
    out[11] = tricks[us] as f64 / 9.0;
    out[12] = tricks[them] as f64 / 9.0;
    // Being on lead with the boss cards is worth more than either alone — the one interaction
    // a linear model cannot discover for itself.
    out[13] = out[8] * out[6];
}

/// Dot product, clamped: the search needs a value in [0, 1] for UCT and for the opponent flip.
pub fn evaluate(weights: &[f64], feats: &[f64; N_FEATURES]) -> f64 {
    let mut acc = 0.0;
    for i in 0..N_FEATURES {
        acc += weights[i] * feats[i];
    }
    acc.clamp(0.0, 1.0)
}
