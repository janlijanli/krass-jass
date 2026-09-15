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
state — alongside the rollout kernel and the search. The search is ISMCTS (`ismcts.rs`: one tree
shared across imagined deals), with beliefs in `belief.rs` (a pool of consistent worlds weighted
by the other seats' plays and bid), the play model those likelihoods come from (`playmodel.rs`),
and a belief network trained on self-play with the true deal (`beliefnet.rs`, off by default).
The voting DMCTS tree (`search.rs`) and the exact endgame solver (`endgame.rs`) are still here
behind flags: both were measured and superseded (`docs/measurements.md` §5h, §3e).

The play model and belief network weights are `include_str!`d from `krass_jass/data/`, like the
trump weights. The wasm build leaves the belief network out: it is unused there and would triple
the payload.

That is more than the search needed. It is what a **client-side build** needs: the crate
compiles to wasm32 at 1.39x native (`bench/wasm.md`), so the game can run with no server at
all. Doing that with a JavaScript copy of the rules would mean two implementations and two
places to be wrong; doing it from this crate means one.

The phase machine and event log are here too, so the crate can run a whole game start to
finish: deal, bidding, Weis, nine tricks, scoring, next round, game over.

**The deal algorithm is specified rather than borrowed** (`deal.rs` / `krass_jass/deal.py`).
CPython's Mersenne Twister seeded from a string cannot be reproduced in Rust, so "any game
replays bit-for-bit" would otherwise have been true only inside one language. Both sides run
SplitMix64 → Fisher-Yates → Lemire, and a test asserts 900 seed/round pairs deal identically.

## What stays in Python

The web layer, the observation builder, training and the arena. Python remains the engine of
record for the served game.

## Keeping the two honest

`tests/test_rules_port.py` checks every ported rule against its Python twin over randomised
input — thousands of hands for Weis, whole rounds ply-by-ply for round state and voids.
`tests/test_game_port.py` drives both engines through the *same* decisions and diffs the
entire event stream, which catches an event emitted in the wrong order, with the wrong
payload, or addressed to the wrong seat — none of which would change a score.
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
