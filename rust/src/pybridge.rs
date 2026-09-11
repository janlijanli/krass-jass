//! PyO3 exports for the ported rules, so each one can be checked against the Python it
//! replaces.
//!
//! This is the whole safety argument for the port, and it is the same one that made the
//! search port safe: `tests/reference.py` was written from the rules text and imports
//! neither implementation, so the Python side is itself independently checked. Agreement
//! across all three is what says the port is right.

use pyo3::prelude::*;

use crate::awareness::trick_taker;
use crate::bidding::infer_from_bid;
use crate::convention;
use crate::leafeval::{features, N_FEATURES};
use crate::policy::{card_features, N_POLICY_FEATURES};
use crate::rollout::{pick_random, Kernel};
use crate::round::Round;
use crate::determinize::determinize;
use crate::objective::{reward, Stakes};
use crate::reading::infer_affinity;
use crate::rng::Rng;
use crate::search::Candidate;
use crate::config::Rules;
use crate::scoring::{claim_sequence, score_round, RoundScore};
use crate::trump::{select_trump, SHOVE};
use crate::voids::infer_forbidden;
use crate::weis::{find_weis, score_stoeck, score_weis, WeisKind};

/// Build a Rules from the fields a test cares about. Anything omitted keeps its default,
/// which is the same default `krass_jass/rules.py` documents.
#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature = (
    multipliers=None, weis_enabled=true, weis_large=false, weis_four_nines=true,
    weis_four_beats_sequence=true, stoeck_enabled=true, last_trick_bonus=5, match_bonus=100,
    strict_undertrump=true, puur_exempt=true, claim_order=None
))]
fn rules_dict(
    multipliers: Option<Vec<i32>>,
    weis_enabled: bool,
    weis_large: bool,
    weis_four_nines: bool,
    weis_four_beats_sequence: bool,
    stoeck_enabled: bool,
    last_trick_bonus: i32,
    match_bonus: i32,
    strict_undertrump: bool,
    puur_exempt: bool,
    claim_order: Option<Vec<u8>>,
) -> Vec<i32> {
    // Returned only so Python can round-trip a config; the real object is built below.
    let r = build_rules(
        multipliers, weis_enabled, weis_large, weis_four_nines, weis_four_beats_sequence,
        stoeck_enabled, last_trick_bonus, match_bonus, strict_undertrump, puur_exempt, claim_order,
    );
    r.multipliers.to_vec()
}

#[allow(clippy::too_many_arguments)]
fn build_rules(
    multipliers: Option<Vec<i32>>,
    weis_enabled: bool,
    weis_large: bool,
    weis_four_nines: bool,
    weis_four_beats_sequence: bool,
    stoeck_enabled: bool,
    last_trick_bonus: i32,
    match_bonus: i32,
    strict_undertrump: bool,
    puur_exempt: bool,
    claim_order: Option<Vec<u8>>,
) -> Rules {
    let mut rules = Rules {
        weis_enabled,
        weis_large,
        weis_four_nines,
        weis_four_beats_sequence,
        stoeck_enabled,
        last_trick_bonus,
        match_bonus,
        strict_undertrump,
        puur_exempt,
        ..Rules::default()
    };
    if let Some(m) = multipliers {
        for (i, v) in m.iter().take(6).enumerate() {
            rules.multipliers[i] = *v;
        }
    }
    if let Some(order) = claim_order {
        for (i, v) in order.iter().take(3).enumerate() {
            rules.claim_order[i] = *v;
        }
    }
    rules
}

/// `(kind, points, cards_mask, length, top_rank, suit)` per meld.
#[pyfunction]
#[pyo3(signature = (hand, trump=-1, weis_large=false, weis_four_nines=true, weis_four_beats_sequence=true))]
fn rs_find_weis(
    hand: u64,
    trump: i32,
    weis_large: bool,
    weis_four_nines: bool,
    weis_four_beats_sequence: bool,
) -> Vec<(String, i32, u64, usize, usize, i64)> {
    let rules = Rules {
        weis_large,
        weis_four_nines,
        weis_four_beats_sequence,
        ..Rules::default()
    };
    find_weis(hand, &rules, trump)
        .into_iter()
        .map(|m| {
            (
                match m.kind {
                    WeisKind::Sequence => "sequence".to_string(),
                    WeisKind::Four => "four".to_string(),
                },
                m.points,
                m.cards,
                m.length,
                m.top_rank,
                if m.suit == usize::MAX { -1 } else { m.suit as i64 },
            )
        })
        .collect()
}

#[pyfunction]
#[pyo3(signature = (hands, trump, forehand=0, weis_large=false, weis_four_nines=true, weis_four_beats_sequence=true))]
fn rs_score_weis(
    hands: Vec<u64>,
    trump: i32,
    forehand: usize,
    weis_large: bool,
    weis_four_nines: bool,
    weis_four_beats_sequence: bool,
) -> ((i32, i32), i32) {
    let mut h = [0u64; 4];
    h.copy_from_slice(&hands);
    let rules = Rules { weis_large, weis_four_nines, weis_four_beats_sequence, ..Rules::default() };
    let (points, winner) = score_weis(&h, trump, &rules, forehand);
    ((points[0], points[1]), winner)
}

#[pyfunction]
#[pyo3(signature = (hands, trump, stoeck_enabled=true))]
fn rs_score_stoeck(hands: Vec<u64>, trump: i32, stoeck_enabled: bool) -> (i32, i32) {
    let mut h = [0u64; 4];
    h.copy_from_slice(&hands);
    let rules = Rules { stoeck_enabled, ..Rules::default() };
    let out = score_stoeck(&h, trump, &rules);
    (out[0], out[1])
}

#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature = (trick_points, tricks_won, last_trick_winner, contract, weis=(0,0), stoeck=(0,0), multipliers=None, last_trick_bonus=5, match_bonus=100, weis_enabled=true, stoeck_enabled=true))]
fn rs_score_round(
    trick_points: (i32, i32),
    tricks_won: (usize, usize),
    last_trick_winner: usize,
    contract: usize,
    weis: (i32, i32),
    stoeck: (i32, i32),
    multipliers: Option<Vec<i32>>,
    last_trick_bonus: i32,
    match_bonus: i32,
    weis_enabled: bool,
    stoeck_enabled: bool,
) -> ((i32, i32), (i32, i32), (i32, i32), (i32, i32), (i32, i32), i32, (i32, i32)) {
    let rules = build_rules(
        multipliers, weis_enabled, false, true, true, stoeck_enabled, last_trick_bonus,
        match_bonus, true, true, None,
    );
    let s: RoundScore = score_round(
        [trick_points.0, trick_points.1],
        [tricks_won.0, tricks_won.1],
        last_trick_winner,
        contract,
        &rules,
        [weis.0, weis.1],
        [stoeck.0, stoeck.1],
    );
    let total = s.total();
    (
        (s.trick_points[0], s.trick_points[1]),
        (s.last_trick[0], s.last_trick[1]),
        (s.match_bonus[0], s.match_bonus[1]),
        (s.weis[0], s.weis[1]),
        (s.stoeck[0], s.stoeck[1]),
        s.multiplier,
        (total[0], total[1]),
    )
}

#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature = (trick_points, tricks_won, last_trick_winner, contract, trick_results, weis=(0,0), stoeck=(0,0), multipliers=None, claim_order=None))]
fn rs_claim_sequence(
    trick_points: (i32, i32),
    tricks_won: (usize, usize),
    last_trick_winner: usize,
    contract: usize,
    trick_results: Vec<(usize, i32)>,
    weis: (i32, i32),
    stoeck: (i32, i32),
    multipliers: Option<Vec<i32>>,
    claim_order: Option<Vec<u8>>,
) -> Vec<(usize, i32)> {
    let rules = build_rules(
        multipliers, true, false, true, true, true, 5, 100, true, true, claim_order,
    );
    let score = score_round(
        [trick_points.0, trick_points.1],
        [tricks_won.0, tricks_won.1],
        last_trick_winner,
        contract,
        &rules,
        [weis.0, weis.1],
        [stoeck.0, stoeck.1],
    );
    claim_sequence(&score, &trick_results, &rules)
}

#[pyfunction]
#[pyo3(signature = (tricks, current_trick, current_leader, trump, puur_exempt=true))]
fn rs_infer_forbidden(
    tricks: Vec<(usize, Vec<usize>)>,
    current_trick: Vec<usize>,
    current_leader: usize,
    trump: i32,
    puur_exempt: bool,
) -> Vec<u64> {
    let rules = Rules { puur_exempt, ..Rules::default() };
    infer_forbidden(&tricks, &current_trick, current_leader, trump, &rules).to_vec()
}

/// The table read that feeds the display. Public information only — see awareness.rs.
#[pyfunction]
fn rs_trick_taker(cards: Vec<usize>, leader: usize, contract: usize) -> Option<usize> {
    trick_taker(&cards, leader, contract)
}

/// Leaf positions with the *mean* of many random playouts as the label.
///
/// The label is deliberately the playout's own expectation rather than the true value of the
/// position: fitting to it makes the evaluator a zero-variance version of the thing it
/// replaces, so a measured difference is variance and nothing else. See leafeval.rs.
///
/// Positions come from random play, one per ply — roughly the distribution the tree's leaves
/// are drawn from, since a leaf is a short tree descent followed by random continuation.
#[pyfunction]
#[pyo3(signature = (seed, rounds, playouts, contract=None))]
fn rs_leaf_samples(
    seed: u64,
    rounds: usize,
    playouts: usize,
    contract: Option<usize>,
) -> (Vec<Vec<f64>>, Vec<f64>) {
    let rules = Rules::default();
    let mut rng = Rng::new(seed | 1);
    let mut xs: Vec<Vec<f64>> = Vec::new();
    let mut ys: Vec<f64> = Vec::new();
    const ROOT: usize = 0;

    for r in 0..rounds {
        let c = contract.unwrap_or(rng.below(6) as usize);
        let k = Kernel::new(c, rules.strict_undertrump, rules.puur_exempt, 5, 0);
        let hands = crate::deal::deal(seed.wrapping_add(r as u64).wrapping_mul(0x9E37_79B9), 0);
        let mut round = Round::new(c, hands, rng.below(4) as usize, rules);

        while !round.done() {
            let mut feats = [0.0f64; N_FEATURES];
            features(
                &round.hands, &round.trick, round.leader, round.to_play(),
                &round.tricks_won, &k, ROOT, &mut feats,
            );

            // The label: many random completions of this exact position, averaged. The
            // baseline evaluator is one draw from this distribution; the fit is its mean.
            let banked = round.trick_points;
            let mut acc = 0.0f64;
            for _ in 0..playouts {
                let mut sim = round.clone();
                while !sim.done() {
                    let card = pick_random(sim.legal_moves(sim.to_play()), &mut rng);
                    let _ = sim.play(card);
                }
                let a = sim.trick_points[ROOT] - banked[ROOT] + k.last_trick_bonus
                    * if sim.last_trick_winner as usize & 1 == ROOT { 1 } else { 0 };
                let b = sim.trick_points[1 - ROOT] - banked[1 - ROOT] + k.last_trick_bonus
                    * if sim.last_trick_winner as usize & 1 == ROOT { 0 } else { 1 };
                acc += a as f64 / ((a + b).max(1)) as f64;
            }
            xs.push(feats.to_vec());
            ys.push(acc / playouts as f64);

            let card = pick_random(round.legal_moves(round.to_play()), &mut rng);
            if round.play(card).is_err() {
                break;
            }
        }
    }
    (xs, ys)
}

/// Features of one candidate card, for building a policy-training set in Python.
#[pyfunction]
#[pyo3(signature = (card, hand, live, trick, contract, trump, partner_winning, opponent_winning))]
#[allow(clippy::too_many_arguments)]
fn rs_card_features(
    card: usize,
    hand: u64,
    live: u64,
    trick: Vec<usize>,
    contract: usize,
    trump: i32,
    partner_winning: bool,
    opponent_winning: bool,
) -> Vec<f32> {
    let mut out = [0.0f32; N_POLICY_FEATURES];
    card_features(card, hand, live, &trick, contract, trump,
                  partner_winning, opponent_winning, &mut out);
    out.to_vec()
}

/// What the bidding says, exposed so the Python mirror can be held to the same answer.
#[pyfunction]
fn rs_infer_from_bid(
    forehand: usize,
    declarer: usize,
    contract: usize,
    seat: usize,
) -> (Vec<Vec<i8>>, Vec<i8>) {
    let (suits, ranks) = infer_from_bid(forehand, declarer, contract, seat);
    (suits.iter().map(|r| r.to_vec()).collect(), ranks.to_vec())
}

/// The search's reward, exposed so the Python mirror can be held to the same numbers.
#[pyfunction]
#[pyo3(signature = (ours, theirs, team, scores, weis, target, multiplier))]
fn rs_reward(
    ours: i32,
    theirs: i32,
    team: usize,
    scores: (i32, i32),
    weis: (i32, i32),
    target: i32,
    multiplier: i32,
) -> f64 {
    reward(
        ours,
        theirs,
        team,
        &Stakes {
            scores: [scores.0, scores.1],
            bonus: [weis.0, weis.1],
            target,
            multiplier,
            risk_lambda: 0.0,
        },
    )
}

/// What the discards suggest, per seat and suit. Mirror of `krass_jass/reading.py`.
#[pyfunction]
fn rs_infer_affinity(
    tricks: Vec<(usize, Vec<usize>)>,
    current_trick: Vec<usize>,
    current_leader: usize,
    trump: i32,
) -> Vec<Vec<i8>> {
    infer_affinity(&tricks, &current_trick, current_leader, trump)
        .iter()
        .map(|row| row.to_vec())
        .collect()
}

/// Draw `samples` determinizations. Exposed for tests: the two properties worth pinning —
/// that the prior tilts the sampling and that it never removes a world — are statements about
/// a *distribution*, so they need many draws rather than one search.
#[pyfunction]
#[pyo3(signature = (unseen, counts, forbidden, affinity, seed, samples, rank_bias=None))]
fn rs_determinize(
    unseen: u64,
    counts: Vec<usize>,
    forbidden: Vec<u64>,
    affinity: Vec<Vec<i8>>,
    seed: u64,
    samples: usize,
    rank_bias: Option<Vec<i8>>,
) -> Vec<Vec<u64>> {
    let mut c = [0usize; 4];
    c.copy_from_slice(&counts[..4]);
    let mut f = [0u64; 4];
    f.copy_from_slice(&forbidden[..4]);
    let mut a = [[0i8; 4]; 4];
    for (seat, row) in affinity.iter().enumerate().take(4) {
        for (suit, &n) in row.iter().enumerate().take(4) {
            a[seat][suit] = n;
        }
    }
    let mut rb = [0i8; 4];
    if let Some(rows) = rank_bias {
        for (i, &v) in rows.iter().enumerate().take(4) {
            rb[i] = v;
        }
    }
    let mut rng = Rng::new(seed | 1);
    let mut out = Vec::with_capacity(samples);
    for _ in 0..samples {
        let mut dealt = [0u64; 4];
        if determinize(unseen, &c, &f, &a, &rb, &mut dealt, &mut rng) {
            out.push(dealt.to_vec());
        }
    }
    out
}

/// The convention tie-break, on a candidate list the caller already has.
///
/// Exposed so `tests/test_convention.py` can hold both implementations to the same answer:
/// both sides read the *same* search output, so any difference is the convention itself.
#[pyfunction]
#[pyo3(signature = (candidates, hand, unseen, seen, trick, seat, trump, contract, forbidden))]
#[allow(clippy::too_many_arguments)]
fn rs_convention_choose(
    candidates: Vec<(usize, u64, f64, u32)>,
    hand: u64,
    unseen: u64,
    seen: u64,
    trick: Vec<usize>,
    seat: usize,
    trump: i32,
    contract: usize,
    forbidden: Vec<u64>,
) -> Option<usize> {
    let cands: Vec<Candidate> = candidates
        .into_iter()
        .map(|(card, visits, mean_score, determinizations_selecting)| Candidate {
            card,
            visits,
            mean_score,
            determinizations_selecting,
        })
        .collect();
    let mut forb = [0u64; 4];
    for (i, v) in forbidden.into_iter().take(4).enumerate() {
        forb[i] = v;
    }
    convention::choose(
        &cands, hand, unseen, seen, &trick, seat, trump, contract, &forb,
    )
}

/// Returns the contract index, or -1 for a shove.
#[pyfunction]
#[pyo3(signature = (hand, is_forehand, multipliers=None))]
fn rs_select_trump(hand: u64, is_forehand: bool, multipliers: Option<Vec<i32>>) -> i64 {
    let rules = build_rules(multipliers, true, false, true, true, true, 5, 100, true, true, None);
    let action = select_trump(hand, is_forehand, &rules);
    if action == SHOVE {
        -1
    } else {
        action as i64
    }
}

#[pyfunction]
#[pyo3(signature = (hand, multipliers=None))]
fn rs_trump_scores(hand: u64, multipliers: Option<Vec<i32>>) -> Vec<f64> {
    let rules = build_rules(multipliers, true, false, true, true, true, 5, 100, true, true, None);
    crate::trump::score_all(hand, &rules).to_vec()
}

/// Replay a whole round through the Rust round state, returning everything the Python
/// `RoundState` exposes, so the two can be compared ply by ply.
#[pyfunction]
#[pyo3(signature = (contract, hands, leader, cards))]
fn rs_replay_round(
    contract: usize,
    hands: Vec<u64>,
    leader: usize,
    cards: Vec<usize>,
) -> PyResult<(Vec<u64>, (i32, i32), (usize, usize), i32, Vec<(usize, i32)>, Vec<u64>)> {
    use crate::round::Round;
    use pyo3::exceptions::PyValueError;

    let mut h = [0u64; 4];
    h.copy_from_slice(&hands);
    let mut round = Round::new(contract, h, leader, Rules::default());

    // Record the legal set at every ply — comparing only the final state would miss a
    // divergence that happened to end up in the same place.
    let mut legal_per_ply = Vec::with_capacity(cards.len());
    for &card in &cards {
        legal_per_ply.push(round.legal_moves(round.to_play()));
        round
            .play(card)
            .map_err(|e| PyValueError::new_err(format!("{e:?}")))?;
    }
    Ok((
        round.hands.to_vec(),
        (round.trick_points[0], round.trick_points[1]),
        (round.tricks_won[0], round.tricks_won[1]),
        round.last_trick_winner,
        round.trick_results.clone(),
        legal_per_ply,
    ))
}

#[pyfunction]
fn rs_deal(seed: u64, round: u32) -> Vec<u64> {
    crate::deal::deal(seed, round).to_vec()
}

/// A Rust `Game`, driven from Python so the two phase machines can be run through the same
/// decisions and their event streams compared.
#[pyclass(name = "RsGame")]
pub struct PyGame {
    inner: crate::game::Game,
}

#[pymethods]
impl PyGame {
    #[new]
    #[pyo3(signature = (seed, target_score=1000, weis_enabled=true, weis_manual=false, stoeck_enabled=true, multipliers=None))]
    fn new(
        seed: u64,
        target_score: i32,
        weis_enabled: bool,
        weis_manual: bool,
        stoeck_enabled: bool,
        multipliers: Option<Vec<i32>>,
    ) -> Self {
        let mut rules = Rules {
            target_score,
            weis_enabled,
            weis_manual,
            stoeck_enabled,
            ..Rules::default()
        };
        if let Some(m) = multipliers {
            for (i, v) in m.iter().take(6).enumerate() {
                rules.multipliers[i] = *v;
            }
        }
        PyGame { inner: crate::game::Game::new(rules, seed) }
    }

    #[getter]
    fn phase(&self) -> String {
        self.inner.phase.as_str().to_string()
    }
    #[getter]
    fn to_act(&self) -> Option<usize> {
        self.inner.to_act()
    }
    #[getter]
    fn scores(&self) -> (i32, i32) {
        (self.inner.scores[0], self.inner.scores[1])
    }
    #[getter]
    fn forehand(&self) -> usize {
        self.inner.forehand
    }
    #[getter]
    fn round_index(&self) -> u32 {
        self.inner.round_index
    }
    #[getter]
    fn weis_offers(&self) -> Vec<i32> {
        self.inner.weis_offers.to_vec()
    }

    fn hand_of(&self, seat: usize) -> u64 {
        self.inner.hand_of(seat)
    }

    fn legal_moves(&self, seat: usize) -> u64 {
        self.inner.round.as_ref().map_or(0, |r| r.legal_moves(seat))
    }

    /// `action` is a contract index, or -1 to shove.
    fn bid(&mut self, seat: usize, action: i64) -> PyResult<()> {
        use pyo3::exceptions::PyValueError;
        let a = if action < 0 { crate::trump::SHOVE } else { action as usize };
        self.inner.bid(seat, a).map_err(|e| PyValueError::new_err(format!("{e:?}")))
    }

    fn choose_weis(&mut self, seat: usize, announce: bool) -> PyResult<()> {
        use pyo3::exceptions::PyValueError;
        self.inner
            .choose_weis(seat, announce)
            .map_err(|e| PyValueError::new_err(format!("{e:?}")))
    }

    fn play(&mut self, seat: usize, card: usize) -> PyResult<()> {
        use pyo3::exceptions::PyValueError;
        self.inner.play(seat, card).map_err(|e| PyValueError::new_err(format!("{e:?}")))
    }

    fn next_round(&mut self) -> PyResult<()> {
        use pyo3::exceptions::PyValueError;
        self.inner.next_round().map_err(|e| PyValueError::new_err(format!("{e:?}")))
    }

    /// Every event as JSON, in order.
    fn events(&self) -> Vec<String> {
        self.inner.log.all().iter().map(|e| e.to_json()).collect()
    }

    /// Events this seat may see, from `after` exclusive.
    fn events_for(&self, seat: usize, after: usize) -> Vec<String> {
        self.inner.log.for_seat(seat, after).into_iter().map(|e| e.to_json()).collect()
    }

    fn weis_summary(&self) -> Vec<(usize, i32, Option<Vec<usize>>, bool, bool)> {
        self.inner
            .weis_summary
            .iter()
            .map(|e| (e.seat, e.points, e.cards.clone(), e.winner, e.best))
            .collect()
    }

    fn stoeck_announced(&self) -> Vec<(usize, i32, usize)> {
        self.inner.stoeck_announced.clone()
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyGame>()?;
    m.add_function(wrap_pyfunction!(rs_deal, m)?)?;
    m.add_function(wrap_pyfunction!(rs_replay_round, m)?)?;
    m.add_function(wrap_pyfunction!(rules_dict, m)?)?;
    m.add_function(wrap_pyfunction!(rs_find_weis, m)?)?;
    m.add_function(wrap_pyfunction!(rs_score_weis, m)?)?;
    m.add_function(wrap_pyfunction!(rs_score_stoeck, m)?)?;
    m.add_function(wrap_pyfunction!(rs_score_round, m)?)?;
    m.add_function(wrap_pyfunction!(rs_claim_sequence, m)?)?;
    m.add_function(wrap_pyfunction!(rs_infer_forbidden, m)?)?;
    m.add_function(wrap_pyfunction!(rs_trick_taker, m)?)?;
    m.add_function(wrap_pyfunction!(rs_convention_choose, m)?)?;
    m.add_function(wrap_pyfunction!(rs_infer_affinity, m)?)?;
    m.add_function(wrap_pyfunction!(rs_reward, m)?)?;
    m.add_function(wrap_pyfunction!(rs_infer_from_bid, m)?)?;
    m.add_function(wrap_pyfunction!(rs_leaf_samples, m)?)?;
    m.add_function(wrap_pyfunction!(rs_card_features, m)?)?;
    m.add_function(wrap_pyfunction!(rs_determinize, m)?)?;
    m.add_function(wrap_pyfunction!(rs_select_trump, m)?)?;
    m.add_function(wrap_pyfunction!(rs_trump_scores, m)?)?;
    Ok(())
}
