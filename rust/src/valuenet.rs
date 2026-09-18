//! A learned value at the leaves of a *small* search — candidate B of `docs/neural-plan.md`.
//!
//! §5g put a learned evaluator in place of the random playout and lost nine points. The reason was
//! precise: it was fitted to the playout's own *mean*, so it could only ever be a lower-variance
//! copy of an estimator whose error already averages away over thousands of samples, while its own
//! error is bias that never does. Two things are different here:
//!
//! - **The target is what actually happened**, in rounds our own bot played to the end — the value
//!   of a position under good play, not under random play. A random playout is unbiased only for
//!   the second, and a real player is not random.
//! - **The search is small.** At a few thousand iterations each leaf is visited a handful of times
//!   and playout noise no longer averages out, which is where a low-variance estimate can pay.
//!
//! Inside an imagined world all four hands are known, so the inputs are perfect information,
//! relative to the seat to move. The output is the fraction of the **remaining** points — cards
//! still in hands or on the table, plus the last-trick bonus — that the mover's team will take.
//! The total remaining is known exactly, so the leaf's expected points follow directly and the
//! round's share stays linear in the estimate.
//!
//! Weights compile in from `krass_jass/data/value_net.json` on native builds; an untrained file
//! answers 0.5 for everything.

use crate::cards::{card_suit, FULL_DECK, NUM_CARDS, NUM_SEATS};
use crate::legal::legal_moves;
use crate::playmodel::{array, number};
use crate::rng::Rng;
use crate::rollout::{pick_random, play_out, Kernel};
use crate::tables::{CARD_VALUES, STRENGTH};

pub const N_VALUE_FEATURES: usize = 295;

const HANDS: usize = 0; //         4 x 36, relative to the seat to move
const TABLE: usize = 144; //       3 x 36, a card on the table by the relative seat that played it
const CONTRACT: usize = 252; //    6
const GONE: usize = 258; //        36, played in earlier tricks
const CARDS_LEFT: usize = 294; //  1

fn set_bits(out: &mut [f32], base: usize, mask: u64) {
    let mut m = mask;
    while m != 0 {
        let c = m.trailing_zeros() as usize;
        m &= m - 1;
        out[base + c] = 1.0;
    }
}

/// The seat whose turn it is at this position.
pub fn to_move(trick: &[usize], trick_leader: usize) -> usize {
    (trick_leader + trick.len()) & 3
}

pub fn features(
    hands: &[u64; NUM_SEATS],
    trick: &[usize],
    trick_leader: usize,
    contract: usize,
    out: &mut [f32; N_VALUE_FEATURES],
) {
    out.fill(0.0);
    let mover = to_move(trick, trick_leader);
    for r in 0..NUM_SEATS {
        set_bits(out, HANDS + r * NUM_CARDS, hands[(mover + r) & 3]);
    }
    let mut on_table = 0u64;
    for (i, &c) in trick.iter().enumerate() {
        let seat = (trick_leader + i) & 3;
        let r = (seat + NUM_SEATS - mover) & 3; // 1..=3: everyone before the mover in this trick
        out[TABLE + (r - 1) * NUM_CARDS + c] = 1.0;
        on_table |= 1u64 << c;
    }
    out[CONTRACT + contract.min(5)] = 1.0;
    let live = hands.iter().fold(on_table, |a, h| a | h);
    set_bits(out, GONE, FULL_DECK & !live);
    out[CARDS_LEFT] = hands[mover].count_ones() as f32 / 9.0;
}

/// Points still to be won from this position: every card in a hand or on the table, plus the
/// last-trick bonus.
pub fn remaining_points(hands: &[u64; NUM_SEATS], trick: &[usize], k: &Kernel) -> i32 {
    let values = &CARD_VALUES[k.contract];
    let mut live = trick.iter().fold(0u64, |a, &c| a | 1u64 << c);
    for h in hands {
        live |= h;
    }
    let mut total = 0;
    let mut m = live;
    while m != 0 {
        let c = m.trailing_zeros() as usize;
        m &= m - 1;
        total += values[c];
    }
    total + k.last_trick_bonus
}

fn best_trump(trick: &[usize], k: &Kernel) -> i32 {
    if k.trump < 0 || trick.is_empty() {
        return -1;
    }
    let strength = &STRENGTH[k.contract][card_suit(trick[0])];
    trick
        .iter()
        .filter(|&&c| card_suit(c) as i32 == k.trump)
        .map(|&c| strength[c] - 100)
        .max()
        .unwrap_or(-1)
}

/// One random completion of the round from this position: points each team takes from here on,
/// the last-trick bonus included. The baseline the value network has to beat.
pub fn random_remaining(
    mut hands: [u64; NUM_SEATS],
    trick: &[usize],
    trick_leader: usize,
    k: &Kernel,
    rng: &mut Rng,
) -> (i32, i32) {
    let values = &CARD_VALUES[k.contract];
    let mut t: Vec<usize> = trick.to_vec();
    let mut leader = trick_leader;
    let mut to_play = to_move(trick, trick_leader);
    let mut pts = [0i32; 2];
    while !t.is_empty() {
        let led = card_suit(t[0]) as i32;
        let legal = legal_moves(hands[to_play], k.trump, led, best_trump(&t, k),
                                k.strict_undertrump, k.puur_exempt);
        if legal == 0 {
            break;
        }
        let c = pick_random(legal, rng);
        hands[to_play] &= !(1u64 << c);
        t.push(c);
        if t.len() == NUM_SEATS {
            let strength = &STRENGTH[k.contract][card_suit(t[0])];
            let best = (0..NUM_SEATS).max_by_key(|&i| strength[t[i]]).unwrap_or(0);
            let winner = (leader + best) & 3;
            pts[winner & 1] += t.iter().map(|&x| values[x]).sum::<i32>();
            leader = winner;
            to_play = winner;
            t.clear();
        } else {
            to_play = (to_play + 1) & 3;
        }
    }
    if hands[to_play] == 0 {
        // The trick just finished was the last one.
        pts[leader & 1] += k.last_trick_bonus;
        return (pts[0], pts[1]);
    }
    let (a, b) = play_out(&mut hands, to_play, k, rng);
    (pts[0] + a, pts[1] + b)
}

#[derive(Debug)]
pub struct ValueNet {
    pub h1: usize,
    pub h2: usize,
    pub w1: Vec<f32>,
    pub b1: Vec<f32>,
    pub w2: Vec<f32>,
    pub b2: Vec<f32>,
    pub w3: Vec<f32>,
    pub b3: Vec<f32>,
}

impl ValueNet {
    pub fn untrained() -> Self {
        ValueNet {
            h1: 0, h2: 0, w1: Vec::new(), b1: Vec::new(), w2: Vec::new(), b2: Vec::new(),
            w3: Vec::new(), b3: Vec::new(),
        }
    }

    pub fn trained(&self) -> bool {
        self.h1 > 0
            && self.h2 > 0
            && self.w1.len() == self.h1 * N_VALUE_FEATURES
            && self.b1.len() == self.h1
            && self.w2.len() == self.h2 * self.h1
            && self.b2.len() == self.h2
            && self.w3.len() == self.h2
            && self.b3.len() == 1
    }

    pub fn from_json(text: &str) -> Self {
        let n = ValueNet {
            h1: number(text, "h1").unwrap_or(0.0) as usize,
            h2: number(text, "h2").unwrap_or(0.0) as usize,
            w1: array(text, "w1"),
            b1: array(text, "b1"),
            w2: array(text, "w2"),
            b2: array(text, "b2"),
            w3: array(text, "w3"),
            b3: array(text, "b3"),
        };
        if n.trained() { n } else { ValueNet::untrained() }
    }

    /// Fraction of the remaining points the mover's team takes, in (0, 1).
    pub fn eval(&self, x: &[f32; N_VALUE_FEATURES]) -> f32 {
        if !self.trained() {
            return 0.5;
        }
        // Mostly zeros — one-hot planes — so the first layer walks the non-zeros.
        let mut nz = [0usize; N_VALUE_FEATURES];
        let mut n_nz = 0;
        for (i, &v) in x.iter().enumerate() {
            if v != 0.0 {
                nz[n_nz] = i;
                n_nz += 1;
            }
        }
        let mut h1 = vec![0.0f32; self.h1];
        for j in 0..self.h1 {
            let row = &self.w1[j * N_VALUE_FEATURES..(j + 1) * N_VALUE_FEATURES];
            let mut acc = self.b1[j];
            for &i in &nz[..n_nz] {
                acc += row[i] * x[i];
            }
            h1[j] = acc.max(0.0);
        }
        let mut z = self.b3[0];
        for j in 0..self.h2 {
            let row = &self.w2[j * self.h1..(j + 1) * self.h1];
            let mut acc = self.b2[j];
            for i in 0..self.h1 {
                acc += row[i] * h1[i];
            }
            z += self.w3[j] * acc.max(0.0);
        }
        1.0 / (1.0 + (-z).exp())
    }
}

/// Native builds carry the trained network; the browser build does not use it.
#[cfg(not(feature = "wasm"))]
const NET_JSON: &str = include_str!("../../krass_jass/data/value_net.json");
#[cfg(feature = "wasm")]
const NET_JSON: &str = "{}";

pub fn net() -> &'static ValueNet {
    use std::sync::OnceLock;
    static CELL: OnceLock<ValueNet> = OnceLock::new();
    CELL.get_or_init(|| ValueNet::from_json(NET_JSON))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_untrained_net_says_half() {
        let x = [0.0f32; N_VALUE_FEATURES];
        assert_eq!(ValueNet::untrained().eval(&x), 0.5);
    }

    #[test]
    fn features_are_relative_to_the_seat_to_move() {
        // Seat 1 led card 9, seat 2 is to move.
        let mut hands = [0u64; NUM_SEATS];
        hands[2] = 1u64 << 3;
        hands[3] = 1u64 << 4;
        hands[0] = 1u64 << 5;
        hands[1] = 1u64 << 6;
        let trick = [9usize];
        let mut x = [0.0f32; N_VALUE_FEATURES];
        features(&hands, &trick, 1, 0, &mut x);
        assert_eq!(x[HANDS + 3], 1.0, "the mover's own hand comes first");
        assert_eq!(x[HANDS + NUM_CARDS + 4], 1.0, "then the seat to its left");
        assert_eq!(x[TABLE + 2 * NUM_CARDS + 9], 1.0, "seat 1 is three places left of seat 2");
        assert_eq!(x[CONTRACT], 1.0);
    }

    #[test]
    fn a_random_completion_hands_out_every_remaining_point() {
        let k = Kernel::new(1, true, true, 5, 0);
        let mut rng = Rng::new(7);
        let hands = crate::deal::deal(11, 0);
        let mut h = [0u64; NUM_SEATS];
        h.copy_from_slice(&hands[..4]);
        let total = remaining_points(&h, &[], &k);
        for _ in 0..50 {
            let (a, b) = random_remaining(h, &[], 0, &k, &mut rng);
            assert_eq!(a + b, total);
        }
    }
}
