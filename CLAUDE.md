# krass-jass

Web app to play Schieber Jass (Swiss, 4 players, French deck): one human plus three
bot services in a Docker Compose stack. The substantial goal is training an algorithm
that plays the game well.

**Full plan, rules research and rationale: see `PLAN.md`.** Read it before starting
work on a new milestone. This file holds only the standing constraints that apply to
every session.

---

## Current state

**M0, M1 and M4 are done.** Rule variants locked in `docs/rules-config.md`; the engine and
its property tests are in; the search is Rust; DMCTS with void tracking and an exact
endgame solver plays through `krass_jass.agent`, measured by `arena/`.

**M3 is partly skipped and owes work:** there is no trump selection yet, so the arena
picks a contract at random per deal. `PLAN.md` §3.1 puts rule-based trump selection at
~16 points of win rate — the largest single gain still on the table. Do it before tuning
anything else.

Next is **M2 (playable loop)** — FastAPI + WebSocket + bots in containers, and the mobile
card-fan component, which `PLAN.md` §5.1 says to prototype before the rest of the layout.

**The search is Rust** (`rust/`, exposed via `krass_jass.native`). Measured: 1.48M DMCTS
iterations/sec single-core, 6.19M on all cores — 42x the Python search. The tuned 800k
budget is 0.13s per move. Python remains the engine of record; only the search moved.
`bench/benchmark.py` reports both in CI.

Decisions still open. `PLAN.md` §9 has the full list of six; these two block architecture:

- **Latency budget per bot move.** Determines whether DMCTS alone is shippable or
  whether distillation to a network (M5) becomes mandatory before the app is playable.
- **CPU-only or GPU.** Determines whether M5 is a weekend or a fortnight, and whether
  the RL loop is realistic at all.

Do not design around an assumed answer to either. Ask.

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
- Search saturates near 2,400 iterations. Serve budget is not a constraint — 2,400
  iterations costs single-digit milliseconds and is indistinguishable from 800,000.
- The gap to a bot that sees every hand is ~6% of points, and **search does not close it**.
  That is the strategy-fusion ceiling and the target for everything after M4.
- Greedy is statistically indistinguishable from random even with trump held constant.
  Keep it as a floor, never cite it as a meaningful rung.
- **M5 as written needs rethinking.** It distils a high-budget teacher for serving speed;
  speed is not the problem and the teacher is not stronger. The version worth building gets
  *past* DMCTS rather than compressing it.

**Search**
- `krass_jass.agent.DmctsAgent` is the agent; the search itself is in `rust/`.
- The endgame solver **replaces** the search once hands are small, it does not decorate it.
  A 5-card solve costs ~3ms; running one per MCTS leaf would cost 40 minutes a move.
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
| M4 | DMCTS | Void tracking, determinization, UCT, exact endgame solver (≤5 cards) |
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
  **This did not reproduce.** Our sweep saturates near 2,400 iterations; 333× more compute
  is worth nothing measurable. Three candidate explanations were tested and two are gone —
  it is not the endgame solver and it is not the missing trump selector
  (`docs/measurements.md` §3). Their figure may be budget *allocation* guidance rather than
  a required total. Do not delete their number; do not treat ours as universal.
- ~25 random rollouts plateaus; 100 MCTS iterations beat 1000 random rollouts. Don't
  spend budget on flat Monte Carlo.
- **Negative result:** sampling determinizations from a learned card-distribution model
  did *not* beat uniform random sampling. It mostly added variance.
- **Negative result:** rule-based rollouts did *not* beat random rollouts in DMCTS.
- Trump selection is worth ~16 points of win rate over random, and a simple ranked
  rule-based selector captures nearly all of it. Build that before any network.
  **Reproduced:** our selector measures a 17-point spread (`docs/measurements.md` §2).
- MCTS-based trump selection underperforms because it rarely learns to shove.

Both negative results are warnings against being clever before being fast.
