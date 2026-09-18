# Neural networks: what to build, how to test it, and what would kill each idea

Written 2026-09-16, after the belief work saturated (`docs/measurements.md` §5r). This is a plan,
not a result. It exists because "add a neural network" is under-specified in a codebase that has
already measured three obvious placements at nothing, and the cheapest way to waste a fortnight
here is to rebuild one of them.

Read `docs/engine-report.md` first for the protocol and the numbers this plan leans on.

---

## 1. What this codebase already knows about networks

| placement | measured | why |
|---|---|---|
| learned **value** replacing the random playout | **−9 points** (§5g) | the playout's error is zero-mean and averages away over thousands of samples to ~0.02; a fitted evaluator's error is bias and survives. A drop-in needs RMSE < 0.02 on a quantity with SD ~0.3 |
| learned **policy prior** in PUCT | null on three seeds (§5j) | 4.2 legal moves, each already visited ~570 times at 2,400 iterations. A prior allocates attention; this search has none to allocate |
| learned **belief** over card locations | null in play (§5q) | marginals per card; the search already reads the table through play likelihoods |
| a **better play model** for those likelihoods | null in play (§5r) | the belief channel is saturated |

Two conclusions carry into any network work here:

1. **A network cannot enter as a component of the current search.** Value, prior and belief are all
   taken, measured, and dead. What is left is a network that *replaces* the search, or that changes
   the search's shape (fewer simulations, different aggregation).
2. **Offline metrics do not forecast points.** Four offline gains of the same size produced one real
   gain (§5r). Every gate below is therefore a *match*, and offline numbers only decide whether a
   match is worth running.

---

## 2. Four candidates, cheapest first

### A. Distil the search into a policy network (a fast bot, not a stronger one)

Train `π(card | observation)` on the search's own decisions, then play it **without search**.

- **Data:** already recorded — 311,683 decisions with per-move visit counts from 12,000 rounds
  (`arena/policy_data.py`), plus 161,850 older ones. Visit distributions are the soft targets.
- **Why it might work where §5j did not:** §5j asked a prior to *steer* a search that needed no
  steering. This asks a network to *be* the player. Published Jass work reports a supervised network
  roughly on par with determinized search, and the M5 success criterion was written for exactly this.
- **What it buys:** difficulty levels, a mobile-cheap bot, and the student half of expert iteration —
  not strength.
- **Offline gate:** top-1 agreement with the search ≥ 70% on held-out rounds (the linear play model
  reaches 63.5% with 36 features, so a real network should clear this).
- **Match gate:** within 1% of the shipped search's points at ~1 ms per move (the M5 criterion), and
  it must beat `greedy` and `random` by the ladder's usual margins.
- **Cost:** hours on CPU. This is the one to do first, because it produces the artefacts every later
  idea needs: an encoder, a Rust inference path, and a trained policy.

> **A is done, and it stops here.** Flat head 51.0% top-1 and 7.6 points below the search;
> action-conditioned 60.3% and 4.0 points below, against a 70% / 1% pair of gates
> (`docs/measurements.md` §5s). The shape fix was worth +9 points of agreement, the data is now the
> binding constraint, and the remedy — ~100× more self-play — buys a cheaper bot rather than a
> stronger one. What it leaves behind is worth keeping: a search-free agent at 0.18 ms a move that
> beats greedy by 18 points, i.e. the difficulty levels M6 asks for.

### B. A value network for a *small* search

§5g killed the value network at 2,400+ iterations. The argument does not hold at 100–200 iterations,
where each leaf is visited a handful of times and playout noise no longer averages out.

- **Shape:** value head on the same encoder as A, trained on realised round outcomes from the same
  self-play, labelled with the round's share on the search's own reward scale.
- **Offline gate:** RMSE against the *true* round outcome better than a k-sample playout at the same
  cost (k ≈ 3–10), not against the playout's mean — §5g's target was the playout's mean, which is why
  it looked promising and measured awful.
- **Match gate:** search at 2,400 iterations with the value head beats search at 2,400 with playouts,
  **at equal wall-clock**, and ideally the pair (small search + net) beats the shipped 153,600 search
  at equal time. That last one is the only version that matters for strength.
- **Kill criterion:** if the value head cannot beat playouts at 2,400 iterations at equal time, the
  whole "network inside the search" family is closed here and B–D stop.

> **B is done, and the kill criterion fired.** Offline the network beat one random playout (RMSE
> 0.188 against 0.210) but not four (0.159). In play: 49.85% at 2,400 iterations (p = 0.39) — the
> criterion — and 50.40% at 153,600 (p = 0.068) at 1.6× the cost per move (`docs/measurements.md`
> §5t). The network line is closed on this hardware.

### C. Expert iteration (the first thing that could make it *stronger*)

Alternate: search with the network as prior and value → record decisions → retrain → repeat.

- **Why it is different from §5i/§5j:** those measured a prior inside a large search. Here the search
  is deliberately *small* (a few hundred iterations), so the prior decides what is examined at all,
  and the value decides what leaves are worth. The literature's successful systems are shaped this
  way, not as a prior bolted onto a large search.
- **Loop:** ~50k–200k self-play rounds per iteration at the small budget, retrain, re-measure.
- **Gate per iteration:** the new network must beat the previous one by ≥ +0.5 of a round's share at
  equal time, on 2,000 deals, or the loop stops. Two consecutive iterations below that ends it.
- **Cost:** days on CPU per iteration; hours on a GPU. This is where the GPU question binds.

### D. Perfect-information distillation (PTIE) — the partner-play idea

Train with a critic that sees all four hands, play with one that does not (PerfectDou's framing;
Suphx's oracle guiding is the same trick with a decayed oracle feature set). This is the only
candidate that addresses the thing our measurements say is *not* a belief problem: partner play, and
the ~7-point gap that better sampling cannot reach.

- **Why here:** we already have a cheating agent, an oracle-belief harness (`arena/oracle.py`) and a
  fully deterministic self-play engine, so the perfect-information critic is free.
- **Risk:** it is an RL loop over millions of games. On CPU only, this is not realistic; with a GPU
  it is a fortnight-scale project with a real chance of nothing.
- **Gate:** same as C, plus a partner-play check — the bot must not get *worse* as a partner to a
  differently-configured bot, which is how a self-play agent usually fails.

---

## 3. The encoder, written once

All four share an input. Keep it to what `build_observation` returns, relative to the acting seat:

| plane group | size | note |
|---|---|---|
| own hand | 36 | |
| played by each seat, relative | 4 × 36 | who has played what |
| led / followed / discarded / ruffed, relative | 4 × 36 each | the shape `beliefnet.rs` already computes |
| current trick, by position | 3 × 36 | |
| legal moves | 36 | the mask, also applied to the output |
| proven voids, shown Weis cards | 3 × 36 each | exact constraints |
| called Weis per seat | 3 × 6 | bucketed |
| contract, declarer, forehand, shove | ~15 | one-hot |
| trick number, points so far, game score | ~6 | |

≈ 900 inputs, which is what `rust/src/beliefnet.rs` already builds — **reuse `rs_belief_features`
rather than writing a second encoder**, extending it where a plane is missing. The project has twice
been saved by having one feature function and a test that Rust and numpy agree on it; keep that.

Output: 36 logits masked by the legal moves, plus (for B–D) one scalar value.

Size: 900 → 256 → 256 → 37 is ~300k parameters. At the measured rates in `docs/value-net-plan.md`
that is tens of microseconds per call natively — irrelevant next to a 153,600-iteration search, and
affordable at 1 ms/move for A.

---

## 4. How it gets implemented here

- **Training in Python.** numpy is enough for A and B (the belief network trained in minutes). C and
  D want PyTorch; that decision follows the GPU answer.
- **Inference in Rust**, like `playmodel.rs` and `beliefnet.rs`: a plain matmul, no ONNX runtime, no
  new dependency in the serving path. Deterministic by construction, which the replay guarantee needs.
- **Weights as a file both sides read.** JSON stops being sensible at 300k parameters (~4 MB); switch
  to a binary blob of `f32`/`f16` with a small JSON header, `include_bytes!` on the native build and
  **excluded from wasm** unless the browser bot uses it — the belief network already sets that
  precedent (the wasm build gets an empty stand-in).
- **Data as Parquet** once a run exceeds a few hundred thousand decisions (`CLAUDE.md`); `.npz` is
  fine below that and is what the current recorders write.
- **Agent surface:** a `net` kind alongside `random`, `greedy`, `dmcts`, so `arena/ab.py`,
  `arena/ladder.py` and the bot service reach it without special cases.

---

## 5. How it gets tested

Nothing changes about the protocol — that is the point.

1. **Unit:** Rust inference and the numpy model agree to < 1e-4 on a few hundred held-out positions.
   Both existing models have this test; it has caught real bugs.
2. **Information boundary:** the encoder is fed only from an observation, and a test swaps hidden
   cards and asserts the inputs do not move (`tests/test_belief_net.py` does this already).
3. **Offline:** held-out top-1 and cross-entropy for policy; RMSE against realised outcomes for value.
   These decide only whether to spend a match.
4. **Match:** `arena/ab.py`, double rounds, paired t-test, 2,000 deals, `HOUSE`, and **equal
   wall-clock** whenever the network costs more per move. The power table in `docs/engine-report.md`
   §2 says what each sample size can resolve: 2,000 deals detect ~0.4 of a round's share.
5. **Replication** on a fresh seed before anything becomes a default. Six borderline results have
   died on this step; two survived it and shipped.
6. **Ladder:** any network agent joins `arena/ladder.py` permanently — random, greedy, rule-based,
   search, network, cheating.
7. **Whole games** (`arena/games.py`) for anything that trades points for position, and for the
   headline number a person cares about.

---

## 6. Order, and what would stop it

```
A (distil a policy)  →  B (value in a small search)  →  C (expert iteration)  →  D (PTIE / RL)
        ↓ fails: no network plays this game well at all — stop
                     ↓ fails: nothing learned belongs inside this search — stop after A
                                        ↓ two flat iterations — stop
```

A is worth doing regardless: it gives difficulty levels and a mobile bot even if it is weaker than
the search. B is the real fork — it decides whether the "network inside a search" family is alive
here at all, and it is cheap because the data exists. C and D only start if B pays.

**What the plan does not promise.** Everything in §1 says the easy placements are exhausted, and the
published Jass work puts a supervised network roughly *level* with determinized search, not above it.
The honest expectation for A is parity at a fraction of the compute, for B a small gain at small
budgets, and for C/D an unknown with a real chance of nothing — bought with days of compute.

---

## 7. The hardware answer, and what it settles

`CLAUDE.md` carried "CPU-only or GPU?" as an open decision since M0. **Answered 2026-09-16: CPU only,
this Mac, 8 cores.**

So the plan is **A, then B, then stop**. C (expert iteration) is a week of compute per iteration
here, and each iteration has to clear +0.5 of a round's share to continue — a bad ratio to start a
loop on. D (perfect-information RL) is out of reach without a GPU and stays written down rather than
attempted.

That also sets what "success" means for this work: **A is about cost, not strength** — a bot that
plays near the search's level at ~1 ms a move buys difficulty levels and a mobile-cheap opponent —
and **B is the only shot at strength**, and only at small budgets, where playout noise still
dominates. If B is null, the network line is closed here and the honest next lever is human data
(`docs/engine-report.md` §10), not more learning against ourselves.
