# krass-jass — Project Plan & Research

Status: the plan as written before any code (kept as the record of the reasoning). What was built
and measured since is in `docs/engine-report.md` (summary) and `docs/measurements.md` (dated
record); where they disagree with this file, they win — several recommendations below, including
the budget figure and ISMCTS being "measured worse", did not hold on this engine.
Scope: web app to play Schieber Jass (4 players, French deck) against 3 bot services, plus a training pipeline for the bot algorithm.

---

## 0. Executive summary

Three things are true and they shape everything else:

1. **Exhaustive search is impossible.** ~1.16e28 states after the deal; from one seat there are ~2.28e11 possible distributions of the unseen 27 cards. You will sample, not enumerate.
2. **You do not need machine learning to get a strong bot.** Determinized MCTS (DMCTS) with no learned component already plays at the level of experienced amateur teams. Learning is the *second* step, and its main job is making that strength cheap enough to serve in a web request.
3. **Your real bottleneck is simulation throughput, not model architecture.** A pure-Python engine will not deliver the rollouts you need. Decide the engine representation before writing anything else.

The recommended path: **rules engine → rule-based + DMCTS baselines → self-play data from a slow high-budget DMCTS → distil into a small network for fast serving → optional RL loop.**

---

## 1. Critique of the brief

You asked for this, so — bluntly.

### 1.1 "Three artificial players, each at best a single service"

Right conclusion, partly wrong reason.

Process isolation does **not** give you the security property you think it does. The property you want is *no agent ever receives information it shouldn't have*, and that is enforced by the **observation builder in the game engine** — the code that decides what goes into the payload. If that function is wrong, three containers don't save you; each container just receives leaked data over HTTP instead of a function call.

Separate services are still worth it, but for different reasons:

- **Benchmarking.** You can run bot version A in seats 0/2 and version B in seats 1/3 and get a clean head-to-head. This is the single most valuable thing about the split.
- **Resource isolation.** MCTS is CPU-bound; you can pin cores, cap CPU per container, enforce hard timeouts.
- **A stable contract.** A REST/gRPC bot interface lets you plug in third-party bots later (the HSLU/Zühlke Jass ecosystem has an established REST bot interface you could mirror).

**Recommendation:** one bot image, three replicas, stateless, configured by env var (`AGENT_KIND`, `SEAT`, `TIME_BUDGET_MS`, `MODEL_VERSION`). Not three codebases. Not stateful services — the engine sends the full observation each turn, the bot answers and forgets.

### 1.2 "No data exchange between users like in the real game"

Correct at the transport level, but be aware what you're signing up for: in the real game there *is* information exchange within a team — via play style. Schmieren (dumping high-value cards into a partner's trick), leading your strong suit, pulling trumps early. That is the interesting and hard part, and it's exactly where bots are still visibly worse than good humans. Research participants specifically noted bots not following signalling conventions. *(2026-09-19: the bots now play the researched Swiss conventions wherever the search rates the convention's card within 0.01 of a round's share of its best — free, and three convention decisions in four go the way a Swiss partner expects. Reading them back is the open half. `docs/measurements.md` §5u, `docs/engine-report.md` §5.4.)* You are choosing the hard version of the problem. That's fine — just don't be surprised when your bot's *individual* play is good and its *team* play is mediocre.

### 1.3 "Calculating all possibilities with 36 cards"

No. Concretely:

| Quantity | Size |
|---|---|
| Orderings of 36 cards (game-tree paths) | 36! ≈ 3.7e41 |
| Ways to deal 36 cards into 4 hands of 9 | ≈ 2.15e19 |
| Distributions of the 27 unseen cards, from one seat | ≈ 2.28e11 |
| Legal playouts × distributions (states after deal) | ≈ 1.16e28 |
| Distinct 9-card hands (for a trump-selection table) | C(36,9) = 94,143,280 |

Two useful nuances:

- **The endgame is exactly solvable.** With ≤ 5 cards per hand, a perfect-information double-dummy solve is cheap. Bolt an exact endgame solver onto the search and the last 3–4 tricks become optimal for free. Published results show bot differences shrink late in the round anyway — this is why.
- **The trump-selection space is small enough to be interesting.** 94M distinct hands is too many to evaluate well, but it's small enough that a *feature-based* table or a tiny network nails it. Trump selection is worth treating as a separate, much easier subproblem.

### 1.4 "Store best practices — maybe a database?"

Wrong artifact. A table of positions cannot generalise over 1e28 states; you will never hit the same position twice. What you actually store:

| Thing | Where | Why |
|---|---|---|
| Model weights | Object store / volume, versioned | This *is* your "stored best practice" |
| Self-play game records | Parquet files on disk/MinIO | Millions of rows, read sequentially for training. Not a Postgres workload. |
| Finished human games, decision traces | Postgres | Small volume, queried by game_id, needs relations |
| Evaluation results (bot A vs bot B) | Postgres | Small, you'll query it constantly |
| Trump-selection heuristic table | A YAML/JSON file in the repo | Tiny, hand-tunable, reviewable in git |

Do not put 10M card decisions in Postgres rows and expect a training loop to read them at speed.

### 1.5 "Stack shall be Python where possible"

This is the risk that will actually bite you.

Published DMCTS tuning found the sweet spot around **1000 determinizations × 800 MCTS iterations per move** — 800k rollouts *per card played*. That was Java. A 10K×10K configuration was estimated at 600 hours on an 8-core machine. Naive Python is roughly 30–100× slower than that.

Options, in the order I'd try them:

1. **Bitboard engine.** Represent a hand as a 36-bit integer, suits as masks. Legal-move generation, trick evaluation and scoring become bit ops. This alone is worth 10–50× over an object-oriented card model, and it's still pure Python.
2. **Numba or Cython on the rollout loop only.** Keeps 95% of the codebase Python.
3. **Rust core via PyO3** for the engine + rollout, Python everywhere else. Still "Python where possible" in any honest reading.

**Do this in week one:** write a benchmark harness that reports `random_rounds_per_second` and `rollouts_per_second`, and put it in CI. If you can't measure throughput you can't make this decision.

Also: your web-facing latency budget is maybe **1–2 seconds per bot move**, not 10. Three bots × 9 tricks × 10s = ~4.5 minutes of thinking per round; nobody will play that. This is the concrete reason you need the distillation step: a network gives DMCTS-comparable strength at ~1ms inference.

### 1.6 "App shall be secure, security by design"

Too vague to act on. "Security by design" without a threat model is a wish. Write the threat model first (§7) — it's half a page and it will change your architecture.

### 1.7 What's missing from the brief

- **Target strength.** "Beats a casual player" and "beats a club player" are different projects.
- **Latency budget per bot move.** See above.
- **Is Weis in scope?** This is the biggest decision you haven't made — see §2.3.
- **Game length.** A game to 3000 points is ~12 rounds. That's a long web session. Consider single-round or to-1000 modes.
- **Multiplayer?** Assumed no (1 human, 3 bots). If you ever want 2 humans, decide now, because it changes session/state handling completely.

---

## 2. Rules research: Schieber Jass

Sources: pagat.com (Schieber + general Swiss Jass rules), Swisslos rule pages. Note these disagree on details — Jass is full of house rules. **Every disputed point below must become an explicit config flag, defaulted, and written down.**

### 2.1 Deck and card values (French suits)

36 cards: A K Q J 10 9 8 7 6 in ♥ ♦ ♠ ♣, nine per player, dealt in threes.

| Rank | Non-trump | Trump | Obenabe | Undenufe |
|---|---|---|---|---|
| Ace | 11 | 11 | 11 | **0** |
| King | 4 | 4 | 4 | 4 |
| Queen (Ober) | 3 | 3 | 3 | 3 |
| **Jack (Under / "Puur")** | 2 | **20** | 2 | 2 |
| 10 (Banner) | 10 | 10 | 10 | 10 |
| **9 ("Näll")** | 0 | **14** | 0 | 0 |
| 8 | 0 | 0 | **8** | **8** |
| 7 | 0 | 0 | 0 | 0 |
| 6 | 0 | 0 | 0 | **11** |

152 in the cards + **5 for the last trick = 157 per round**. Match (all nine tricks) = +100 → 257.
In no-trump contracts the 8s are worth 8 to compensate for the missing Puur/Näll, keeping the total at 157.
**Undenufe inverts the values along with the order:** the 6 is worth 11 and the Ace 0. Both no-trump
contracts still total 38 per suit → 152 + 5 = 157, so a "points sum to 157" test will *not* catch a
mis-implemented Undenufe. Test the per-card values directly.

Card order — trump: **J > 9 > A > K > Q > 10 > 8 > 7 > 6**. Non-trump: A > K > Q > J > 10 > 9 > 8 > 7 > 6.
Undenufe: order fully reversed, **6 highest, A lowest**.

### 2.2 Bidding and multipliers

Forehand either picks a contract or **shoves** (*schiebt*) to their partner, who must then choose.

| Contract | Multiplier |
|---|---|
| Two "cheap" suits — Schilten/Schellen = **♠ ♦** | ×1 |
| Two "dear" suits — Eichel/Rosen = **♣ ♥** | ×2 |
| Obenabe (no trump, high→low) | ×3 |
| Undenufe (no trump, low→high) | ×4 |

The multiplier applies to **everything** in the hand: trick points, Weis and Stöck.

The German→French suit mapping is the thing to get right here: Eichel↔♣, Rosen↔♥, Schilten↔♠,
Schellen↔♦. The ×1 pair is Schilten + Schellen, i.e. **spades and diamonds** — not spades and clubs.

*Config flags:* `allow_zurueckschieben` (shove back — default off), `multipliers` (some houses play all ×1 with a 1000 target).

### 2.3 Weis and Stöck — the complexity bomb

**Weis** are card combinations announced during the first trick.

Small Weis (recommended default):
- Sequence of 3 in a suit: 20 · Sequence of 4: 50 · Sequence of 5+: 100
- Four 10s / Queens / Kings / Aces: 100 each
- Four Jacks: **200**
- Four 9s: 150 (optional, must be agreed)

Large Weis adds longer sequences (6→150, 7→200, 8→250, 9→300) and — importantly — lets **the same card count in both a four-of-a-kind and a sequence**. Small Weis does not.

Comparison order for Weis: longer sequence beats shorter; higher top card breaks ties; trump breaks further ties; then earliest to play. For Weis purposes rank order is always A K Q J 10 9 8 7 6 (so J-10-9 of trumps is a valid sequence; J-9-A is not). In Undenufe the reversed order applies for tie-breaking.

Scoring: **the team holding the single best Weis scores all of its Weis; the other team scores nothing.**

**Stöck**: King + Queen of trumps in one hand = 20 points. It is *not* a Weis and cannot be beaten. Announced when the second of the two is played.

> **Recommendation.** Weis is the single largest source of rule bugs and of scoring variance. The HSLU/Fribourg experiments **disabled Weis, Stöck and the match bonus** when benchmarking bots, precisely to cut variance. Do the same: implement Weis behind a flag (`WEIS_ENABLED`, default `true` for humans, `false` for bot-vs-bot evaluation runs). Train and A/B test with it off; play with it on.

### 2.4 Trick-taking rules (the part that is genuinely different)

This is where naive implementations get it wrong. Anticlockwise play, winner leads next.

- Any card may be led.
- **You may always trump, even when you can follow suit.** (Unlike Bridge/Skat/Hearts — and the reason Jass card play has a higher branching factor.)
- If a non-trump is led: follow suit **or** trump. If you can't follow, play anything, subject to the undertrump rule.
- If trump is led: you must follow with a trump **unless your only trump is the Puur** (Jack), in which case you may play anything.
- **Undertrumping (strict version, applies to Schieber):** if a non-trump was led and someone has already trumped, you may not play a *lower* trump — unless your hand is nothing but trumps, in which case any trump is allowed.
- No-trump contracts: ordinary follow-suit, highest of the led suit wins.

**The legal-move generator is the highest-risk function in the codebase.** Property-test it (Hypothesis): for random states, assert the returned set is non-empty, is a subset of the hand, and matches an independently-written naive reference implementation.

### 2.5 Winning

First to 3000 points (≈12 rounds). Losers under 1500 are *Schneider*. Reaching 1500 first is the *Bergpreis*. Stöck-Weis-Stich decides simultaneous claims.

*Config flags:* `target_score` (3000 / 1500 / 1000 / single round), `schneider_enabled`, `bergpreis_enabled`, `claim_order`.

---

## 3. The algorithm

### 3.1 What the literature actually found

The relevant work is Joel Niklaus's 2019 Fribourg master's thesis (*JassTheRipper*) with Thomas Koller (HSLU), plus the associated AAAI/SDS papers. Findings that should directly shape your build:

- **DMCTS (Determinized MCTS) and a supervised DNN are roughly equally strong**, and both beat rule-based bots and ISMCTS.
- Six experienced human teams (avg 15 years' play) scored **49.5% ± 14.2%** of points against a DMCTS team over 136 rounds — i.e. roughly par with strong amateurs.
- **Hyperparameters:** for a fixed budget of 800k rollouts, `1000 determinizations × 800 iterations` was the sweet spot. More than ~1000 determinizations stopped helping. Exploration constant ≈ 1.5 (much higher than the ~0.2 that's optimal for perfect-information MCTS — expected for imperfect information).
- **Value estimation:** ~25 random rollouts plateaus. **100 MCTS iterations beat 1000 random rollouts.** So don't waste budget on flat Monte Carlo.
- **Two negative results worth internalising:**
  - Sampling determinizations from a *learned card-distribution model* did **not** beat uniform random sampling. It mostly increased variance.
  - Replacing random rollouts with rule-based rollouts did **not** improve DMCTS.
  - Both are warnings against premature cleverness. Uniform sampling + more compute wins.
  - **Reproduced, for a prior that is not a learned one.** We built the obvious objection to that first result: `krass_jass/reading.py` tilts the determinization by what the *discard convention* says rather than by a fitted corpus, bounded four-to-one so no world is removed. It is worth nothing — two nulls and one borderline p that did not replicate (`docs/measurements.md` §5c). Off by default, kept behind a flag. The warning against premature cleverness survives contact with a cleverer prior.
- **Trump selection:** a learned network was best (and a good *ranked rule-based* selector came within ~0.7 points of it — 49.26% vs 50%). Random trump selection scored 34% — trump choice alone is worth ~16 points of win rate. A simple rule-based selector gets you nearly all of the available gain. **Do the rule-based one first.**
- Search-based MCTS trump selection was *worse*, because it almost never learned to shove — and shoving is valuable, since it conveys information.

### 3.2 Recommended agent architecture

Split the two decisions; they are different problems:

**Trump selection (7 actions: 4 suits, Obenabe, Undenufe, shove).**
Phase 1: rule-based scoring — per-suit points for holding Puur, Näll, Ace, length, plus counts of 6s/7s/8s for Undenufe and Aces/Kings for Obenabe. Shove if the best score is below a threshold. Cheap, transparent, near-optimal.
Phase 2: a small MLP on the 36-bit hand + "am I forehand or the partner" flag. ~2 hidden layers.

**Card play.**
Phase 1: DMCTS. For each of N determinizations (random legal assignment of unseen cards consistent with observed voids), run a perfect-information UCT search; aggregate move scores across determinizations weighted by selection count.
Phase 2: exact endgame solver when ≤5 cards remain per hand.
Phase 3: distil to a policy+value net for serving.

### 3.3 Void tracking — the cheap win

When a player fails to follow suit, they are *provably* void in that suit. Track a per-seat void matrix and constrain determinization sampling to consistent deals. This is exact inference, not a model, and it's the highest value-per-line-of-code feature in the whole search. Do it from the start.

### 3.4 The distillation plan (this is the answer to "how do I store best practices")

```
  slow DMCTS self-play (offline, seconds/move — see the cost note below)
        │
        ▼
  N million (observation, chosen_move, final_score) records → Parquet
        │
        ▼
  supervised training: policy head + value head (+ optional card-distribution head)
        │
        ▼
  small network, ~1ms inference  →  served by the bot container
        │
        ▼
  (optional) network as prior/eval inside a small-budget MCTS at serve time
```

Published network shape, as a starting point: a CNN over a 4×9 card grid with ~43 channels (cards played, by whom, in which trick, current trick, own hand, legal moves, plus broadcast planes for trump / declarer / score / trick count), 6 conv layers of 256 channels, three heads (policy / value / card-distribution). That reached ~0.78 policy accuracy against human play.

**Important for you:** they trained on **1.8M human rounds from Swisslos**, which you do not have. Your training corpus must come from **your own DMCTS self-play**. This is the whole reason throughput matters.

> **Cost note — read this before committing to M5.** Measured on an M2, Python 3.12, with a
> deliberately optimistic bitboard rollout (no undertrump rule, no Weis, no validation):
> **~25k full rounds/sec single-core**, i.e. ~50k raw rollouts/sec, or ~12–25k/sec once MCTS tree
> overhead is included. The tuned 800k-rollout budget is therefore **30–65 seconds per move**, and a
> 1.5s serve budget buys ~3% of it.
>
> A ~1M-decision corpus is ~28k rounds × 36 decisions. At a 30s/move teacher that is 8,400 core-hours
> — **44 days with all 8 cores pegged**. At 10s/move, 15 days. At 5s/move, 7 days.
>
> So the affordable teacher is ~5s/move — only 3–7× the compute of what you could serve *directly*
> at 1.5s, which in MCTS is worth perhaps 1–3% of points. **At pure-Python throughput, distillation
> buys close to nothing over simply serving DMCTS.** It pays only when the teacher has 100–1000× the
> student's search, and that requires the engine to get 30–100× faster first.
>
> **Consequence:** Numba/Cython/Rust on the rollout loop is not a contingency for M5, it is a
> precondition. Keep the rollout loop isolated and free of Python objects from M1 onward so it can be
> swapped without touching anything else. That is a module-boundary decision made *before* the first
> commit, not after profiling. See `docs/plan-review.md`.

### 3.5 Alternatives considered and rejected (for v1)

- **CFR / Deep CFR.** Strong theory, converges to low exploitability, but slow to converge and essentially unproven outside Poker/2-player. Overkill here.
- **ISMCTS.** Theoretically cleaner (avoids strategy fusion) but measured *worse* than DMCTS in Jass. Skip.
- **Pure RL from scratch (AlphaZero-style).** Viable as phase 4, but you need a fast engine and a working eval harness first, or you will not be able to tell whether it's learning.

---

## 4. Evaluation methodology

Get this right early or every later decision is noise.

- **Double rounds.** Play each deal twice, swapping which team gets which hands. This cancels most of the deal luck and is the difference between a usable A/B test and a coin flip.
- **Protocol:** 10 × 100 rounds per matchup; report mean % of total points and std; **paired** t-test on the per-deal differences. Double rounds are a paired design — an unpaired test discards the pairing and throws away most of the variance reduction you just bought. Expect std around 1% between bots, ~14% against humans.
- **Disable Weis / Stöck / match bonus** in evaluation runs to cut variance further.
- **Fixed seeds**, recorded in the result row, so any matchup can be replayed exactly.
- Nightly CI job: current agent vs. previous release vs. rule-based baseline. Plot it. A regression should fail the build.
- Baseline ladder to keep around forever: `random` → `greedy` (highest-value legal card) → `rule-based` → `DMCTS(small)` → `DMCTS(large)` → `cheating MCTS` (sees all hands — your upper bound).

---

## 5. System architecture

```
                    ┌──────────────┐
     browser ◄─WS──►│  web (FastAPI)│  ── serves UI, owns session
                    │  + Jinja/HTMX │
                    └───────┬───────┘
                            │ internal only
                    ┌───────▼───────────────┐
                    │  engine (FastAPI)      │  authoritative rules + state
                    │  - legal moves         │  builds PER-SEAT observations
                    │  - scoring             │  emits decision traces
                    └──┬────┬────┬───────────┘
                       │    │    │  REST, per-seat observation only
              ┌────────▼┐ ┌─▼───┐ ┌▼──────┐
              │ bot-1   │ │bot-2│ │ bot-3 │   same image, 3 replicas
              └─────────┘ └─────┘ └───────┘   stateless, no egress
                            │
        ┌───────────────────┼────────────────────┐
   ┌────▼─────┐      ┌──────▼──────┐      ┌──────▼──────┐
   │ postgres │      │ model store │      │ otel/traces │
   │ games,   │      │ (volume or  │      │ (optional)  │
   │ evals    │      │  MinIO)     │      └─────────────┘
   └──────────┘      └─────────────┘
```

Separately, offline and **not** part of the compose stack that serves the app:

```
   trainer (batch container)  →  reads/writes Parquet, writes model versions
   arena   (batch container)  →  runs tournaments, writes eval rows to postgres
```

Keep training out of the serving compose file. Different lifecycle, different resource profile.

### 5.1 Stack choices

| Layer | Choice | Note |
|---|---|---|
| Web / API | FastAPI + Pydantic | Pydantic models double as your wire contract |
| Realtime | WebSocket | Card animations need push; polling will feel bad |
| Templates | Jinja2 + HTMX | See caveat below |
| Engine core | Pure Python, **bitboard** representation | Then Numba/Rust if benchmarks demand |
| Bot service | FastAPI, stateless | `POST /select_trump`, `POST /play_card` |
| DB | PostgreSQL | Games, traces, eval results |
| Training data | Parquet (pyarrow) | Not the DB |
| Model | PyTorch | Export to ONNX for CPU-only serving |
| Orchestration | Docker Compose | Mirrors your geomcp setup |

**Frontend caveat, honestly stated:** a card table is animation-heavy and stateful in a way HTMX handles awkwardly. Your realistic options are (a) Jinja + WebSocket + ~200–300 lines of vanilla JS and CSS Grid — my recommendation, since card layout is mostly CSS anyway; (b) Reflex/NiceGUI to stay in Python — but you'll fight it for custom card layout; (c) accept a small JS framework for the table only. Don't let "Python where possible" push you into (b) by default; it's the option most likely to become the thing you hate.

**Responsive:** design mobile-first. The hard part is the 9-card hand on a 375px viewport — overlapping fanned cards with a tap-to-lift interaction. Prototype that one component before anything else; it constrains the whole layout.

### 5.2 The bot contract

```
POST /select_trump
{
  "hand": ["HA","HK","H9","SJ", ...],        // 9 cards, own hand ONLY
  "is_forehand": true,                        // false = partner shoved to me
  "scores": {"us": 1240, "them": 980},
  "seat": 1,
  "decision_seed": 774411203,                 // derived, see §6 — NOT the game seed
  "trace": true
}
→ { "action": "DIAMONDS" | "OBENABE" | "UNDENUFE" | "SHOVE",
    "trace": { "candidates": [...], "budget_used_ms": 812 } }

POST /play_card
{
  "hand": [...],                              // own remaining cards ONLY
  "legal_moves": [...],                       // engine-computed, authoritative
  "trump": "DIAMONDS",
  "declarer_seat": 0,
  "current_trick": [{"seat":0,"card":"D8"}],
  "tricks_played": [ ... ],                   // public history
  "weis_announced": [ ... ],                  // public
  "scores": {...},
  "seat": 1,
  "time_budget_ms": 1500,
  "decision_seed": 774411203,                 // derived, see §6 — NOT the game seed
  "trace": true
}
→ { "card": "DJ", "trace": {...} }
```

**Note what is absent:** no other player's hand, no deck order, **no game seed**, no full-state object. The engine computes `legal_moves` and the bot's answer is re-validated server-side — never trust the bot's move.

`decision_seed` is the one deliberate exception, and it is what makes replay possible at all — see §6. It is a *derived* per-decision value that reveals nothing about hidden state; the raw game seed never crosses the boundary.

**Identity fields are absent on purpose.** The bot never learns `game_id`, `round` or `trick`. The engine holds those and assembles the trace record in §6 by joining its own context onto the bot's returned `trace` block. The bot cannot write a trace row by itself, and shouldn't be able to.

**The agent is a library, not a service.** The FastAPI bot is a thin wrapper around an importable `agent.decide(observation) -> move`. Self-play and the arena call that function directly across a process pool; they do not go through HTTP. Three containers exist to serve *one* game to a human, not to generate millions of them.

Consider mirroring the existing HSLU/Zühlke Jass bot REST interface so external bots can be dropped in for benchmarking.

---

## 6. Debug mode and traceability

Every decision writes one structured record:

```json
{
  "game_id": "...", "round": 3, "trick": 5, "seat": 2,
  "agent_kind": "dmcts", "agent_version": "0.4.1", "model_version": "policy-2026-09-01",
  "rng_seed": 8823411,
  "observation_hash": "sha256:...",
  "legal_moves": ["DJ","S7","CA"],
  "chosen": "DJ",
  "candidates": [
    {"card":"DJ","visits":41203,"mean_score":0.612,"determinizations_selecting":734},
    {"card":"CA","visits":18877,"mean_score":0.548,"determinizations_selecting":201}
  ],
  "budget_used_ms": 1487, "determinizations": 1000, "iterations": 800,
  "known_voids": {"0":["HEARTS"],"3":[]}
}
```

- **Seed everything.** Deal RNG, determinization RNG and rollout RNG all derive from one game seed → any game replays bit-for-bit. This turns "the bot did something weird" into a reproducible test case.
- **How that survives the information boundary.** The bots are stateless services that do their own determinization and rollouts, so bit-for-bit replay and "the observation carries no seed" are in direct conflict: one of them has to give. The resolution is a *derived* seed — the engine sends `decision_seed = HMAC(game_seed, game_id ‖ seat ‖ round ‖ trick)` in each observation, and the bot seeds its RNG from that alone. The bot gets reproducibility; it cannot invert the HMAC to recover the game seed, and the value is independent of any hidden card. Never send `game_seed` itself: it determines the deal, and a bot holding it can reconstruct every hand at the table.
- **Replay viewer** in the UI: step through a finished game, see each bot's candidate scores and inferred voids.
- **Trap to avoid:** the debug panel must not leak hidden cards to the human *during* play. Gate it — traces are only readable after the round ends, or behind a `DEV_MODE` flag that is off in the compose file you actually run. Put a test in CI that asserts the mid-game debug endpoint returns no unseen card identifiers.
- OpenTelemetry spans across web → engine → bot, correlated by `game_id`.

---

## 7. Threat model (write this before the architecture is fixed)

| # | Threat | Impact | Mitigation |
|---|---|---|---|
| T1 | Engine leaks hidden cards into a bot observation | Bot cheats; results invalid | Single `build_observation(seat)` function. Unit test asserting the payload contains no card not in that seat's hand/public history. **Fuzz it in CI.** |
| T2 | Debug/trace endpoint leaks hidden state to the human | Human cheats | Traces gated post-round; `DEV_MODE` off by default; CI assertion |
| T3 | Client submits an illegal move or another seat's move | State corruption | Engine is authoritative; re-validate every move against `legal_moves`; bind the session to a seat |
| T4 | Bot container hangs or spins | Game stalls, CPU exhaustion | Hard `time_budget_ms` + client-side timeout + fallback to a random legal move; per-container CPU limit |
| T5 | Compromised/hostile bot exfiltrates data | Data loss | Bot containers on an internal-only Docker network, **no egress**, no DB credentials, no writable volumes. Model weights are **baked into the image** and the image tag carries `MODEL_VERSION` — do not mount the model store into a bot. If that ever becomes impractical, a single `read_only` bind mount of the model file is the one permitted exception. |
| T6 | Dependency supply chain | RCE | Pinned lockfile, `pip-audit`/Trivy in CI, SBOM, Dependabot |
| T7 | Session hijack | Play as someone else | Signed HTTP-only SameSite cookies; no accounts = no password surface |
| T8 | WebSocket abuse / resource exhaustion | DoS | Rate limit per session, cap concurrent games, message size limits |

Container hardening baseline: non-root user, `read_only: true` rootfs with a tmpfs for scratch, `no-new-privileges:true`, dropped capabilities, pinned base image digests, only the `web` service publishes a port.

**Privacy note:** if you use guest sessions with a signed cookie and no accounts, you have essentially no personal data to protect. That is a design win — don't build auth you don't need.

**Licensing note:** `jass-kit-py` (the HSLU Python toolkit) is **GPL-3.0**. If you depend on it, that propagates. Since you're writing your own engine anyway, use it at most as a *test-only oracle* to cross-validate your rules, and keep it out of the runtime dependency graph — or skip it entirely.

---

## 8. Milestones

**M0 — Decisions (before any code).** Lock: rule variants and defaults, target strength, latency budget, Weis in/out for v1, game length, single-human-only. Write it down as `docs/rules-config.md`.

**M1 — Engine + tests.** Bitboard state, legal moves, trick resolution, scoring, Weis comparison. Property tests against a naive reference implementation. **Benchmark harness in CI reporting rounds/sec.** No web, no bots. This is the foundation and it must be boringly correct.

**M2 — Playable loop.** FastAPI engine + web + WebSocket + random/greedy bots in three containers. Compose stack up. Mobile card-fan component working. Nothing smart yet — the point is the plumbing and the observation boundary.

**M3 — Rule-based bot + arena.** Rule-based trump selection, greedy-plus card play. Tournament harness with double rounds, seeds, results to Postgres. Now you can measure.

**M4 — DMCTS.** Void tracking, determinization, UCT, exact endgame solver. Tune determinizations/iterations/exploration against your own throughput. Expect this to be your strongest bot for a long while.

**M5 — Self-play data + distillation.** Batch self-play with high-budget DMCTS → Parquet → policy/value net → ONNX → served bot. Success criterion: **network at ~1ms/move within 1% of points against high-budget DMCTS.**

**Entry condition (new):** M5 does not start until the benchmark harness shows the rollout loop is
fast enough for a teacher at least ~100× the serve budget. On the numbers in §3.4 that means a
native rollout loop. If M1–M4 leave you at pure-Python throughput, the correct move is to **ship
DMCTS directly at the serve budget and skip M5**, not to distil a teacher that is barely stronger
than the student. Re-run the arithmetic against measured throughput before deciding.

**M6 — Polish.** Debug/replay UI, security hardening pass, difficulty levels (which map naturally to search budget), observability.

M7+ (optional): RL self-play loop, explicit team-coordination modelling, opponent modelling.

---

## 9. Open questions for you

1. Target strength: casual, or club player?
2. Latency budget per bot move — 1s? 2s? Does a visible "thinking" delay actually improve UX here (it does for perceived humanness)?
3. Weis in v1, or v2?
4. Do you have a GPU, or is this CPU-only? Affects whether the distillation step is a weekend or a fortnight.
5. Multi-human ever? Decide now.
6. Are you willing to write Rust for the rollout loop if benchmarks demand it, or is the throughput ceiling something you'd rather design around (smaller budgets, longer training wall-clock)?

---

## 10. References

- Schieber rules: https://www.pagat.com/jass/schieber.html
- General Swiss Jass rules (Weis, Stöck, trick-taking): https://www.pagat.com/jass/swjass.html
- Swisslos rule pages: https://www.swisslos.ch/en/jass/informations/jass-rules/
- Niklaus, *JassTheRipper: A High-Human AI for the Swiss Card Game Jass* (MSc, Fribourg, 2019) — https://niklaus.ai/files/theses/Master_Thesis.pdf
- Niklaus et al., *Survey of AI for Card Games and Its Application to the Swiss Game Jass*, SDS 2019
- JassTheRipper source (Java, DMCTS): https://github.com/JoelNiklaus/JassTheRipper
- jass-kit-py (HSLU, **GPL-3.0**): https://github.com/thomas-koller/jass-kit-py
- pyschieber (Python engine + CLI, useful as a rules cross-check): https://github.com/Murthy10/pyschieber
- Cowling, Powley & Whitehouse, *Information Set Monte Carlo Tree Search*, IEEE TCIAIG 2012
- Browne et al., *A Survey of Monte Carlo Tree Search Methods*, IEEE TCIAIG 2012
