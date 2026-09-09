# krass-jass

Web app to play Schieber Jass (Swiss, 4 players, French deck): one human plus three
bot services in a Docker Compose stack. The substantial goal is training an algorithm
that plays the game well.

**Full plan, rules research and rationale: see `PLAN.md`.** Read it before starting
work on a new milestone. This file holds only the standing constraints that apply to
every session.

---

## Current state

Planning reviewed (`docs/plan-review.md`), no code yet. Next milestone is **M0**, whose
deliverable is `docs/rules-config.md` — the review found two rules errors in `PLAN.md`
(trump multipliers, Undenufe card values) that are exactly what M0 exists to catch, so
it is not skippable. M1 (engine + tests) follows.

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
- If profiling proves pure Python insufficient, escalate in this order: Numba/Cython
  on the rollout loop only → Rust core via PyO3. Do not reach for either speculatively
  for M1–M4 — but a native rollout loop is a **precondition for M5**, not a contingency
  (`PLAN.md` §3.4 cost note). So: keep the rollout loop isolated behind a narrow seam and
  free of Python objects from the first commit, so it can be swapped without touching
  anything else.
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
- Internal-only Docker network. No egress, no DB credentials, no writable volumes.
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

**Evaluation**
- Double rounds: play each deal twice with the teams swapped. Without this, A/B results
  are noise.
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
- ~25 random rollouts plateaus; 100 MCTS iterations beat 1000 random rollouts. Don't
  spend budget on flat Monte Carlo.
- **Negative result:** sampling determinizations from a learned card-distribution model
  did *not* beat uniform random sampling. It mostly added variance.
- **Negative result:** rule-based rollouts did *not* beat random rollouts in DMCTS.
- Trump selection is worth ~16 points of win rate over random, and a simple ranked
  rule-based selector captures nearly all of it. Build that before any network.
- MCTS-based trump selection underperforms because it rarely learns to shove.

Both negative results are warnings against being clever before being fast.
