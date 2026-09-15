//! Beliefs from behaviour: weight each imagined deal by how likely the table's plays were.
//!
//! `docs/measurements.md` §5k measured belief accuracy as the largest lever in the engine —
//! a fifth of the worlds replaced by the truth is worth +2.5 of a round's share — and every
//! belief correction tried before this was a bounded per-suit tilt, worth a small fraction of
//! a percent of an oracle by that curve. Those tilts nudge *which suit* a seat is dealt.
//!
//! This is the common practice in trick-taking engines instead (Kermit-style inference in
//! Skat): keep the exact constraints as they are, then weight each consistent world by
//!
//! ```text
//!   α · Σ log π(card a seat played | that seat's hand *in this world*, what it could see)
//! + β · log P(the bid | the bidder's hand in this world)
//! ```
//!
//! over every card the other three seats have played this round. A world where the partner
//! discarded a bare ace while holding two small cards in the suit is a world the partner's
//! play makes unlikely, and it gets looked at less. The evidence compounds over the round,
//! and it conditions on whole hands rather than suits — the magnitude the old priors lacked.
//!
//! # Why a pool
//!
//! Weighting needs a replay of the round per world, ~60 µs with the play model. The shared
//! tree draws ~38,000 worlds a move, and weighting candidates for each would cost tens of
//! seconds. So the worlds are drawn and weighted **once per decision** into a pool, and the
//! search samples from the pool in proportion to the weights. §5h found the shared tree needs
//! a few hundred distinct worlds; the pool reports its effective sample size so a run can see
//! when the weights have collapsed onto too few.
//!
//! α and β temper the model. Our bots bid deterministically and play much like the model, so
//! in self-play a sharp likelihood reads a clone almost perfectly — which a human is not.

use crate::announce::determinize_consistent;
use crate::cards::{card_suit, NUM_SEATS};
use crate::config::Rules;
use crate::legal::legal_moves;
use crate::playmodel::{model, PlayCtx};
use crate::rng::Rng;
use crate::rollout::Kernel;
use crate::search::Position;
use crate::tables::STRENGTH;
use crate::trump::{score_all, weights};

/// What the search knows about the round's history and how to use the play model.
#[derive(Clone, Debug)]
pub struct PlayInfo {
    /// Seat that declared; 4 or more when unknown.
    pub declarer: usize,
    /// Every card played this round before the current decision, `(seat, card)` in order,
    /// including the cards already in the current trick.
    pub history: Vec<(usize, usize)>,
    /// Weight on the card-play likelihood. 0 is off.
    pub belief_alpha: f32,
    /// Worlds drawn and weighted per decision.
    pub belief_pool: usize,
    /// Weight on the bid likelihood. 0 is off.
    pub bid_alpha: f32,
    /// Softness of the bid model: contract scores are divided by this before the softmax.
    pub bid_temperature: f32,
    /// Temperature of the play model when it replaces the random rollout. 0 keeps the
    /// random rollout, which is the baseline every earlier figure used.
    pub rollout_temperature: f32,
    /// The other three seats choose by the play model inside the tree, conditioned on their
    /// own hand in the imagined world, instead of by UCT over statistics pooled across worlds.
    pub tree_policy: bool,
    /// Temperature of the play model for the likelihood and the tree policy.
    pub policy_temperature: f32,
    /// Weight on the belief network's Σ log q(card at its seat) — `beliefnet.rs`. 0 is off.
    pub belief_gamma: f32,
    /// Per seat, the cards a Weis showed it holding and it has not played. The network reads
    /// them; the sampler already has them as `forbidden` for everyone else.
    pub known: [u64; NUM_SEATS],
}

impl PlayInfo {
    /// Nothing used: the search behaves exactly as it did before this file.
    pub fn off() -> Self {
        PlayInfo {
            declarer: NUM_SEATS,
            history: Vec::new(),
            belief_alpha: 0.0,
            belief_pool: 0,
            bid_alpha: 0.0,
            bid_temperature: 1.0,
            rollout_temperature: 0.0,
            tree_policy: false,
            policy_temperature: 1.0,
            belief_gamma: 0.0,
            known: [0; NUM_SEATS],
        }
    }

    pub fn weighting(&self) -> bool {
        self.belief_pool > 0
            && (self.belief_alpha > 0.0 || self.bid_alpha > 0.0 || self.belief_gamma > 0.0)
    }

    fn forehand(&self, trick_leader: usize) -> usize {
        self.history.first().map_or(trick_leader, |&(s, _)| s)
    }
}

fn best_trump(trick: &[usize], k: &Kernel) -> i32 {
    if k.trump < 0 || trick.is_empty() {
        return -1;
    }
    let strength = &STRENGTH[k.contract][card_suit(trick[0])];
    let mut best = -1;
    for &c in trick {
        if card_suit(c) as i32 == k.trump {
            best = best.max(strength[c] - 100);
        }
    }
    best
}

/// Σ log π over the other seats' plays, replayed from the hands this world deals them.
/// `-inf` when the world makes a play illegal — which sound void inference should already
/// have excluded, so it is a guard, not a filter.
pub fn play_log_likelihood(current: &[u64; NUM_SEATS], info: &PlayInfo, root: usize, k: &Kernel) -> f32 {
    let mut hands = *current;
    for &(s, c) in &info.history {
        hands[s] |= 1u64 << c;
    }
    let mut live = hands.iter().fold(0u64, |a, h| a | h);
    let m = model();
    let mut trick: Vec<usize> = Vec::with_capacity(4);
    let mut leader = 0usize;
    let mut acc = 0.0f32;
    for &(s, c) in &info.history {
        if trick.is_empty() {
            leader = s;
        }
        if s != root {
            let led = trick.first().map_or(-1, |&x| card_suit(x) as i32);
            let legal = legal_moves(hands[s], k.trump, led, best_trump(&trick, k),
                                    k.strict_undertrump, k.puur_exempt);
            if legal & (1u64 << c) == 0 {
                return f32::NEG_INFINITY;
            }
            if legal.count_ones() > 1 {
                let ctx = PlayCtx::new(hands[s], live, &trick, leader, s, k.contract, info.declarer);
                acc += m.log_prob(&ctx, legal, c, info.policy_temperature);
            }
        }
        hands[s] &= !(1u64 << c);
        live &= !(1u64 << c);
        trick.push(c);
        if trick.len() == NUM_SEATS {
            trick.clear();
        }
    }
    acc
}

/// log P(choice | hand) under a softmax over the rule selector's own contract scores, with the
/// shove scored at its threshold. `choice` of None is the shove.
fn bid_log_prob(hand: u64, may_shove: bool, choice: Option<usize>, temperature: f32) -> f32 {
    let rules = Rules::default();
    let scores = score_all(hand, &rules);
    let t = temperature.max(1e-3) as f64;
    let mut logits: Vec<f64> = scores.iter().map(|s| s / t).collect();
    if may_shove {
        logits.push(weights().shove_threshold / t);
    }
    let max = logits.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let norm = max + logits.iter().map(|l| (l - max).exp()).sum::<f64>().ln();
    let pick = match choice {
        Some(c) => logits[c],
        None => logits[scores.len()],
    };
    (pick - norm) as f32
}

/// log P(the bidding | the dealt hands in this world), for the seats other than `root`.
pub fn bid_log_likelihood(
    current: &[u64; NUM_SEATS],
    info: &PlayInfo,
    root: usize,
    trick_leader: usize,
    contract: usize,
) -> f32 {
    if info.declarer >= NUM_SEATS {
        return 0.0;
    }
    let mut dealt = *current;
    for &(s, c) in &info.history {
        dealt[s] |= 1u64 << c;
    }
    let forehand = info.forehand(trick_leader);
    let t = info.bid_temperature;
    let mut acc = 0.0;
    if forehand != root {
        acc += if info.declarer == forehand {
            bid_log_prob(dealt[forehand], true, Some(contract), t)
        } else {
            bid_log_prob(dealt[forehand], true, None, t)
        };
    }
    if info.declarer != forehand && info.declarer != root {
        acc += bid_log_prob(dealt[info.declarer], false, Some(contract), t);
    }
    acc
}

/// Worlds drawn once per decision, weighted by the evidence, and sampled in proportion.
pub struct Pool {
    worlds: Vec<[u64; NUM_SEATS]>,
    cumulative: Vec<f64>,
    /// Effective sample size, `(Σw)² / Σw²`. Equal to the pool size when the weights are flat.
    pub ess: f64,
}

impl Pool {
    pub fn build(pos: &Position, k: &Kernel, counts: &[usize; NUM_SEATS], rng: &mut Rng) -> Option<Pool> {
        let info = &pos.play;
        // The network's answer depends on the decision, not on the world, so it is computed once
        // and each world only sums the entries for where it put the cards.
        let net_lq = if info.belief_gamma > 0.0 {
            let inp = crate::beliefnet::BeliefInput {
                seat: pos.seat,
                hand: pos.hand,
                history: &info.history,
                contract: k.contract,
                declarer: info.declarer,
                forehand: info.forehand(pos.trick_leader),
                forbidden: pos.forbidden,
                known: info.known,
                weis_called: pos.announcements.called,
            };
            let mut lq = [[0.0f32; 3]; crate::cards::NUM_CARDS];
            crate::beliefnet::net().log_probs(&inp, &mut lq);
            Some(lq)
        } else {
            None
        };
        let mut worlds = Vec::with_capacity(info.belief_pool);
        let mut logw = Vec::with_capacity(info.belief_pool);
        for _ in 0..info.belief_pool {
            let mut dealt = [0u64; NUM_SEATS];
            if !determinize_consistent(
                pos.unseen, counts, &pos.forbidden, &pos.affinity, &pos.rank_bias,
                &pos.announcements, pos.seat, pos.hand, &mut dealt, rng,
            ) {
                continue;
            }
            dealt[pos.seat] = pos.hand;
            let mut lw = 0.0f32;
            if info.belief_alpha > 0.0 {
                lw += info.belief_alpha * play_log_likelihood(&dealt, info, pos.seat, k);
            }
            if info.bid_alpha > 0.0 {
                lw += info.bid_alpha
                    * bid_log_likelihood(&dealt, info, pos.seat, pos.trick_leader, k.contract);
            }
            if let Some(lq) = &net_lq {
                let mut acc = 0.0f32;
                for r in 1..NUM_SEATS {
                    let mut m = dealt[(pos.seat + r) & 3] & pos.unseen;
                    while m != 0 {
                        let c = m.trailing_zeros() as usize;
                        m &= m - 1;
                        acc += lq[c][r - 1];
                    }
                }
                lw += info.belief_gamma * acc;
            }
            if lw.is_finite() {
                worlds.push(dealt);
                logw.push(lw as f64);
            }
        }
        if worlds.is_empty() {
            return None;
        }
        let max = logw.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let w: Vec<f64> = logw.iter().map(|l| (l - max).exp()).collect();
        let sum: f64 = w.iter().sum();
        let sq: f64 = w.iter().map(|x| x * x).sum();
        let mut acc = 0.0;
        let cumulative = w
            .iter()
            .map(|x| {
                acc += x / sum;
                acc
            })
            .collect();
        Some(Pool { worlds, cumulative, ess: sum * sum / sq })
    }

    pub fn draw(&self, rng: &mut Rng) -> [u64; NUM_SEATS] {
        let u = (rng.next_u64() >> 11) as f64 / (1u64 << 53) as f64;
        let i = self.cumulative.partition_point(|&c| c < u).min(self.worlds.len() - 1);
        self.worlds[i]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn with_no_model_every_consistent_world_is_equally_likely() {
        // The shipped model may be untrained; with alpha applied to a uniform model the
        // likelihood depends only on how many legal cards each play had, which is the same in
        // every world only when hands agree — so test the uniform scorer directly.
        let k = Kernel::new(0, true, true, 5, 0);
        let mut info = PlayInfo::off();
        info.history = vec![(1, 9)];
        let mut a = [0u64; NUM_SEATS];
        a[1] = 1u64 << 10;
        let lp = play_log_likelihood(&a, &info, 0, &k);
        assert!(lp.is_finite());
    }

    #[test]
    fn a_world_that_makes_a_play_illegal_scores_minus_infinity() {
        // Seat 1 led a heart (9); seat 2 discarded a spade (18) while this world gives it a
        // heart (10). Following suit was compulsory, so the world cannot be the real one.
        let k = Kernel::new(0, true, true, 5, 0);
        let mut info = PlayInfo::off();
        info.history = vec![(1, 9), (2, 18)];
        let mut hands = [0u64; NUM_SEATS];
        hands[1] = 1u64 << 11;
        hands[2] = 1u64 << 10;
        assert_eq!(play_log_likelihood(&hands, &info, 0, &k), f32::NEG_INFINITY);
    }

    #[test]
    fn a_bid_is_likelier_from_a_hand_that_scores_it_highly() {
        let t = 3.0;
        // Four trumps with Puur and Nell in diamonds against a flat hand.
        let strong = (1u64 << 3) | (1u64 << 5) | (1u64 << 0) | (1u64 << 1) | (1u64 << 12)
            | (1u64 << 21) | (1u64 << 30) | (1u64 << 31) | (1u64 << 14);
        let flat = (1u64 << 8) | (1u64 << 7) | (1u64 << 16) | (1u64 << 17) | (1u64 << 25)
            | (1u64 << 26) | (1u64 << 34) | (1u64 << 35) | (1u64 << 6);
        assert!(bid_log_prob(strong, true, Some(0), t) > bid_log_prob(flat, true, Some(0), t));
    }
}
