# krass-jass

Web app to play Schieber Jass (Swiss, 4 players, French deck): one human plus three
bot services in a Docker Compose stack. The substantial goal is training an algorithm
that plays the game well.

**Full plan, rules research and rationale: see `PLAN.md`.** Read it before starting
work on a new milestone. This file holds only the standing constraints that apply to
every session.

---

## Current state

**M0–M4 are done and the game is playable.** Rule variants locked in `docs/rules-config.md`;
the engine and its property tests are in; the search is Rust. The bots run ISMCTS (one tree
shared across imagined deals) at 153,600 iterations through `krass_jass.agent`, with beliefs
weighted by the other seats' plays and bid, measured by `arena/`. **`docs/engine-report.md` is
the current summary of how the bots play and what each part is worth; `docs/measurements.md` is
the dated record behind it.**

**Trump selection is in and tuned.** Rule-based, with weights fitted against simulated
contract values (`arena/contracts.py`, `arena/fit_trump.py`): 58% of whole games against the
hand-written weights (`docs/measurements.md` §5n). It now calls Obenabe/Undenufe about half
the time — check that against human play before trusting it further.

M2 is done (FastAPI + WebSocket, bots in containers, the card fan, and a serverless wasm build).

**Sidi Barrani is a second game mode** (`RulesConfig.mode = "sidi"`, preset `SIDI`), the Schieber
stays the default and unchanged. Rules as the owner decided them in `docs/rules-config.md`; the
bidding language, how the bots bid, play for the bid and read the auction, and the order of work
in `docs/sidi-plan.md`. The auction lives in `krass_jass/auction.py` and `rust/src/auction.rs`
under the same two-implementation rule as everything else, and so is the bidder
(`krass_jass/sidi_bidding.py`, `rust/src/sidi_bidding.rs`): the offline build on GitHub Pages plays
the Sidi with the same bots as the server, doubling on the same estimate.

**The search is Rust** (`rust/`, exposed via `krass_jass.native`). Measured: 1.48M DMCTS
iterations/sec single-core, 6.19M on all cores — 42x the Python search. The tuned 800k
budget is 0.13s per move. Python remains the engine of record; only the search moved.
`bench/benchmark.py` reports both in CI.

Decisions still open. `PLAN.md` §9 has the full list of six; these two block architecture:

- **Latency budget per bot move.** *Settled 2026-09-15 by the owner:* strength over speed, a
  few seconds a move is acceptable. The shipped search takes well under a second natively.
- **CPU-only or GPU.** *Settled 2026-09-16 by the owner:* **CPU only, this Mac (8 cores).** So the
  network work is distillation and a value head for a *small* search; expert iteration is a week per
  iteration and RL from scratch is out of reach. See `docs/neural-plan.md`.

Do not design around an assumed answer to anything else here. Ask.

---

## Standing constraints

**Engine**
- Python where possible. Bitboard representation — a hand is a 36-bit integer, suits
  are masks. Not an object-oriented card model; the throughput difference is 10–50×.
- **The search lives in Rust** (`rust/`), because the strength goal requires learned
  self-play and Python put one training corpus at 33 days. Ported as a unit — kernel *and*
  UCT tree: profiling showed the rollout is 73% of search time, so porting the kernel alone
  would have capped the whole exercise at ~2.4x. Do not re-split them.
- **The rules exist twice, and that is deliberate.** Python is the engine of record and
  what the server runs; Rust is the same rules again so the game can run without a server
  (wasm) and so the search does not cross a language boundary. Ported: legal moves, trick
  resolution, scoring, claim order, Weis, Stöck, void inference, trump selection, round
  state, **the phase machine and the event log** — the crate can run a whole game.
- **The deal algorithm is specified, not borrowed** (`krass_jass/deal.py` and its Rust
  mirror). Python's `random` cannot be reproduced in Rust, so a shared SplitMix64 →
  Fisher-Yates → Lemire deal is what makes "replays bit-for-bit" true across languages.
  Do not swap either side back to a language RNG.
- Any change to a rule in Python must land in `rust/` in the same commit, and vice versa.
  `tests/test_rust_conformance.py` and `tests/test_rules_port.py` assert agreement over
  randomised input, and `tests/reference.py` — written from the rules text, importing
  neither — is what stops the two agreeing on the same mistake.
- Trump weights live in `krass_jass/data/trump_weights.json` and are `include_str!`d into
  Rust. One file, both implementations. Edit the JSON, not either copy.
- There is **no Python fallback for the search**, deliberately. A silent fallback is a 20x
  slowdown disguised as a working system.
- Legal-move generation is table-driven: 9 bits per suit → 512 entries, keyed on
  `(led_suit, trump, per-suit hand masks, trumped_yet)`. A lookup, not a branch tree.
- Python 3.12 or newer. 3.9 is ~48% slower on this workload; it is free throughput.
- The engine is authoritative. It computes `legal_moves`; every move a bot returns is
  re-validated server-side. Never trust a bot's move.

**Information boundary (the core invariant)**
- A single `build_observation(seat)` function decides what any agent sees. Bots receive
  their own hand, public history, and engine-computed legal moves — nothing else.
  No other player's hand, no deck order, no **game** seed, no full-state object.
  Not `game_id`, `round` or `trick` either — the engine joins those on when it writes
  the trace.
- The one deliberate exception is `decision_seed` (see Determinism below). It is derived,
  reveals nothing hidden, and without it replay is impossible. The raw game seed must
  never cross the boundary: it determines the deal, so a bot holding it can reconstruct
  every hand at the table.
- There is a CI test that fuzzes observations and asserts no unseen card identifier
  appears in the payload. If you change the observation shape, that test moves with it.
- Debug traces must not leak hidden state to the human mid-game. Traces are readable
  after the round ends, or behind `DEV_MODE` (off by default).

**Bots**
- One image, three replicas, configured by env (`AGENT_KIND`, `SEAT`, `TIME_BUDGET_MS`,
  `MODEL_VERSION`). Not three codebases.
- Stateless. Full observation in, move out, forget. No memory between turns.
- The agent is a **library** — `agent.decide(observation) -> move` — and FastAPI is a thin
  wrapper over it. Self-play and the arena import it and run it across a process pool;
  they never go through HTTP. The three containers serve one game to a human, not millions
  to a trainer.
- **One internal network per bot**, not one shared between them. No egress, no DB
  credentials, no writable volumes. Bots must not be able to reach each other: "no data
  exchange between players" is a premise of the design, not just a transport detail.
- Model weights are baked into the image and the image tag carries `MODEL_VERSION`.
  Do not mount the model store into a bot.
- Hard timeout with fallback to a random legal move. A hung bot must not stall a game.

**Determinism and tracing**
- All RNG — deal, determinization, rollouts — derives from one game seed. Any game
  replays bit-for-bit. This turns "the bot did something weird" into a test case.
- Bots are stateless services that roll their own dice, so this only works if they are
  seeded from outside: the engine sends
  `decision_seed = HMAC(game_seed, game_id ‖ seat ‖ round ‖ trick)` in every observation
  and the bot seeds from that alone.
- Every decision writes a structured record: game_id, round, trick, seat, agent version,
  model version, seed, legal moves, chosen move, per-candidate visits and scores,
  budget used, inferred voids.

**Data**
- Model weights are the stored "best practice", not a table of positions. There are
  ~1.16e28 states; you will never see the same one twice.
- Self-play training records → Parquet. Games, decision traces and eval results →
  Postgres. Do not put millions of card decisions in Postgres rows.

**Measured, and it changes things** (`docs/measurements.md`)
- The search budget pays to ~64× 2,400 iterations and is flat after (§3b). Serve 153,600. The
  older "saturates at 2,400" was true of the voting search and was carried across the change to
  ISMCTS without being re-taken — re-take any number whose algorithm has changed underneath it.
- **Beliefs are saturated.** Reading the table (the play and bid likelihood) was worth +1.3,
  replicated. Reading it *better* — sharper weights, a larger pool, a belief network, a play model
  retrained on today's bot — is worth nothing measurable, four times over (§5q, §5r). The offline
  oracle-equivalent measure predicted only that first step and has predicted nothing since: use it
  to screen for signal, never as a forecast of points.
- **The other seats are modelled by the play model inside the tree** (`tree_policy`, on): +0.86 of a
  round's share, replicated, at the shipped budget (§5p). It costs ~11x a move (~2 s natively), which
  the latency decision allows; the browser build leaves it off until measured there.
- **Conventions are a price, not a score** (§5u). The researched Swiss conventions
  (`krass_jass/convention.py`) may choose any move the search rated within **0.01** of a round's share
  of its best, never one it barely explored. That is free (50.03%, p = 0.86) and makes the partner play
  the card a Swiss player expects in 73% of convention decisions (59% for the search alone); 0.02 cost
  half a point. They are *played*, not yet *read*: the play model the beliefs and the tree policy see
  the table through was fitted without them.
- **The play model reads the conventions now** (§5w). Refitted to 12,000 rounds of self-play in which
  every seat plays them, it agrees with the search on 65.2% of decisions (61.4% before) and is worth
  **+0.45** of a round's share, replicated. Re-take it whenever how the bots play changes.
- **Networks, on this hardware, are closed** (`docs/neural-plan.md`). A policy network replacing the
  search is 4 points weaker (§5s); a value network at its leaves is null at a small budget and a
  costly, non-significant lean at the shipped one (§5t). Both gains of this stretch came from
  modelling *how the other seats play*, not *what a position is worth*.
- The gap to a bot that sees every hand is ~7 points of a round's share. Strategy fusion is only
  ~0.7 of it (§5h); **belief accuracy is the largest lever** (§5k). Weighting imagined deals by
  the other seats' plays and bid under a learned play model is worth +1.3, replicated (§5o).
- Greedy is statistically indistinguishable from random even with trump held constant.
  Keep it as a floor, never cite it as a meaningful rung.
- **M5 as written needs rethinking.** It distils a high-budget teacher for serving speed;
  speed is not the problem and the teacher is not stronger. The version worth building gets
  *past* DMCTS rather than compressing it.

**Search**
- `krass_jass.agent.DmctsAgent` is the agent; the search itself is in `rust/`.
- The exact endgame solver is **off** (`endgame_cards = 0`): a perfect-information solve inside
  each imagined deal is strategy fusion, and removing it was worth +1.71 (§3e). Kept behind the
  flag because it is still right for a search that votes.
- Beliefs are **weights on a pool of consistent worlds** (`rust/src/belief.rs`), never removals:
  exact constraints (voids, shown Weis, called Weis) filter; models only weight. Keep the pool's
  effective sample size in the hundreds — the shared tree needs ~300+ distinct worlds (§5h).
- Priors that tilt *which* worlds are dealt measured null on the voting search and **negative** on
  the shared tree (`signal_reading`, §3f). A policy prior in the selection rule is null because
  every one of ~4 legal moves is already visited hundreds of times (§5j).
- Void inference is in `voids.py` and must stay *sound* — never claim an unproven
  constraint. An unsound one does not crash, it just makes the bot quietly worse.

**Evaluation**
- Double rounds: play each deal twice with the teams swapped. Without this, A/B results
  are noise. Both halves use the **same** game seed (common random numbers) — decision
  seeds already vary by seat, and a different seed leaks back the variance the pairing
  exists to cancel.
- The cheating baseline lives in `arena/`, never in `krass_jass/`. It takes the true deal
  and must not be reachable from anything that serves a game.
- Protocol: 10 × 100 rounds, report mean % of total points and std, **paired** t-test on
  per-deal differences. Double rounds are a paired design; an unpaired test discards the
  pairing and most of the variance reduction with it.
- Disable Weis, Stöck and the match bonus in evaluation runs to cut variance.
- Keep the whole baseline ladder alive forever: random → greedy → rule-based →
  DMCTS(small) → DMCTS(large) → cheating MCTS (sees all hands; upper bound).
- A benchmark harness reporting `rounds_per_second` and `rollouts_per_second` lands in
  M1 and stays in CI. Throughput is the project's real bottleneck — measure it always.

**Rules configuration**
- Jass is full of house rules and the sources genuinely disagree. Every disputed point
  is an explicit config flag with a written-down default. Never hardcode a variant.
- Weis is behind a flag: on for human play, off for bot-vs-bot evaluation. It is the
  largest source of rule bugs and scoring variance.
- The legal-move generator is the highest-risk function in the codebase — trumping is
  always allowed even when you can follow suit, the strict undertrump rule applies, and
  the Puur (trump Jack) is exempt from following a trump lead. Property-test it against
  an independently written naive reference implementation.

**Licensing**
- `jass-kit-py` is GPL-3.0. Test-only oracle at most; keep it out of the runtime
  dependency graph.
- `pyschieber` is the other cross-check dependency; its licence has not been checked.
  Check it before importing it anywhere, including tests.

---

## Conventions

- Type hints throughout; Pydantic models are the wire contract between services.
- Tests: pytest + Hypothesis for the rules engine. Rules code is not "done" without
  property tests.
- Pinned lockfile; `pip-audit`/Trivy in CI.
- Containers: non-root, read-only rootfs with tmpfs scratch, `no-new-privileges`,
  dropped capabilities, pinned base image digests. Only `web` publishes a port.
- Keep the training and arena containers out of the serving compose file. Different
  lifecycle, different resource profile.

---

## Milestones

| | | |
|---|---|---|
| M0 | Decisions | Lock rule variants, target strength, latency budget, Weis scope, game length |
| M1 | Engine + tests | Bitboard state, legal moves, scoring, property tests, benchmark harness |
| M2 | Playable loop | FastAPI + WebSocket + random bots in containers; mobile card-fan component |
| M3 | Rule-based bot + arena | Rule-based trump selection; tournament harness with double rounds |
| M4 | Search | Void tracking, determinization, ISMCTS; beliefs from play, bid and Weis. Endgame solver built, measured harmful, off |
| M5 | Distillation | High-budget self-play → Parquet → policy/value net → ONNX → served. **Gated:** needs a teacher ~100× the serve budget, so it needs a native rollout loop first. If throughput isn't there, ship DMCTS directly and skip M5. |
| M6 | Polish | Debug/replay UI, security pass, difficulty levels (= search budget) |

Success criterion for M5: the network at ~1ms/move stays within 1% of points against
high-budget DMCTS.

---

## Things the research already settled — don't rediscover them

From the Fribourg/HSLU work on this exact variant (sources in `PLAN.md`):

- DMCTS and a supervised network are roughly equally strong; both beat rule-based
  agents and ISMCTS. **Search first, learning second.**
- Sweet spot for a 800k-rollout budget: ~1000 determinizations × 800 iterations.
  More than ~1000 determinizations stops helping. Exploration constant ≈ 1.5.
  **Only half reproduced.** On the voting search ours saturated near 2,400 iterations; on the
  shared tree that replaced it the budget pays to ~153,600 and is flat after (§3, §3b). Do not
  delete their number; do not treat ours as universal.
- ~25 random rollouts plateaus; 100 MCTS iterations beat 1000 random rollouts. Don't
  spend budget on flat Monte Carlo.
- **Negative result:** sampling determinizations from a learned card-distribution model
  did *not* beat uniform random sampling. It mostly added variance.
  **Reproduced with a non-learned prior.** `krass_jass/reading.py` reads the discard
  convention the table is deliberately playing and tilts sampling by a bounded factor (no
  world removed). Also worth nothing: two nulls and one p=0.049 that did not replicate
  (`docs/measurements.md` §5c), and on the shared tree it is a measured *loss* (§3f). Off by
  default, behind `DmctsAgent.signal_reading` and `READ_SIGNALS` in `wasm_api.rs`. What did
  work is different in kind: weighting whole worlds by the likelihood of every observed play
  (§5o), not tilting per-suit sampling.
- **Negative result:** rule-based rollouts did *not* beat random rollouts in DMCTS.
- Trump selection is worth ~16 points of win rate over random, and a simple ranked
  rule-based selector captures nearly all of it. Build that before any network.
  **Reproduced:** our selector measures a 17-point spread (`docs/measurements.md` §2). Its
  hand-written weights were not near-optimal: tuned by simulation they win 58% of games (§5n).
- MCTS-based trump selection underperforms because it rarely learns to shove.

Both negative results are warnings against being clever before being fast.
