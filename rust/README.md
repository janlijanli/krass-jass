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

## What is here now

The full rules, not just the hot path: legal moves, trick resolution, scoring, the
Stöck-Weis-Stich claim ordering, Weis, Stöck, void inference, trump selection and round
state — alongside the rollout kernel, the DMCTS tree and the exact endgame solver.

That is more than the search needed. It is what a **client-side build** needs: the crate
compiles to wasm32 at 1.39x native (`bench/wasm.md`), so the game can run with no server at
all. Doing that with a JavaScript copy of the rules would mean two implementations and two
places to be wrong; doing it from this crate means one.

## What stays in Python

The web layer, the game phase machine, the event log, the observation builder, training and
the arena. Python remains the engine of record for the served game.

## Keeping the two honest

`tests/test_rules_port.py` checks every ported rule against its Python twin over randomised
input — thousands of hands for Weis, whole rounds ply-by-ply for round state and voids.
`tests/reference.py` is written from the rules text and imports neither, which is what stops
the two implementations agreeing on the same misreading.

Trump weights are `include_str!`d from `krass_jass/data/trump_weights.json`, the same file
Python reads, because wasm has no filesystem. One source, both sides.

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
