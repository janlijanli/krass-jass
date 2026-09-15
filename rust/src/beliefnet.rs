//! Where the hidden cards are, learned from the truth — P(card at seat | what this seat saw).
//!
//! `belief.rs` reads the table *through* a model of play: it weights a world by how likely the
//! other seats' cards were, holding that world. That is Bayesian inversion, and it is exactly
//! as good as the play model and the pool it weights. This is the other common practice — the
//! "card-distribution head" of the Jass networks and the belief networks of later card-game
//! agents: train directly on self-play, where the true deal is always known, to predict for
//! every unseen card which of the other three seats holds it.
//!
//! No cheating agent is needed for it. Every simulated round already carries its answer.
//!
//! # Only what the seat could see
//!
//! The inputs are the seat's own hand and public information — who played which card and how
//! (led, followed, discarded, ruffed), the proven voids, the cards a Weis showed, the value each
//! seat called, the bid. The function takes nothing else, so it cannot read a hidden hand even
//! by accident. Everything is relative to the observing seat (left, partner, right), so one
//! network serves all four.
//!
//! The exact constraints stay exact: a card a seat provably cannot hold is masked out of the
//! softmax rather than learned, and the search keeps rejecting worlds that contradict a call.
//! The network only has to learn what those rules leave open.
//!
//! Weights compile in from `krass_jass/data/belief_net.json`. An untrained file is uniform over
//! the seats each card is still allowed at.

use crate::cards::{card_suit, FULL_DECK, NUM_CARDS, NUM_SEATS};
use crate::playmodel::{array, number};

pub const N_BELIEF_FEATURES: usize = 865;

const PLAYED: usize = 36;
const LED: usize = 180;
const DISCARDED: usize = 324;
const RUFFED: usize = 468;
const FORBIDDEN: usize = 612;
const KNOWN: usize = 720;
const CONTRACT: usize = 828;
const DECLARER: usize = 834;
const FOREHAND: usize = 838;
const SHOVED: usize = 842;
const WEIS: usize = 843;
const COUNTS: usize = 861;
const TRICKS: usize = 864;

/// What one seat knows at one decision.
pub struct BeliefInput<'a> {
    pub seat: usize,
    pub hand: u64,
    /// Every card played this round, `(seat, card)` in order, current trick included.
    pub history: &'a [(usize, usize)],
    pub contract: usize,
    /// 4 or more when unknown.
    pub declarer: usize,
    pub forehand: usize,
    /// Per seat, cards it provably cannot hold — voids and cards a Weis showed elsewhere.
    pub forbidden: [u64; NUM_SEATS],
    /// Per seat, cards a Weis showed it holding and it has not played yet.
    pub known: [u64; NUM_SEATS],
    /// Per seat, the Weis value it called; -1 when not (yet) known.
    pub weis_called: [i32; NUM_SEATS],
}

/// Position of `other` relative to `seat`: 0 self, 1 left, 2 partner, 3 right.
#[inline]
fn rel(seat: usize, other: usize) -> usize {
    (other + NUM_SEATS - seat) & 3
}

fn weis_bucket(points: i32) -> usize {
    match points {
        p if p < 0 => 0,
        0 => 1,
        1..=20 => 2,
        21..=50 => 3,
        51..=100 => 4,
        _ => 5,
    }
}

fn set_bits(out: &mut [f32], base: usize, mask: u64) {
    let mut m = mask;
    while m != 0 {
        let c = m.trailing_zeros() as usize;
        m &= m - 1;
        out[base + c] = 1.0;
    }
}

impl<'a> BeliefInput<'a> {
    pub fn played(&self) -> u64 {
        self.history.iter().fold(0u64, |a, &(_, c)| a | 1u64 << c)
    }

    pub fn unseen(&self) -> u64 {
        FULL_DECK & !self.hand & !self.played()
    }

    /// Whether card `c` may lie with the seat `r` places to the left (1..=3).
    pub fn allowed(&self, c: usize, r: usize) -> bool {
        let other = (self.seat + r) & 3;
        self.unseen() >> c & 1 == 1 && self.forbidden[other] >> c & 1 == 0
    }

    pub fn features(&self, out: &mut [f32; N_BELIEF_FEATURES]) {
        out.fill(0.0);
        set_bits(out, 0, self.hand);
        let trump = if self.contract < 4 { self.contract as i32 } else { -1 };
        let mut played_count = [0usize; NUM_SEATS];
        for (i, &(s, c)) in self.history.iter().enumerate() {
            let r = rel(self.seat, s & 3);
            out[PLAYED + r * NUM_CARDS + c] = 1.0;
            played_count[s & 3] += 1;
            let pos = i % NUM_SEATS;
            if pos == 0 {
                out[LED + r * NUM_CARDS + c] = 1.0;
            } else {
                let led = card_suit(self.history[i - pos].1);
                let suit = card_suit(c);
                if suit != led {
                    let plane = if trump >= 0 && suit == trump as usize { RUFFED } else { DISCARDED };
                    out[plane + r * NUM_CARDS + c] = 1.0;
                }
            }
        }
        for r in 1..NUM_SEATS {
            let other = (self.seat + r) & 3;
            set_bits(out, FORBIDDEN + (r - 1) * NUM_CARDS, self.forbidden[other]);
            set_bits(out, KNOWN + (r - 1) * NUM_CARDS, self.known[other]);
            out[WEIS + (r - 1) * 6 + weis_bucket(self.weis_called[other])] = 1.0;
            out[COUNTS + r - 1] = (9usize.saturating_sub(played_count[other])) as f32 / 9.0;
        }
        out[CONTRACT + self.contract.min(5)] = 1.0;
        if self.declarer < NUM_SEATS {
            out[DECLARER + rel(self.seat, self.declarer)] = 1.0;
        }
        if self.forehand < NUM_SEATS {
            out[FOREHAND + rel(self.seat, self.forehand)] = 1.0;
        }
        if self.declarer < NUM_SEATS && self.forehand < NUM_SEATS && self.declarer != self.forehand {
            out[SHOVED] = 1.0;
        }
        out[TRICKS] = (self.history.len() / NUM_SEATS) as f32 / 8.0;
    }
}

pub struct BeliefNet {
    pub h1: usize,
    pub h2: usize,
    pub w1: Vec<f32>,
    pub b1: Vec<f32>,
    pub w2: Vec<f32>,
    pub b2: Vec<f32>,
    pub w3: Vec<f32>,
    pub b3: Vec<f32>,
}

impl BeliefNet {
    pub fn uniform() -> Self {
        BeliefNet {
            h1: 0, h2: 0, w1: Vec::new(), b1: Vec::new(), w2: Vec::new(), b2: Vec::new(),
            w3: Vec::new(), b3: Vec::new(),
        }
    }

    pub fn trained(&self) -> bool {
        self.h1 > 0
            && self.h2 > 0
            && self.w1.len() == self.h1 * N_BELIEF_FEATURES
            && self.b1.len() == self.h1
            && self.w2.len() == self.h2 * self.h1
            && self.b2.len() == self.h2
            && self.w3.len() == 3 * NUM_CARDS * self.h2
            && self.b3.len() == 3 * NUM_CARDS
    }

    pub fn from_json(text: &str) -> Self {
        let n = BeliefNet {
            h1: number(text, "h1").unwrap_or(0.0) as usize,
            h2: number(text, "h2").unwrap_or(0.0) as usize,
            w1: array(text, "w1"),
            b1: array(text, "b1"),
            w2: array(text, "w2"),
            b2: array(text, "b2"),
            w3: array(text, "w3"),
            b3: array(text, "b3"),
        };
        if n.trained() { n } else { BeliefNet::uniform() }
    }

    /// Raw logits, `3 × 36`: index `card * 3 + (r - 1)` for the seat `r` places to the left.
    fn logits(&self, x: &[f32; N_BELIEF_FEATURES]) -> Vec<f32> {
        // The input is mostly zeros — one-hot planes — so the first layer walks the non-zeros.
        let nz: Vec<usize> = (0..N_BELIEF_FEATURES).filter(|&i| x[i] != 0.0).collect();
        let mut h1 = vec![0.0f32; self.h1];
        for j in 0..self.h1 {
            let row = &self.w1[j * N_BELIEF_FEATURES..];
            let mut acc = self.b1[j];
            for &i in &nz {
                acc += row[i] * x[i];
            }
            h1[j] = acc.max(0.0);
        }
        let mut h2 = vec![0.0f32; self.h2];
        for j in 0..self.h2 {
            let row = &self.w2[j * self.h1..(j + 1) * self.h1];
            let mut acc = self.b2[j];
            for i in 0..self.h1 {
                acc += row[i] * h1[i];
            }
            h2[j] = acc.max(0.0);
        }
        let mut out = vec![0.0f32; 3 * NUM_CARDS];
        for k in 0..3 * NUM_CARDS {
            let row = &self.w3[k * self.h2..(k + 1) * self.h2];
            let mut acc = self.b3[k];
            for i in 0..self.h2 {
                acc += row[i] * h2[i];
            }
            out[k] = acc;
        }
        out
    }

    /// `out[card][r - 1]` = log P(card lies with the seat `r` places to the left). A seat the
    /// card is not allowed at is `-inf`; a card that is not hidden is `-inf` everywhere.
    pub fn log_probs(&self, inp: &BeliefInput, out: &mut [[f32; 3]; NUM_CARDS]) {
        let logits = if self.trained() {
            let mut x = [0.0f32; N_BELIEF_FEATURES];
            inp.features(&mut x);
            self.logits(&x)
        } else {
            vec![0.0f32; 3 * NUM_CARDS]
        };
        let unseen = inp.unseen();
        for c in 0..NUM_CARDS {
            out[c] = [f32::NEG_INFINITY; 3];
            if unseen >> c & 1 == 0 {
                continue;
            }
            let allowed: Vec<usize> = (1..NUM_SEATS).filter(|&r| inp.allowed(c, r)).collect();
            if allowed.is_empty() {
                // Constraints that leave a card nowhere are a bug upstream, not a belief; do not
                // let one card poison a whole world's weight.
                out[c] = [-(3.0f32).ln(); 3];
                continue;
            }
            let max = allowed.iter().map(|&r| logits[c * 3 + r - 1]).fold(f32::NEG_INFINITY, f32::max);
            let norm = max + allowed.iter().map(|&r| (logits[c * 3 + r - 1] - max).exp()).sum::<f32>().ln();
            for &r in &allowed {
                out[c][r - 1] = logits[c * 3 + r - 1] - norm;
            }
        }
    }
}

/// Native builds carry the trained network. The browser build does not use it — `belief_gamma` is
/// off there — and the weights would triple the wasm payload, so it gets the untrained stand-in.
#[cfg(not(feature = "wasm"))]
const NET_JSON: &str = include_str!("../../krass_jass/data/belief_net.json");
#[cfg(feature = "wasm")]
const NET_JSON: &str = "{}";

/// The shipped network, parsed once.
pub fn net() -> &'static BeliefNet {
    use std::sync::OnceLock;
    static CELL: OnceLock<BeliefNet> = OnceLock::new();
    CELL.get_or_init(|| BeliefNet::from_json(NET_JSON))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn input<'a>(history: &'a [(usize, usize)], forbidden: [u64; 4]) -> BeliefInput<'a> {
        BeliefInput {
            seat: 0,
            hand: 0x1FF, // all of the first suit
            history,
            contract: 1,
            declarer: 2,
            forehand: 1,
            forbidden,
            known: [0; 4],
            weis_called: [-1, 0, 20, -1],
        }
    }

    #[test]
    fn an_untrained_net_is_uniform_over_allowed_seats() {
        let hist = [(1usize, 9usize), (2, 10), (3, 18)];
        let mut forbidden = [0u64; 4];
        forbidden[3] = 1u64 << 11; // the right-hand seat cannot hold card 11
        let inp = input(&hist, forbidden);
        let mut lp = [[0.0f32; 3]; 36];
        BeliefNet::uniform().log_probs(&inp, &mut lp);
        assert!(lp[0].iter().all(|x| x.is_infinite()), "own card is not hidden");
        assert!(lp[9].iter().all(|x| x.is_infinite()), "played card is not hidden");
        assert!((lp[11][0] - -(2.0f32).ln()).abs() < 1e-6);
        assert!((lp[11][1] - -(2.0f32).ln()).abs() < 1e-6);
        assert!(lp[11][2].is_infinite(), "a forbidden seat gets no probability");
        assert!((lp[20][2] - -(3.0f32).ln()).abs() < 1e-6);
    }

    #[test]
    fn features_mark_leads_discards_and_ruffs_relative_to_the_observer() {
        // Hearts (suit 1) is trump. Left leads a heart, partner discards a spade, right ruffs a
        // club lead in the next trick.
        let hist = [(1usize, 9usize), (2, 18), (3, 10), (0, 11), (1, 27), (2, 28), (3, 12)];
        let inp = input(&hist, [0; 4]);
        let mut x = [0.0f32; N_BELIEF_FEATURES];
        inp.features(&mut x);
        assert_eq!(x[LED + NUM_CARDS + 9], 1.0, "left led card 9");
        assert_eq!(x[DISCARDED + 2 * NUM_CARDS + 18], 1.0, "partner discarded card 18");
        assert_eq!(x[RUFFED + 3 * NUM_CARDS + 12], 1.0, "right ruffed with a trump");
        assert_eq!(x[PLAYED..LED].iter().sum::<f32>(), hist.len() as f32);
        assert_eq!(x[SHOVED], 1.0, "declarer is not forehand");
        assert_eq!(x[WEIS + 6 + 2], 1.0, "partner called 20");
    }
}
