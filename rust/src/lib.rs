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

pub mod cards;
pub mod determinize;
pub mod endgame;
pub mod legal;
pub mod rng;
pub mod rollout;
pub mod search;
pub mod tables;

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
    seat, hand, unseen, trick, trick_leader, contract, forbidden=None,
    determinizations=1000, iterations=800, exploration=1.5, seed=0, threads=1,
    endgame_cards=5, strict_undertrump=true, puur_exempt=true
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
    determinizations: usize,
    iterations: usize,
    exploration: f64,
    seed: u64,
    threads: usize,
    endgame_cards: u32,
    strict_undertrump: bool,
    puur_exempt: bool,
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
    let k = make_kernel(contract, strict_undertrump, puur_exempt, 5, 0)?;
    let pos = search::Position {
        seat: seat & 3,
        hand,
        unseen,
        trick,
        trick_leader: trick_leader & 3,
        forbidden: v,
    };
    // Long CPU-bound work: release the GIL so the caller stays responsive and rayon can
    // actually use the cores.
    let out = py.allow_threads(|| {
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
    Ok(())
}
