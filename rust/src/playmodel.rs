//! A model of how a seat plays, from that seat's own view — π(card | observation).
//!
//! `docs/measurements.md` §5k put belief accuracy as the largest lever in the file, and every
//! belief correction tried so far was a bounded per-suit tilt worth a fraction of a percent of
//! an oracle. The common practice in trick-taking engines (Kermit and its successors in Skat)
//! is stronger: weight each imagined deal by how likely the table's actual plays would have
//! been, *holding that deal*. That needs a model of play conditioned on a seat's own hand —
//! this one — and the same model is what a rollout needs to stop playing at random.
//!
//! # Only what the seat could see
//!
//! Every input is the seat's own hand, the set of cards still unplayed (public), the trick on
//! the table, the contract and who declared. Nothing reads another hand. Inside an imagined
//! world that is the property that makes the likelihood meaningful: it asks "would *this* hand
//! have played that card", not "would a player who could see everything".
//!
//! # The model
//!
//! Features of the (state, card) pair, scored by one shared function: a linear term plus a
//! small ReLU layer for the conjunctions a linear model cannot represent (§5j's first attempt
//! failed on exactly that). A softmax over the legal cards makes it a distribution.
//!
//! The weights are compiled in from `krass_jass/data/play_policy.json`, one file for native and
//! wasm, the same arrangement as the trump weights. An empty file means an untrained model,
//! which is uniform — every caller then behaves exactly as it did without one.

use crate::cards::{card_suit, NUM_CARDS, NUM_RANKS, NUM_SEATS, SUIT_MASK};
use crate::leafeval::top_live;
use crate::rng::Rng;
use crate::tables::{CARD_VALUES, STRENGTH};

pub const N_PLAY_FEATURES: usize = 36;

/// Everything about a decision that does not depend on which card is being scored.
pub struct PlayCtx<'a> {
    pub hand: u64,
    /// Cards in anybody's hand — not yet played and not on the table.
    pub live: u64,
    pub trick: &'a [usize],
    pub seat: usize,
    pub contract: usize,
    trump: i32,
    led: i32,
    best_on_table: i32,
    partner_winning: bool,
    opponent_winning: bool,
    table_points: f32,
    my_trumps: f32,
    others_trumps: f32,
    declarer_team: bool,
    tricks_done: f32,
}

impl<'a> PlayCtx<'a> {
    /// `declarer` of 4 or more means unknown.
    pub fn new(
        hand: u64,
        live: u64,
        trick: &'a [usize],
        trick_leader: usize,
        seat: usize,
        contract: usize,
        declarer: usize,
    ) -> Self {
        let trump = if contract < 4 { contract as i32 } else { -1 };
        let led = trick.first().map_or(-1, |&c| card_suit(c) as i32);
        let mut best_on_table = -1;
        let mut partner_winning = false;
        let mut opponent_winning = false;
        let mut table_points = 0.0;
        if led >= 0 {
            let st = &STRENGTH[contract][led as usize];
            let mut best = 0usize;
            for (i, &c) in trick.iter().enumerate() {
                table_points += CARD_VALUES[contract][c] as f32;
                if st[c] > st[trick[best]] {
                    best = i;
                }
            }
            best_on_table = st[trick[best]];
            let winner = (trick_leader + best) & 3;
            partner_winning = (winner & 1) == (seat & 1);
            opponent_winning = !partner_winning;
        }
        let others = live & !hand;
        let (my_trumps, others_trumps) = if trump >= 0 {
            let m = SUIT_MASK[trump as usize];
            ((hand & m).count_ones() as f32, (others & m).count_ones() as f32)
        } else {
            (0.0, 0.0)
        };
        // Cards out of play: the ones already played, which is everything not live and not on
        // the table. Four per trick.
        let gone = NUM_CARDS as u32 - live.count_ones() - trick.len() as u32;
        PlayCtx {
            hand,
            live,
            trick,
            seat,
            contract,
            trump,
            led,
            best_on_table,
            partner_winning,
            opponent_winning,
            table_points,
            my_trumps,
            others_trumps,
            declarer_team: declarer < NUM_SEATS && (declarer & 1) == (seat & 1),
            tricks_done: (gone / 4) as f32,
        }
    }

    pub fn features(&self, card: usize, out: &mut [f32; N_PLAY_FEATURES]) {
        let suit = card_suit(card);
        let contract = self.contract;
        let in_suit = &STRENGTH[contract][suit];
        let is_trump = self.trump >= 0 && suit == self.trump as usize;
        let value = CARD_VALUES[contract][card] as f32 / 20.0;
        let is_boss = top_live(self.live, suit, contract) == 1u64 << card;
        let others = self.live & !self.hand;

        let mut beaters = 0u32;
        let mut rank = 0u32;
        let mut rest = others & SUIT_MASK[suit];
        while rest != 0 {
            let c = rest.trailing_zeros() as usize;
            rest &= rest - 1;
            if in_suit[c] > in_suit[card] {
                beaters += 1;
            }
        }
        for c in suit * NUM_RANKS..(suit + 1) * NUM_RANKS {
            if in_suit[c] < in_suit[card] {
                rank += 1;
            }
        }
        let mine = self.hand & SUIT_MASK[suit];
        let mut lowest = true;
        let mut highest = true;
        let mut rest = mine & !(1u64 << card);
        while rest != 0 {
            let c = rest.trailing_zeros() as usize;
            rest &= rest - 1;
            if in_suit[c] < in_suit[card] {
                lowest = false;
            } else {
                highest = false;
            }
        }

        let leading = self.trick.is_empty();
        let b = |x: bool| if x { 1.0f32 } else { 0.0 };
        let takes = !leading && STRENGTH[contract][self.led as usize][card] > self.best_on_table;
        let follows = !leading && suit as i32 == self.led;
        let partner = b(self.partner_winning);
        let opponent = b(self.opponent_winning);

        out[0] = 1.0;
        out[1] = b(is_trump);
        out[2] = value;
        out[3] = b(is_boss);
        out[4] = beaters as f32 / 9.0;
        out[5] = rank as f32 / 8.0;
        out[6] = mine.count_ones() as f32 / 9.0;
        out[7] = b(leading);
        out[8] = self.trick.len() as f32 / 3.0;
        out[9] = b(follows);
        out[10] = b(!leading && !follows && !is_trump);
        out[11] = partner;
        out[12] = opponent;
        out[13] = b(takes);
        out[14] = b(takes && self.trick.len() == 3);
        out[15] = b(takes && beaters == 0);
        out[16] = self.table_points / 40.0;
        out[17] = out[16] * out[13];
        out[18] = value * partner;
        out[19] = value * opponent * (1.0 - out[13]);
        out[20] = out[1] * partner;
        out[21] = out[1] * opponent;
        out[22] = out[1] * out[7] * self.my_trumps / 9.0;
        out[23] = out[3] * out[7];
        out[24] = b(lowest);
        out[25] = b(highest);
        out[26] = out[1] * out[7] * self.others_trumps / 9.0;
        out[27] = b(self.declarer_team);
        out[28] = out[27] * out[7] * out[1];
        out[29] = b(is_trump && card % NUM_RANKS == 3); // Puur
        out[30] = b(is_trump && card % NUM_RANKS == 5); // Nell
        out[31] = self.tricks_done / 8.0;
        out[32] = out[7] * (others & SUIT_MASK[suit]).count_ones() as f32 / 9.0;
        out[33] = value * out[7] * (1.0 - out[3]);
        out[34] = b(self.trump < 0) * out[7] * out[3];
        out[35] = b(!leading && !follows && is_trump); // ruffing in
    }
}

#[derive(Debug)]
pub struct PlayModel {
    pub hidden: usize,
    pub w1: Vec<f32>,
    pub b1: Vec<f32>,
    pub w2: Vec<f32>,
    pub skip: Vec<f32>,
}

impl PlayModel {
    pub fn uniform() -> Self {
        PlayModel { hidden: 0, w1: Vec::new(), b1: Vec::new(), w2: Vec::new(), skip: Vec::new() }
    }

    /// A model is trained when its shapes add up; anything else scores every card the same.
    pub fn trained(&self) -> bool {
        self.skip.len() == N_PLAY_FEATURES
            && self.w1.len() == self.hidden * N_PLAY_FEATURES
            && self.b1.len() == self.hidden
            && self.w2.len() == self.hidden
    }

    pub fn from_json(text: &str) -> Self {
        let m = PlayModel {
            hidden: number(text, "n_hidden").unwrap_or(0.0) as usize,
            w1: array(text, "w1"),
            b1: array(text, "b1"),
            w2: array(text, "w2"),
            skip: array(text, "skip"),
        };
        if m.trained() { m } else { PlayModel::uniform() }
    }

    #[inline]
    pub fn logit(&self, x: &[f32; N_PLAY_FEATURES]) -> f32 {
        let mut acc = 0.0f32;
        for i in 0..N_PLAY_FEATURES {
            acc += self.skip[i] * x[i];
        }
        for j in 0..self.hidden {
            let row = &self.w1[j * N_PLAY_FEATURES..(j + 1) * N_PLAY_FEATURES];
            let mut h = self.b1[j];
            for i in 0..N_PLAY_FEATURES {
                h += row[i] * x[i];
            }
            if h > 0.0 {
                acc += self.w2[j] * h;
            }
        }
        acc
    }

    /// Logits over the legal cards, divided by `temperature`. Returns the log of the
    /// normaliser, so a caller can turn any one logit into a log-probability.
    pub fn logits(&self, ctx: &PlayCtx, legal: u64, temperature: f32, out: &mut [f32; NUM_CARDS]) -> f32 {
        let inv = 1.0 / temperature.max(1e-3);
        let mut feats = [0.0f32; N_PLAY_FEATURES];
        let mut max = f32::NEG_INFINITY;
        let mut rest = legal;
        while rest != 0 {
            let c = rest.trailing_zeros() as usize;
            rest &= rest - 1;
            out[c] = if self.trained() {
                ctx.features(c, &mut feats);
                self.logit(&feats) * inv
            } else {
                0.0
            };
            max = max.max(out[c]);
        }
        let mut sum = 0.0f32;
        let mut rest = legal;
        while rest != 0 {
            let c = rest.trailing_zeros() as usize;
            rest &= rest - 1;
            sum += (out[c] - max).exp();
        }
        max + sum.ln()
    }

    /// log π(card) among `legal`. `card` must be legal.
    pub fn log_prob(&self, ctx: &PlayCtx, legal: u64, card: usize, temperature: f32) -> f32 {
        if !self.trained() {
            return -(legal.count_ones() as f32).ln();
        }
        let mut l = [0.0f32; NUM_CARDS];
        let norm = self.logits(ctx, legal, temperature, &mut l);
        l[card] - norm
    }

    /// Draw a card from π.
    pub fn sample(&self, ctx: &PlayCtx, legal: u64, temperature: f32, rng: &mut Rng) -> usize {
        if !self.trained() || legal.count_ones() == 1 {
            return crate::rollout::pick_random(legal, rng);
        }
        let mut l = [0.0f32; NUM_CARDS];
        let norm = self.logits(ctx, legal, temperature, &mut l);
        let u = (rng.next_u64() >> 40) as f32 / (1u64 << 24) as f32;
        let mut acc = 0.0f32;
        let mut rest = legal;
        let mut last = 0;
        while rest != 0 {
            let c = rest.trailing_zeros() as usize;
            rest &= rest - 1;
            acc += (l[c] - norm).exp();
            last = c;
            if u < acc {
                return c;
            }
        }
        last
    }
}

const MODEL_JSON: &str = include_str!("../../krass_jass/data/play_policy.json");

/// The shipped model, parsed once.
pub fn model() -> &'static PlayModel {
    use std::sync::OnceLock;
    static CELL: OnceLock<PlayModel> = OnceLock::new();
    CELL.get_or_init(|| PlayModel::from_json(MODEL_JSON))
}

pub(crate) fn number(text: &str, key: &str) -> Option<f64> {
    let at = text.find(&format!("\"{key}\""))?;
    let rest = &text[at + key.len() + 2..];
    let tail = &rest[rest.find(':')? + 1..];
    let tail = tail.trim_start();
    let end = tail
        .find(|c: char| !(c == '-' || c == '.' || c == 'e' || c == 'E' || c == '+' || c.is_ascii_digit()))
        .unwrap_or(tail.len());
    tail[..end].parse().ok()
}

pub(crate) fn array(text: &str, key: &str) -> Vec<f32> {
    let Some(at) = text.find(&format!("\"{key}\"")) else { return Vec::new() };
    let Some(open) = text[at..].find('[') else { return Vec::new() };
    let start = at + open + 1;
    let Some(close) = text[start..].find(']') else { return Vec::new() };
    text[start..start + close]
        .split(',')
        .filter_map(|s| {
            let s = s.trim();
            if s.is_empty() { None } else { s.parse().ok() }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_untrained_model_is_uniform() {
        let m = PlayModel::uniform();
        let trick: [usize; 0] = [];
        let ctx = PlayCtx::new(0b111, (1u64 << 36) - 1, &trick, 0, 0, 0, 0);
        let lp = m.log_prob(&ctx, 0b111, 1, 1.0);
        assert!((lp - -(3.0f32).ln()).abs() < 1e-6);
    }

    #[test]
    fn probabilities_sum_to_one() {
        let text = format!(
            "{{\"n_hidden\": 2, \"w1\": [{}], \"b1\": [0.1, -0.2], \"w2\": [0.5, -0.3], \"skip\": [{}]}}",
            (0..2 * N_PLAY_FEATURES).map(|i| format!("{}", (i as f32 * 0.37).sin())).collect::<Vec<_>>().join(","),
            (0..N_PLAY_FEATURES).map(|i| format!("{}", (i as f32 * 0.11).cos())).collect::<Vec<_>>().join(","),
        );
        let m = PlayModel::from_json(&text);
        assert!(m.trained());
        let hand = 0b1_0110_1101u64 | (1u64 << 20);
        let trick = [9usize];
        let ctx = PlayCtx::new(hand, (1u64 << 36) - 1 & !(1u64 << 9), &trick, 1, 2, 1, 3);
        let legal = hand;
        let total: f32 = crate::cards::card_list(legal)
            .into_iter()
            .map(|c| m.log_prob(&ctx, legal, c, 1.0).exp())
            .sum();
        assert!((total - 1.0).abs() < 1e-4, "{total}");
    }
}
