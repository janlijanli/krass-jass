# krass-jass-core

The hot path: legal-move generation, the rollout kernel and the DMCTS tree.

## Why this exists

`docs/plan-review.md` §1 measured the pure-Python search at **35k iterations/sec**, which
puts the literature's tuned 800k-rollout budget at 23 seconds per move and a self-play
training corpus at **33 days** of an 8-core machine. That is not a loop anyone iterates on,
and the strength goal requires learned self-play, which requires that loop.

Profiling also settled *what* to port. The rollout is 73% of search time, so porting only
the kernel — the escalation path originally written into `PLAN.md` — would have capped the
whole exercise at ~2.4x by Amdahl. **The tree had to come with it.**

## What stays in Python

`RoundState`, the observation builder, scoring, Weis, the web layer, training and the arena.
Those run 36 times a game. Only the search runs 800,000 times a move.

## Safety

The port is checked, not trusted. `tests/test_rust_conformance.py` walks whole random rounds
for all six contracts and asserts three-way agreement between this crate, the Python engine,
and `tests/reference.py` — which was written from the rules text and imports neither. It also
asserts the search returns identical results at 1 and 8 threads, because bit-for-bit replay
is a project constraint and would otherwise break the moment the search went parallel.

Determinism comes from SplitMix64: one seed is expanded into an independent stream per
determinization, so results never depend on how rayon scheduled the work.

## Build

```bash
cd rust && maturin develop --release
```

Requires a Rust toolchain (`rustup default stable`) and `maturin` in the active venv.

## Layout

| | |
|---|---|
| `cards.rs` | encoding, masks — the contract shared with `krass_jass/cards.py` |
| `tables.rs` | card values, trick strengths, undertrump masks, all `const` |
| `legal.rs` | legal moves — the twin of `krass_jass/legal.py` |
| `rollout.rs` | the random playout kernel |
| `determinize.rs` | void-consistent sampling of the unseen cards |
| `search.rs` | UCT tree and per-determinization aggregation |
| `lib.rs` | PyO3 bindings |
