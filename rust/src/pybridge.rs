//! PyO3 exports for the ported rules, so each one can be checked against the Python it
//! replaces.
//!
//! This is the whole safety argument for the port, and it is the same one that made the
//! search port safe: `tests/reference.py` was written from the rules text and imports
//! neither implementation, so the Python side is itself independently checked. Agreement
//! across all three is what says the port is right.

use pyo3::prelude::*;

use crate::awareness::{trick_points, trick_taker, trump_read};
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

#[pyfunction]
fn rs_trick_points(cards: Vec<usize>, contract: usize) -> i32 {
    trick_points(&cards, contract)
}

/// `(trumps still out, per-seat void codes)` — 0 unknown, 1 only-possibly-Puur, 2 none.
#[pyfunction]
#[pyo3(signature = (tricks, current_trick, current_leader, seat, hand, trump, puur_exempt=true))]
fn rs_trump_read(
    tricks: Vec<(usize, Vec<usize>)>,
    current_trick: Vec<usize>,
    current_leader: usize,
    seat: usize,
    hand: u64,
    trump: i32,
    puur_exempt: bool,
) -> (Option<u32>, Vec<u8>) {
    let rules = Rules { puur_exempt, ..Rules::default() };
    let read = trump_read(
        &tricks, &current_trick, current_leader, seat, hand, trump, &rules,
    );
    (read.out, read.voids.to_vec())
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
    m.add_function(wrap_pyfunction!(rs_trick_points, m)?)?;
    m.add_function(wrap_pyfunction!(rs_trump_read, m)?)?;
    m.add_function(wrap_pyfunction!(rs_select_trump, m)?)?;
    m.add_function(wrap_pyfunction!(rs_trump_scores, m)?)?;
    Ok(())
}
