//! PyO3 bindings for the krass-jass search core.
//!
//! The Python package stays the engine of record: `RoundState`, the observation builder,
//! scoring and Weis all live there and run 36 times a game. This crate owns only the hot
//! path — legal moves, rollouts and the DMCTS tree — which runs hundreds of thousands of
//! times per move.
//!
//! Every function here has a Python twin, and `tests/test_rust_conformance.py` asserts they
//! agree over whole random rounds against `tests/reference.py`, which was written from the
//! rules text and imports neither.

#[cfg(feature = "python")]
use pyo3::prelude::*;
#[cfg(feature = "python")]
use pyo3::exceptions::PyValueError;

pub mod awareness;
pub mod bidding;
pub mod cards;
pub mod config;
pub mod convention;
pub mod deal;
pub mod events;
pub mod game;
pub mod determinize;
pub mod endgame;
pub mod ismcts;
pub mod leafeval;
pub mod legal;
pub mod objective;
pub mod policy;
pub mod reading;
pub mod rng;
pub mod rollout;
pub mod round;
pub mod search;
pub mod tables;
pub mod scoring;
pub mod trump;
#[cfg(feature = "python")]
mod pybridge;
pub mod voids;
pub mod weis;

#[cfg(feature = "wasm")]
mod wasm_api;
#[cfg(feature = "wasm")]
mod wasm_bench;

#[cfg(feature = "python")]
use cards::NUM_SEATS;
#[cfg(feature = "python")]
use rng::Rng;
#[cfg(feature = "python")]
use rollout::Kernel;

#[cfg(feature = "python")]
fn make_kernel(
    contract: usize,
    strict_undertrump: bool,
    puur_exempt: bool,
    last_trick_bonus: i32,
    match_bonus: i32,
) -> PyResult<Kernel> {
    if contract >= tables::NUM_CONTRACTS {
        return Err(PyValueError::new_err(format!("bad contract {contract}")));
    }
    Ok(Kernel::new(
        contract,
        strict_undertrump,
        puur_exempt,
        last_trick_bonus,
        match_bonus,
    ))
}

#[cfg(feature = "python")]
/// Mask of legal cards. Twin of `krass_jass.legal.legal_moves`.
#[pyfunction]
#[pyo3(signature = (hand, trump, led, best_trump_strength, strict_undertrump=true, puur_exempt=true))]
fn legal_moves(
    hand: u64,
    trump: i32,
    led: i32,
    best_trump_strength: i32,
    strict_undertrump: bool,
    puur_exempt: bool,
) -> u64 {
    legal::legal_moves(
        hand,
        trump,
        led,
        best_trump_strength,
        strict_undertrump,
        puur_exempt,
    )
}

#[cfg(feature = "python")]
/// Random playout to the end of the round. Twin of `krass_jass.rollout.play_out`.
#[pyfunction]
#[pyo3(signature = (hands, leader, contract, seed, strict_undertrump=true, puur_exempt=true, last_trick_bonus=5, match_bonus=100))]
#[allow(clippy::too_many_arguments)]
fn play_out(
    hands: Vec<u64>,
    leader: usize,
    contract: usize,
    seed: u64,
    strict_undertrump: bool,
    puur_exempt: bool,
    last_trick_bonus: i32,
    match_bonus: i32,
) -> PyResult<(i32, i32)> {
    if hands.len() != NUM_SEATS {
        return Err(PyValueError::new_err("hands must have 4 entries"));
    }
    let k = make_kernel(
        contract,
        strict_undertrump,
        puur_exempt,
        last_trick_bonus,
        match_bonus,
    )?;
    let mut h = [0u64; NUM_SEATS];
    h.copy_from_slice(&hands);
    let mut rng = Rng::new(seed);
    Ok(rollout::play_out(&mut h, leader & 3, &k, &mut rng))
}

#[cfg(feature = "python")]
/// Benchmark helper: `n` playouts from one deal, returning only the count. Keeps the
/// Python-side loop out of the measurement.
#[pyfunction]
#[pyo3(signature = (hands, leader, contract, seed, n))]
fn play_out_many(
    hands: Vec<u64>,
    leader: usize,
    contract: usize,
    seed: u64,
    n: usize,
) -> PyResult<u64> {
    if hands.len() != NUM_SEATS {
        return Err(PyValueError::new_err("hands must have 4 entries"));
    }
    let k = make_kernel(contract, true, true, 5, 0)?;
    let mut base = [0u64; NUM_SEATS];
    base.copy_from_slice(&hands);
    let mut rng = Rng::new(seed);
    let mut acc = 0u64;
    for _ in 0..n {
        let mut h = base;
        let (a, _) = rollout::play_out(&mut h, leader & 3, &k, &mut rng);
        acc = acc.wrapping_add(a as u64);
    }
    Ok(acc)
}

#[cfg(feature = "python")]
/// Determinized MCTS. Returns `(card, visits, mean_score, determinizations_selecting)`
/// per legal move, best first — the shape the decision trace in `PLAN.md` §6 expects.
#[pyfunction]
#[pyo3(signature = (
    seat, hand, unseen, trick, trick_leader, contract, forbidden=None, affinity=None, rank_bias=None,
    determinizations=1000, iterations=800, exploration=1.5, seed=0, threads=1,
    endgame_cards=5, strict_undertrump=true, puur_exempt=true,
    scores=(0, 0), weis=(0, 0), target=0, multiplier=1, adversarial=true, risk_lambda=0.0, leaf_weights=None, ismcts=false, resample_every=1, order_moves=false, prior_weight=0.0, policy_weights=None
))]
#[allow(clippy::too_many_arguments)]
fn dmcts(
    py: Python<'_>,
    seat: usize,
    hand: u64,
    unseen: u64,
    trick: Vec<usize>,
    trick_leader: usize,
    contract: usize,
    forbidden: Option<Vec<u64>>,
    affinity: Option<Vec<Vec<i8>>>,
    rank_bias: Option<Vec<i8>>,
    determinizations: usize,
    iterations: usize,
    exploration: f64,
    seed: u64,
    threads: usize,
    endgame_cards: u32,
    strict_undertrump: bool,
    puur_exempt: bool,
    scores: (i32, i32),
    weis: (i32, i32),
    target: i32,
    multiplier: i32,
    adversarial: bool,
    risk_lambda: f64,
    leaf_weights: Option<Vec<f64>>,
    ismcts: bool,
    resample_every: usize,
    order_moves: bool,
    prior_weight: f64,
    policy_weights: Option<Vec<f32>>,
) -> PyResult<Vec<(usize, u64, f64, u32)>> {
    if hand & unseen != 0 {
        return Err(PyValueError::new_err("hand and unseen must be disjoint"));
    }
    let mut v = [0u64; NUM_SEATS];
    if let Some(vs) = forbidden {
        if vs.len() != NUM_SEATS {
            return Err(PyValueError::new_err("forbidden must have 4 entries"));
        }
        v.copy_from_slice(&vs);
    }
    let mut a = [[0i8; 4]; NUM_SEATS];
    if let Some(rows) = affinity {
        if rows.len() != NUM_SEATS || rows.iter().any(|r| r.len() != 4) {
            return Err(PyValueError::new_err("affinity must be 4 rows of 4"));
        }
        for (seat, row) in rows.iter().enumerate() {
            for (suit, &n) in row.iter().enumerate() {
                a[seat][suit] = n;
            }
        }
    }
    let mut rb = [0i8; NUM_SEATS];
    if let Some(rows) = rank_bias {
        if rows.len() != NUM_SEATS {
            return Err(PyValueError::new_err("rank_bias must have 4 entries"));
        }
        rb.copy_from_slice(&rows);
    }
    let k = make_kernel(contract, strict_undertrump, puur_exempt, 5, 0)?;
    let pos = search::Position {
        seat: seat & 3,
        hand,
        unseen,
        trick,
        trick_leader: trick_leader & 3,
        forbidden: v,
        affinity: a,
        rank_bias: rb,
        // `target: 0` keeps the old behaviour — the share of this round — which is what the
        // round-level arena measures and what every figure before measurements.md §5d used.
        stakes: objective::Stakes {
            scores: [scores.0, scores.1],
            bonus: [weis.0, weis.1],
            target,
            multiplier,
            risk_lambda,
        },
        adversarial,
        leaf_weights: leaf_weights.unwrap_or_default(),
    };
    // Long CPU-bound work: release the GIL so the caller stays responsive and rayon can
    // actually use the cores.
    let out = py.allow_threads(|| {
        // The endgame is an exact double-dummy solve that replaces the search entirely, and
        // it is identical under either algorithm — so endgame positions go to `dmcts`, which
        // already owns that branch, rather than being duplicated here.
        let max_hand = (0..NUM_SEATS)
            .map(|s| if s == pos.seat & 3 { pos.hand.count_ones() } else { 0 })
            .max()
            .unwrap_or(0);
        let in_endgame = endgame_cards > 0 && max_hand <= endgame_cards && max_hand > 0;
        if ismcts && !in_endgame {
            // Equal total budget: one shared tree gets what the determinized search spends
            // across all of its separate ones.
            return crate::ismcts::ismcts(
                &pos, &k, determinizations * iterations, exploration, seed, resample_every,
                order_moves, prior_weight,
                policy_weights.as_deref().unwrap_or(&[]),
            );
        }
        search::dmcts(
            &pos,
            &k,
            determinizations,
            iterations,
            exploration,
            seed,
            threads.max(1),
            endgame_cards,
        )
    });
    Ok(out
        .into_iter()
        .map(|c| (c.card, c.visits, c.mean_score, c.determinizations_selecting))
        .collect())
}

#[cfg(feature = "python")]
/// Exact double-dummy solve. Returns `(team_0_points, nodes_visited)`.
///
/// Perfect information: every seat plays optimally knowing all four hands. Inside a
/// determinization that assumption is exactly right, which is why it can replace the
/// random playout in the endgame.
#[pyfunction]
#[pyo3(signature = (hands, trick, leader, contract, strict_undertrump=true, puur_exempt=true, last_trick_bonus=5))]
fn solve_endgame(
    hands: Vec<u64>,
    trick: Vec<usize>,
    leader: usize,
    contract: usize,
    strict_undertrump: bool,
    puur_exempt: bool,
    last_trick_bonus: i32,
) -> PyResult<(i32, u64)> {
    if hands.len() != NUM_SEATS {
        return Err(PyValueError::new_err("hands must have 4 entries"));
    }
    let k = make_kernel(contract, strict_undertrump, puur_exempt, last_trick_bonus, 0)?;
    let mut h = [0u64; NUM_SEATS];
    h.copy_from_slice(&hands);
    Ok(endgame::solve_exact(&mut h, &trick, leader & 3, &k))
}

#[cfg(feature = "python")]
#[pymodule]
fn krass_jass_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(legal_moves, m)?)?;
    m.add_function(wrap_pyfunction!(play_out, m)?)?;
    m.add_function(wrap_pyfunction!(play_out_many, m)?)?;
    m.add_function(wrap_pyfunction!(dmcts, m)?)?;
    m.add_function(wrap_pyfunction!(solve_endgame, m)?)?;
    pybridge::register(m)?;
    Ok(())
}
