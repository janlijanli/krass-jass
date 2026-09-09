# Review of `PLAN.md` and `CLAUDE.md`

Date: 2026-09-09. Reviewed at planning stage, before any code.

**Verdict:** a good plan — the research is real, the negative results are the right ones to
internalise, and `CLAUDE.md` is correctly scoped to standing constraints rather than narrative.
Worth building against. It has one structural flaw that invalidates M5 as written, four concrete
errors, and two internal contradictions. All of them have been corrected in the two documents;
this file records what was wrong and why, so the reasoning isn't lost.

---

## 1. Structural: the distillation step doesn't survive the arithmetic

This is the finding that should change the milestone plan rather than just the prose.

`docs/bench_rollout_ceiling.py` implements a deliberately *optimistic* pure-Python bitboard rollout
— precomputed suit masks, table-driven trump ordering, no undertrump rule, no Weis, no observation
building, no validation. It is a ceiling, not an estimate. On an M2, Python 3.12, single core:

```
~25,000 full rounds/sec   (~890,000 card-plays/sec)
```

Working through it:

| | |
|---|---|
| Raw rollouts/sec (a rollout is ~half a round) | ~50,000 |
| With MCTS tree overhead (nodes, UCT, backprop — typically 2–4×) | ~12,000–25,000 |
| Tuned budget from the literature | 800,000 rollouts/move |
| → time per move at the tuned budget | **30–65 seconds** |
| → rollouts available at a 1.5s serve budget | ~20,000–35,000, i.e. **~3% of tuned** |

`PLAN.md` §1.5 knows Python is slow. It never lands the consequence, which is in §3.4:

A distillation corpus needs roughly 1M decisions ≈ 28k rounds × 36 decisions.

| Teacher budget | Core-hours | Wall-clock on 8 cores |
|---|---|---|
| 30 s/move (§3.4's original "minutes/move") | 8,400 | **44 days** |
| 10 s/move | 2,800 | 15 days |
| 5 s/move | 1,400 | 7 days |

So the affordable teacher is ~5 s/move — **only 3–7× the compute of what you could serve directly**
at 1.5s. In MCTS that gap is worth perhaps 1–3% of points. Distillation pays when the teacher has
100–1000× the student's search; at 3–7× it buys close to nothing over simply serving DMCTS.

Separately, the ~28k-round corpus you can afford is **65× smaller** than the 1.8M human rounds that
produced the published 0.78 policy accuracy. `PLAN.md` flags that you lack the human corpus but
never costs out the replacement.

> **Update, M1 complete.** The real engine is *faster* than the probe — 39,000 rounds/sec and
> 72,000 mid-round rollouts/sec, because trick resolution became a table lookup. That puts the tuned
> budget at **11s per move before any MCTS tree overhead**, so 22–44s once search is wrapped around
> it. The corpus figures above are expressed in seconds-per-move and are unchanged; the
> teacher/student ratio at an affordable teacher is still ~3×. **The conclusion stands.**
> `bench/benchmark.py` now reports this on every CI run.

**Consequences, now written into both documents:**

- Numba/Cython/Rust on the rollout loop is a **precondition for M5**, not a contingency. Both
  documents previously framed it as speculative escalation to avoid. That framing is right for
  M1–M4 and wrong for M5.
- Because of that, the rollout loop needs its own narrow seam and no Python objects **from the
  first commit**. That is a module-boundary decision made before code, not after profiling.
- M5 now carries an explicit entry condition: if measured throughput can't support a teacher ~100×
  the serve budget, ship DMCTS directly and skip M5.

Two things that survive intact and deserve promotion:

- **The exact endgame solver (≤5 cards) is the best compute-per-line in the project.** It removes
  the last 3–4 tricks from the search budget entirely.
- **Table-driven legal-move generation** — 9 bits per suit → 512 entries, keyed on
  `(led_suit, trump, per-suit hand masks, trumped_yet)` — is the concrete Python accelerant the plan
  was missing. Worth 3–5× over branching logic. Added to `CLAUDE.md`.

---

## 2. Concrete errors

### 2.1 Trump multipliers were wrong (§2.2) — **fixed**

The plan had ♣♠ = ×1 and ♥♦ = ×2. The German→French mapping is Eichel↔♣, Rosen↔♥, Schilten↔♠,
Schellen↔♦, and the ×1 pair is Schilten + Schellen. Correct grouping is **♠♦ = ×1, ♣♥ = ×2** —
clubs and diamonds were swapped. Verify against pagat when writing `docs/rules-config.md`.

### 2.2 Undenufe card values were wrong (§2.1) — **fixed**

The table merged Obenabe and Undenufe into one column with Ace = 11 marked "(Obenabe)". In Undenufe
the values invert along with the order: **the 6 is worth 11 and the Ace 0.**

The dangerous part: both contracts total 38/suit × 4 = 152 (+5 = 157) either way, so a
"points sum to 157" test will **not** catch this. It would silently mis-score every Undenufe hand.
Test per-card values directly. The table now has separate columns and carries that warning.

### 2.3 Wrong statistical test (§4) — **fixed**

The plan specified double rounds — a *paired* design, correctly identified as the difference between
a usable A/B test and a coin flip — and then specified an **unpaired t-test**, which discards the
pairing and with it most of the variance reduction. Now a paired t-test on per-deal differences.

### 2.4 Everything else checks out

All five combinatorics figures are correct to the digits given: 36! ≈ 3.72e41, deals ≈ 2.15e19,
unseen distributions from one seat ≈ 2.28e11, C(36,9) = 94,143,280, and 1.16e28 follows. Card values,
152 + 5 = 157, trump order, the undertrump rule, the Puur exemption, Stöck, anticlockwise play — all
correct. The Weis structure is right, and treating 5+ = 100 as the small-Weis default is a defensible
house choice given it sits behind a flag.

---

## 3. Internal contradictions

### 3.1 Determinism vs. the information boundary — **resolved**

These two constraints were mutually exclusive as written:

- *"All RNG — deal, determinization, rollouts — derives from one game seed. Any game replays
  bit-for-bit."*
- *"no RNG seed"* in the observation (`PLAN.md` §5.2, threat T1).

The bots are stateless services that do their own determinization and rollouts. With no seed
reaching them, **bot decisions are not reproducible and no game replays bit-for-bit** — losing one
of the plan's stated highest-value debugging properties.

Resolution now in both documents: the engine sends
`decision_seed = HMAC(game_seed, game_id ‖ seat ‖ round ‖ trick)` in each observation. Derived, not
invertible, independent of any hidden card. The rule is narrowed from "no RNG seed" to "no *game*
seed" — that distinction matters, because the game seed determines the deal, so a bot holding it can
reconstruct every hand at the table.

### 3.2 T5 "no volumes" vs. serving model weights — **resolved**

M5 ships an ONNX model to the bot container, but T5 forbade volumes and egress, leaving no stated
delivery path. Now: weights are baked into the image, the image tag carries `MODEL_VERSION` (which
also makes that env var honest), and a single read-only bind mount is named as the one permitted
exception.

### 3.3 Milestone bookkeeping — **fixed**

`CLAUDE.md` said "next milestone is M1" while M0's deliverable, `docs/rules-config.md`, did not
exist. Since §2.1 and §2.2 above are precisely the class of error M0 exists to catch, M0 is not
skippable. `CLAUDE.md` also said two decisions were open where `PLAN.md` §9 lists six; it now points
at the full list.

---

## 4. Still missing before the first commit

Not fixed here — these are decisions, not corrections.

- **Repo layout and module boundaries.** The most conspicuous gap for a repo about to be populated,
  and given §1 above, where the rollout-loop seam sits is the most consequential early decision.
- **Game state machine, session resume, concurrency model.** Nothing written on any of them. One
  game per process? asyncio? What happens when a WebSocket drops mid-trick?
- **CI definition.** `CLAUDE.md` names four things that must run in CI (observation fuzzing,
  property tests, the benchmark harness, the nightly ladder) but nothing defines the pipeline.
- **No Stöck in no-trump contracts** — there is none; worth stating explicitly so nobody implements
  it.
- **`pyschieber` licence unchecked.** `jass-kit-py` is correctly flagged GPL-3.0, but the other
  cross-check dependency was never examined. Check before importing it anywhere, tests included.
- **Python version pin.** The default `python3` on this machine is 3.9 and is **48% slower** on this
  workload (16.8k vs 24.9k rounds/sec). Pin ≥3.12. Noted in `CLAUDE.md`; still needs to land in
  packaging.

---

## 5. Changes applied

`PLAN.md`

- §2.1 — split the Obenabe/Undenufe column; Undenufe 6 = 11, A = 0; added the "157 test won't catch
  this" warning
- §2.2 — corrected multiplier suit groups to ♠♦ = ×1 / ♣♥ = ×2, with the German→French mapping spelled out
- §3.4 — added the costed throughput note and the M5 precondition
- §4 — unpaired → paired t-test
- §5.2 — added `decision_seed` to both endpoints; documented why identity fields are absent; stated
  that the agent is a library and self-play does not go over HTTP
- §6 — reconciled bit-for-bit replay with the information boundary via the derived seed
- §7 — T5 now specifies how model weights reach the bot
- §8 — M5 gained an explicit entry condition

`CLAUDE.md`

- Current state → M0, with the reason; open decisions now point at `PLAN.md` §9
- Engine → native rollout loop as an M5 precondition, the rollout seam, table-driven legal moves,
  Python ≥3.12
- Information boundary → "no game seed", identity fields, the `decision_seed` exception
- Bots → agent-as-library, weights baked into the image, "no *writable* volumes"
- Determinism → the derived-seed mechanism
- Evaluation → paired t-test
- Licensing → `pyschieber` unchecked
- Milestones → M5 gate

`docs/bench_rollout_ceiling.py` — new; the throughput probe behind §1.
