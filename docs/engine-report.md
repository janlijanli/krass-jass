# How the krass-jass bots play, and what each part is worth

A statistical report on the engine as it stands on **2026-09-15**: the evaluation protocol and the
statistics behind every figure, the search (Information Set MCTS), how the bots form beliefs
about hidden cards, how they choose trump, and every measurement that decided a default — with the
negative results kept, because most of what was tried did not work.

`docs/measurements.md` is the dated record this report summarises: experiments in the order they
were run, superseded results left in and marked. Section references like **§5h** point there.
Where the two disagree, the record is the source and this report is wrong.

---

## 0. Summary

### What ships

| component | setting | evidence (bot vs bot) |
|---|---|---|
| Search | ISMCTS, one tree shared across imagined deals | +1.15 vs voting DMCTS at equal iterations, +0.53 at equal time (§5h) |
| Budget | 40 × 3,840 = **153,600** iterations a move | pays to ~64× 2,400, flat after (§3b) |
| Endgame solver | **off** (`endgame_cards = 0`) | turning it off: **+1.71** (§3e) |
| Exploration constant | 1.5 | 0.7, 1.0, 2.5 all null (§5p) |
| World sampling | resample every 4 iterations | 1 is null, 8 loses the gain (§5h, §3c) |
| Hard constraints | voids, shown Weis cards, called Weis values | +0.62 and +0.40 (§5l, §5m) |
| **Beliefs** | worlds weighted by the other seats' plays and the bid, α = β = 1, pool 4,096 | **+1.31, replicated +1.32** (§5o) |
| **Trump selection** | rule-based, weights tuned by simulation | **58.3% of games** vs hand-written weights (§5n) |
| **Tree policy** | the other three seats move by the play model inside the tree | **+0.86, replicated** at equal iterations, ~11× a move (§5p); off in the browser |
| **Play model** | 32 hidden units, fitted to 310,184 decisions of convention self-play | **+0.45, replicated**, over the model fitted without conventions (§5w) |
| **Swiss conventions** | draw trump, cash aces then kings, schmieren, never trump the partner, … — may choose any move within **0.01** of the best by the search's own score | **free** (50.03%, p = 0.86); the partner plays the expected card in **73%** of convention decisions, from 59% (§5u) |
| Game objective | play for the game near the finishing line | null, kept because it cannot hurt (§5d) |

### What was measured and does not ship

| tried | result | why it stays off |
|---|---|---|
| belief network (learned card locations), weight 1 | +0.03 oracle-equivalent offline; **50.15%, p = 0.24** over 2,000 deals | null in play (§5q) |
| sharper belief weights (α 1.5, β 2, bid T 1, pool 8,192) | +0.034 offline; **50.09%, p = 0.43** over 2,000 deals | null in play (§5r) |
| play model retrained on today's bot (63.5% top-1) | +0.015 offline; **50.12%, p = 0.30** over 2,000 deals | null in play (§5r) |
| trump refit on labels from a stronger card player | **+3.2 ± 1.6** game points a round, held out | a tenth of the first fit; not run in play (§5r) |
| play-model rollouts | +1.10 at equal iterations, **null at equal time** | ~40× cost spends all of it (§5p) |
| policy network playing without search | 60.3% agreement with the search; **−4.0** against it | data-limited; kept as a fast difficulty level (§5s) |
| value network at the leaves | 49.85% at 2,400 (p = 0.39); 50.40% at 153,600 (p = 0.068) at 1.6× the time | kill criterion fired (§5t) |
| discard-signal reading | null on the voting search, **−0.36** on the shared tree | §5c, §3f |
| hand-written or learned policy prior (PUCT) | null (and −0.84 at high weight) | ~4 legal moves, each already visited ~570× (§5i, §5j) |
| linear leaf evaluator instead of random playout | **−9 points** | bias does not average out; playout noise does (§5g) |
| risk-averse reward | null at four settings | §5f |
| deeper exact endgame (6 cards) | **−0.65** | strategy fusion, sharpened (§3d) |

### How far from perfect information

A bot that sees all four hands beats the shipped-before-this-week search **57.35% ± 6.46** over 800
deals (§3f) — about 7 points of a round's share. Strategy fusion accounts for ~0.7 of that (§5h).
Replacing a fraction *p* of the imagined deals with the truth recovers most of the rest along a
concave curve (§5k), which is why belief work is where the recent gains came from.

---

## 1. What is being measured

### The unit: share of a round's points

Every round-level figure is the **share of the points** one agent's team took, averaged over deals:

```
share = points_A / (points_A + points_B)
```

Points are the round's `RoundScore.total` — trick points, the last-trick bonus, the match bonus,
and under `HOUSE` rules Weis and Stöck — **already multiplied by the contract multiplier**
(Ecken, Schaufel ×1; Herz, Kreuz ×2; Obenabe ×3; Undenufe ×4). Within one round the multiplier
cancels out of the share. Across the two halves of a double round (below) it does not, because
each half bids independently and can land on a different contract — so the share *does* price a
bidding change in game points.

50% is equality. A difference of **+1.0** means one percentage point of the round's points.

### Rules presets

- **`EVAL`** — Weis, Stöck and the match bonus off, no target score. Lower variance; the preset of
  every figure up to §5k.
- **`HOUSE`** — the rules you play: Weis and Stöck on, match bonus 100, target 3,000 (matches use
  `target_score=None` so the round objective is unchanged). Needed for anything involving Weis,
  since under `EVAL` that information does not exist.

### Whole games

`arena/games.py` plays complete games to a target (1,000 unless stated) and counts games won. It is
the right instrument for anything that trades points for position — the game objective, bidding —
and ~20× noisier per sample than rounds (per-pair standard deviation ~23–27% of games against ~5–7%
of points).

---

## 2. Protocol and statistics

### Double rounds and common random numbers

Each deal is played **twice with the teams swapped**: A sits on seats 0/2 with hands H, then on
seats 1/3 with the other hands. Both halves use the **same game seed**, so every per-decision seed
(`HMAC(game_seed, game_id ‖ seat ‖ round ‖ trick)`) is shared where the positions coincide. The deal
and the random numbers are common; only the agents differ. An agent against itself scores exactly
0.5 on every deal — a test asserts it.

For deal *i*, `s_i` is A's share over both halves combined.

### The test

Paired, on the per-deal differences from equality:

```
d_i = s_i − 0.5
t   = mean(d) / (sd(d) / √n)
p   = 2 · (1 − Φ(|t|))          (normal approximation; n is in the hundreds to thousands)
```

**Reading the tables.** `51.31% ± 5.91` means mean share 51.31% with a **per-deal standard
deviation** of 5.91 percentage points — *not* a standard error. The standard error is `sd / √n`:
5.91 / √1000 = **0.19**. Where a table gives `± 0.118`, it is a standard error, and says so.

Pooling across seeds concatenates the deals (seeds are independent), so the pooled standard error is
`sd_pooled / √(n₁ + n₂)`.

### Power

For a two-sided test at α = 0.05 with 80% power, the minimum detectable effect is about
`2.8 × sd / √n`:

| per-deal sd | 600 deals | 1,000 | 2,000 | 3,000 | 6,000 |
|---|---|---|---|---|---|
| 5 (card play, `EVAL`) | 0.57 | 0.44 | 0.31 | 0.26 | 0.18 |
| 6.5 (card play, `HOUSE`) | 0.74 | 0.58 | 0.41 | 0.33 | 0.24 |
| 9.6 (bidding changes) | 1.10 | 0.85 | 0.60 | 0.49 | 0.35 |

| whole games, per-pair sd ~25% | 400 pairs | 800 | 1,600 | 2,400 |
|---|---|---|---|---|
| minimum detectable, % of games | 3.5 | 2.5 | 1.8 | 1.4 |

This table is why effects of a few tenths of a point needed 3,000–6,000 deals.

### Replication, and the borderline results that died

Six results in the record reached p ≈ 0.02–0.05 on a first look and **did not replicate** on a fresh
seed — among them the disciplined-signaller reading (§5c), the hand-written PUCT prior at c = 1 (§5i)
and the learned prior (§5j), which went 50.44 → 50.23 → 50.02 across three seeds. The pattern
was always the same: a bump noticed inside a sweep of several settings — where one p below 0.05 is
expected by chance about a quarter of the time — then defended. The rules adopted since:

1. **Predict first.** Say what the mechanism is and which direction it moves before measuring.
2. **Replicate on a fresh seed** before anything becomes a default.
3. **Equal wall-clock** is the shipping gate for anything that costs more per move.

Results that shipped under those rules replicated tightly: ISMCTS three times (§5h), called-Weis
beliefs over four seeds at χ² = 1.9 on 3 df (§5m), play-model beliefs at 51.31 and 51.32 (§5o).

### Offline belief quality: oracle-equivalent *p*

Matches cost hours; belief settings were chosen offline first (`arena/belief_quality.py`). For a
decision, draw a pool of worlds consistent with every hard constraint, give each a weight `w_j`,
and score the belief by the expected fraction of hidden cards placed with the right seat:

```
u = mean_j acc(world_j)               (uniform over the pool)
a = Σ_j w_j · acc(world_j) / Σ_j w_j  (weighted)
p = (a − u) / (1 − u)
```

Mixing a fraction *p* of true deals into a sampler of accuracy *u* gives accuracy exactly
`u + p(1 − u)`, so *p* is on the same axis as §5k's oracle experiment and converts to points with it
(§4.3). It is a proxy: the search consumes worlds, not accuracy.

The pool's **effective sample size** is `ESS = (Σw)² / Σw²`. §5h found the shared tree needs a few
hundred distinct worlds (the gain from ISMCTS is intact at 600 distinct worlds and gone at 300), so
settings that collapse ESS below ~300 are rejected however accurate they look.

### Clustered and cross-fitted estimates (trump selection)

Contract values were simulated on 16 deals per hand. Deals sharing a hand are correlated, so
standard errors are **clustered by hand** (mean per hand, then the standard error of those means).
The "best call per hand" is **cross-fitted**: chosen on half of a hand's deals and scored on the
other half, then swapped — choosing and scoring on the same deals rewards the luckiest noise. The
cross-fitted estimate is conservative (it chooses on only 8 deals).

---

## 3. The search

### 3.1 Information Set MCTS

The hidden cards make Jass a game of imperfect information. The search handles it by
**determinization** — imagining concrete deals of the unseen cards consistent with everything
known — and by **sharing one tree across all of them** (`rust/src/ismcts.rs`).

Per move, for each iteration:

1. **World.** Every 4 iterations, draw a new imagined deal of the unseen cards (§4). The searching
   seat's own hand is always the real one.
2. **Selection.** Walk down the shared tree. A node is reached by a sequence of played cards —
   public information — so a node *is* an information set and holds one set of statistics.
   Different worlds make different cards legal; each child counts how often it was **available**,
   and UCT divides by that rather than by the parent's visits:

   ```
   score(child) = Q̄ + c · √( ln(available) / visits ),     c = 1.5
   Q̄ = mean reward             if the searching team is to move
   Q̄ = 1 − mean reward         if the opponents are  (adversarial backup)
   ```

   Without the availability count, cards that are rarely dealt look unpopular instead of untested —
   the one detail that separates a working ISMCTS from a broken one.
3. **Expansion.** The first untried legal card at the first node that has one.
4. **Rollout.** Finish the round with uniformly random legal play in the current world.
5. **Reward.** The searching team's **share of the round's points** — or, within a few rounds of
   the target score, a projection of the chance of winning the game (§5d, v3).
6. **Backup** along the path.

The move played is the **most visited** root child (ties by mean value) — unless a Swiss
convention names another card the search rated within 0.01 of a round's share of it, in which case
that card is played (§5.4, measurements §5u).

### 3.2 Why a shared tree and not a vote

The design it replaced (`rust/src/search.rs`, "DMCTS" or PIMC) built **a separate tree per imagined
deal** and voted. Each tree is a perfect-information search, so the voting search effectively
chooses a different card for every world and then holds an election — **strategy fusion**. A real
player must pick one card that works across every world they cannot tell apart; a shared tree
enforces that in the data structure.

| ISMCTS vs voting DMCTS | share | deals | p |
|---|---|---|---|
| equal iterations | 50.72% ± 6.24 | 1,000 | 2.4e-04 |
| equal iterations, fresh seed | 51.23% ± 6.49 | 1,400 | 1.3e-12 |
| equal iterations, third seed | 51.15% ± 6.74 | 1,400 | 2.0e-10 |
| **equal wall-clock** | **50.53% ± 6.77** | 1,400 | 3.4e-03 |

The mechanism was checked rather than assumed: the gap to a cheating agent narrows by 0.74 (59.13%
against voting, 58.39% against ISMCTS) — consistent with the head-to-head, and only about a tenth
of the hidden-information cost.

### 3.3 The exact endgame solver, and why it is off

A double-dummy solver (`rust/src/endgame.rs`) returns the exact value of a position given all four
hands. For the voting search it replaced the last tricks and helped. For the shared tree it is a
liability: below the threshold the search becomes "deal a world, solve it perfectly, vote" — PIMC
again, with every vote made *more* confident about deals that are mostly wrong.

| `endgame_cards` vs 5, at 153,600 iterations | share | deals | p |
|---|---|---|---|
| 6 | 49.350% ± 0.110 (SE) | 2,000 | 3.2e-09 |
| 4 | 50.50% ± 3.70 | 1,000 | 1.8e-05 |
| **0 — no solver** | **51.707% ± 0.074 (SE)** | **4,000** | ~1e-118 |

Monotone in depth. At the old 2,400-iteration budget turning it off was worth +1.41 (n = 1,000), so
it had been costing strength since ISMCTS arrived. It stays in the code behind the flag, because it
is still the right tool for a search that votes.

### 3.4 Budget

On the voting search, more budget stopped paying near 2,400 iterations (§3, `EVAL`, n = 500 each
against a 2,400 reference: 60 → 43.71%, 800 → 49.14%, 8,000 → 50.03%, 40,000 → 50.23%; 40k vs 2.4k
50.30% over 1,000 deals, 800k vs 40k 49.60%). That number set the serve budget for months. **It
does not hold for the shared tree:**

| ISMCTS budget vs 2,400, `HOUSE` | share | deals | p |
|---|---|---|---|
| 9,600 (4×) | 50.41% ± 6.09 | 600 | 0.096 |
| 38,400 (16×) | 50.370% ± 0.113 (SE) | 3,000 | 0.001 |
| **153,600 (64×)** | **50.560% ± 0.118 (SE)** | 3,000 | 2e-06 |
| 614,400 (256×) | 50.64% ± 6.05 | 600 | 0.0096 |

Controls: the same 153,600-vs-2,400 comparison under `EVAL` is 50.695% ± 0.121 SE (n = 3,000), so it is
not the Weis constraints; with the voting search it is 50.140% ± 0.146 SE (n = 2,000, p = 0.34), so
saturation was a property of the voting search. The curve is shallow: 40,000 still beats 2,400 by
nothing measurable (50.31%, n = 300).

### 3.5 Split and resampling

At a fixed 2,400 iterations, split between worlds and iterations per world (voting search, n = 600
each against 40 × 60): 4 × 600 → 48.89%; 10 × 240 → 49.65%; 20 × 120 → 50.39%; 80 × 30 → 50.27%;
240 × 10 → 47.56%; 600 × 4 → 41.41%. A broad plateau with two floors: at least ~10 worlds and ~30
iterations per world.

For ISMCTS, drawing a world every iteration costs 1.95× the voting search; sharing a world across a
few iterations recovers the cost:

| worlds shared | cost vs DMCTS | share vs DMCTS | p |
|---|---|---|---|
| 1 | 1.95× | 50.59% ± 6.55 | 0.0045 |
| **4** | **1.41×** | **50.64% ± 6.77** | **0.0029** |
| 8 | 1.34× | 50.07% ± 6.62 | 0.74 |
| 16 | 1.30× | 49.82% ± 6.57 | 0.39 |

The gain survives at 4 and is gone at 8. At 153,600 iterations, `resample_every` 1 against 4 is
50.125% ± 0.098 SE (n = 2,000, p = 0.20): world diversity is no longer the constraint.

### 3.6 Exploration constant

1.5 was inherited from the published voting search and first tuned for the shared tree on 2026-09-15:

| exploration vs 1.5, 153,600 iterations, `HOUSE` | share | deals | p |
|---|---|---|---|
| 0.7 | 50.08% ± 5.48 | 1,000 | 0.66 |
| 1.0 | 50.05% ± 5.15 | 1,000 | 0.75 |
| 2.5 | 50.09% ± 5.20 | 1,000 | 0.59 |

Flat across 0.7–2.5 (standard error ~0.17 each). It stays at 1.5.

### 3.7 What the search is not missing

Five attempts to improve the search from the inside measured nothing or worse, and each came with a
mechanism explaining why:

- **Leaf evaluator** (§5g). A linear evaluator fitted to the playout's own mean, nearly twice as
  accurate per call (RMSE 0.23 vs 0.43), lost **9 points** at every split. The playout's error is
  zero-mean and averages out over thousands of samples to ~0.02; an evaluator's error is bias and
  does not. A drop-in value function would need RMSE below ~0.02 on a quantity with SD ~0.3.
- **Policy priors** (§5i, §5j). Hand-written knowledge in PUCT: null at c = 0.5–2, **−0.84 at
  c = 4** (p = 5e-05). A prior learned from the search's own play (48% top-1): 50.44 → 50.23 → 50.02
  on three seeds; a uniform prior in the same slot is null too. The average position has **4.2 legal
  moves** and 2,400 iterations visit each ~570 times — there is nothing to prune.
- **Risk-averse reward** (§5f): λ = 0.25, 0.5, 1, 2 → 50.34, 49.53, 49.60, 49.68 (n = 600 each), all
  null. (An affine penalty would provably change nothing; the tested form has a kink.)
- **Deeper exact endgame** (§3d): −0.65.
- **Play model inside the search** (§5p): see §5.3 — real at equal iterations, not at equal time.

---

## 4. Beliefs

### 4.1 Why beliefs are the lever

§5k replaced a fraction *p* of the search's imagined deals with the true deal (`arena/oracle.py`,
measurement only), walking the bot from its own beliefs to perfect ones. n = 800 each:

| *p* | 0.05 | 0.10 | 0.20 | 0.35 | 0.50 | 0.75 | 1.00 |
|---|---|---|---|---|---|---|---|
| share | 50.36% | 51.34% | 52.52% | 54.14% | 55.24% | 56.75% | 57.81% |
| gain per 1% of *p* | 0.072 | **0.134** | 0.126 | 0.118 | 0.105 | 0.090 | 0.078 |

Concave: the return per unit of belief accuracy peaks at *p* ≈ 0.1–0.2. **Each 1% of
oracle-equivalent accuracy is worth roughly 0.07–0.13 points**, so beating ISMCTS's +1.15 needed
beliefs worth ~10% of an oracle. Every earlier prior (§5c, §5e) was worth a fraction of one percent
by this scale, which is why they measured nothing.

### 4.2 Hard constraints: filter, never weight

Three kinds of information are exact and remove worlds:

- **Voids** (`krass_jass/voids.py`). A seat that failed to follow suit holds none of it; under the
  Puur exemption, a seat that discards on a trump lead holds at most the Puur. Stored as a per-seat
  mask of cards it provably cannot hold, and required to be *sound* — never an unproven constraint.
- **Shown Weis** (§5l). The winning Weis is turned face up. In 66% of rounds a Weis is shown,
  pinning 17.3% of the unseen cards at those decisions. Worth **+0.62 ± 0.18** of a round's share
  (two seeds, 1,500 deals each, p = 5e-06 and 6e-07) and **+1.78** points of games won (1,600 games,
  p = 0.002).
- **Called Weis values, including silence** (§5m). A value names no card, so it is checked on whole
  dealt worlds (`rust/src/announce.rs`), rejecting up to 16 draws before accepting one that
  contradicts a call. **80.4%** of imagined worlds had contradicted what the table said. Worth
  **+0.400 ± 0.082 SE** over 6,000 deals on four seeds (p = 1.1e-06) and +1.40 ± 0.44 SE of games
  (2,400 games, p = 0.0015) — on top of the shown cards. Building it exposed a sampler bug that had
  been discarding most pinned worlds since §5l.

### 4.3 Soft evidence: weights on a pool of worlds

Everything a model says goes into **weights**, never removals (`rust/src/belief.rs`). Once per
decision, 4,096 worlds are drawn under the hard constraints and weighted:

```
log w(world) = α · Σ_plays log π(card | that seat's hand in this world, public state)
             + β · log P(bid | bidder's dealt hand in this world)
             + γ · Σ_hidden cards log q(card at its seat in this world)
```

The search then samples its worlds from the pool in proportion to `w`.

- **Play likelihood (α).** Replay the round in the imagined world; for every card another seat
  played with more than one legal option, add the log-probability the **play model** (§5.1) gives
  it, holding *that seat's* hand in *this* world. A world where the partner discarded an ace from
  ace-small is a world their play makes unlikely.
- **Bid likelihood (β).** Forehand's action (a contract or a shove) and, after a shove, the
  partner's call, under a softmax over the trump selector's own contract scores at temperature 3,
  with the shove scored at its threshold.
- **Belief network (γ).** Learned card locations (§4.5). Off.

Shipped: **α = β = 1, γ = 0, pool 4,096.**

**Offline** (1,500 decisions, pool 2,048, `HOUSE`, our bots at the table):

| α | β | oracle-equivalent *p* | median ESS |
|---|---|---|---|
| 0.5 | 0.5 | 0.081 | 933 |
| 1 | 0 | 0.096 | 504 |
| **1** | **1** | **0.123** | 351 |
| 2 | 1 | 0.154 | 91 |

α = 2 buys accuracy by collapsing onto ~90 worlds — below what the tree needs. By §4.1's curve,
*p* ≈ 0.12 predicts **+1.3–1.5** before any match was run. It rises through the round: 0.06 after 6
cards, 0.08 after 13, 0.10 after 17, 0.17 after 22, 0.21 after 26.

With **random card play** at the table — a table the play model knows nothing about — *p* falls to
0.048 (0.015 from plays alone) and never below uniform: a wrong model costs sampling efficiency,
not correctness.

**In play**, vs the same search without it, 153,600 iterations, `HOUSE`:

| | share | deals | p |
|---|---|---|---|
| seed 91 | **51.31% ± 5.91** | 1,000 | 2.4e-12 |
| seed 8802 | **51.32% ± 5.80** | 1,000 | 6.5e-13 |
| **pooled** | **51.315%, SE 0.131** | 2,000 | < 1e-20 (t ≈ 10) |

The offline prediction matched to a tenth of a point. Cost: median ~670 ms a move against ~420 ms
without it, measured natively under load.

**Sharper is not better, and neither is a better model.** Three further offline gains of the same
size all measured null in play: the belief network's +0.031 (§4.5), +0.034 from sharper weights
(α = 1.5, β = 2, bid temperature 1, pool 8,192) at 50.09% ± 5.20, p = 0.43, and +0.015 from a play
model retrained on today's bot — 63.5% top-1 against 61.4% — at 50.12% ± 5.08, p = 0.30 (§5r, 2,000
deals each). The offline measure predicted the *first* step, from uniform sampling to reading the
table, to a tenth of a point; it has predicted nothing since. Treat it as a screen for whether a
signal exists, not as a forecast of points — and read the three nulls together as **the belief
channel being saturated at the shipped setting**: what remains of the gap to perfect information is
not reachable by improving which worlds get imagined.

### 4.4 The bidding prior that did not work, and why this did

§5e put the bid into the sampler as a bounded per-suit tilt (a suit-caller holds 3.7 of the suit
against a random 2.25; an Obenabe caller 2.66 aces against 1.00) — and measured 50.03% ± 6.54
(n = 1,000). Instrumented, the decisions it changed were ones the search already rated within
0.008 of each other: a small tilt only flips near-ties. The likelihood weighting differs in
magnitude, not kind — it conditions on whole hands and compounds over every observed card.

### 4.5 A belief network trained on the truth

Every self-play round knows the true deal, so a network can learn card locations directly
(`rust/src/beliefnet.rs`, `arena/train_belief.py`). No cheating agent is involved. Inputs are only
what the deciding seat saw, relative to it (left, partner, right): its hand; who played each card
and whether it was led, followed, discarded or ruffed; proven voids; shown Weis cards; each seat's
called value; contract, declarer, shove. Output: for each hidden card, a softmax over the seats it
is still allowed at (forbidden seats are masked, not learned). Architecture 865 → 64 → 32 → 108.

Validation by held-out round:

| network | rounds | per-card accuracy | validation loss |
|---|---|---|---|
| uniform over allowed seats | — | 40.8–41.0% | — |
| 128 → 64 | 6,000 | 45.5% | best at epoch 1, then rising (memorises) |
| 64 → 32 | 6,000 | 46.0% | 0.938 |
| **64 → 32** | **18,000** | **46.8%** | **0.923** |

In worlds, on the same 1,500 decisions (oracle-equivalent *p*, pool 2,048):

| weighting | 6,000 rounds | 18,000 rounds | ESS (18k) |
|---|---|---|---|
| network alone | 0.055 | 0.069 | 835 |
| plays + bid (shipped) | 0.124 | 0.124 | 486 |
| plays + bid + network × 0.5 | 0.139 | 0.143 | 325 |
| plays + bid + network × 1 | 0.149 | **0.155** | 197 |

The network on its own reads about half as much as the play-model likelihood — marginals over single
cards cannot carry "these two cards went together", which a replay under a play model can. On top of
it, it adds **+0.031** at weight 1: roughly **+0.3–0.4** of a round's share by §4.1. The search's
pool is 4,096, roughly doubling ESS.

**In play** (γ = 1 against the shipped α = β = 1, 153,600 iterations, `HOUSE`): **50.15% ± 5.65** over
2,000 deals, p = 0.24 — standard error 0.126, 95% interval −0.10 to +0.40. A null. The offline mapping
that predicted §4.3 to a tenth of a point overstates this one; a network of per-card marginals most
plausibly adds accuracy on cards the decisions do not turn on. It stays off.

---

## 5. The play model

### 5.1 Model

`rust/src/playmodel.rs`: π(card | a seat's own view). 36 features of each (state, card) pair —
card value, whether it is the highest unplayed card of its suit, how many unseen cards beat it, its
rank within the suit, the seat's length in the suit, whether it leads, follows, discards or ruffs,
whether the partner or an opponent is currently winning the trick, whether it takes the trick (and
whether it takes it safely), points on the table, trump counts, declarer team, Puur and Nell, trick
number, and interactions — scored by one shared function, a linear term plus a 32-unit ReLU layer,
softmaxed over the legal cards. Everything is computable from the seat's own hand and public
information, so inside an imagined world it asks "would *this* hand have played that card".

### 5.2 Fit

Trained (`arena/train_policy.py`) on **310,184 decisions** of the shipped search playing itself at
38,400 iterations under `HOUSE` — with the conventions on, so the model learns a table that plays
them (§5w: +0.45 of a round's share, replicated) — split by round:

| | |
|---|---|
| validation cross-entropy | **0.837** (uniform over legal moves: 1.288) |
| top-1 agreement with the search | **65.2%** (a linear model on 16 features, §5j: 48.0%; uniform: 30.7%) |
| Rust vs numpy, largest probability difference | 5e-06 |

The weights live in `krass_jass/data/play_policy.json`, compiled into both native and wasm builds.

### 5.3 The play model inside the search

Two further uses, both measured against the shipped search (both sides with beliefs on):

| variant | cost / move | equal iterations | **equal time (~153,600-iteration time)** |
|---|---|---|---|
| other three seats move by π inside the tree, holding their own hand in the world | ~11× | 51.23% ± 6.08 (38,400; p = 1.4e-10); **50.62% ± 6.16** (153,600; p = 1.4e-03) | **50.39% ± 6.65** (14,400; p = 0.066) |
| rollouts by π instead of at random | ~40× | 51.10% ± 6.80 (9,600; p = 3.3e-07) | **50.15% ± 7.22** (3,840; p = 0.52) |

n = 1,000 each. Both effects are real per iteration and both fail the equal-time gate, which is the
same shape as ISMCTS itself (+1.15 per iteration, +0.53 per second). The tree policy fixes a real
defect — in the shared tree the other seats' statistics are pooled across worlds, so they are
effectively conditioned on the searcher's real hand and blind to their own — and keeps a +0.39 lean.
It is the first place a larger move budget would go.

### 5.4 Conventions: what the partner plays, and what it reads

The owner asked for a partner that plays like a person, and for the Swiss conventions to be
researched and implemented. `krass_jass/convention.py` (mirrored in `rust/src/convention.rs`) carries
them, with their sources — Swisslos Jass-Onkel, jassverzeichnis.ch, and others:

| leading | following |
|---|---|
| opponents out of trump: cash the boss | Obenabe / Undenufe: drop the next card under a partner's top card |
| declaring team draws trump: the Puur with three or more, the other trump with two, never a bare Puur | partner winning, last to play: schmieren — the highest value that is neither trump nor a boss |
| bare Puur: a small card of the strongest side suit | partner winning: never trump the partner |
| cash side bosses, highest value first, not in a suit the partner discarded | discard low from the weakest suit, never a boss |
| anziehen: low in the strongest suit without its boss | cannot win: play low |

**They are not in the search's score.** The search rates the moves; a convention may only choose among
the moves it rated nearly the best — within a *price* of 0.01 of a round's share by the search's own
estimate, and never a move it gave less than 0.5% of its visits (a barely explored move has no reliable
score). Measured against conventions off (§5u): the price 0.01 is free (50.03%, p = 0.86) and makes the
bot play the convention's card in 73.2% of the decisions a convention speaks to, against 65.9% for the
old tie window and 58.9% for the search alone; 0.02 reaches 79.7% and costs half a point (p = 0.018).

**Playing them, and now reading them.** The beliefs (§4.3) and the tree policy (§5.3) see the other
seats through the play model, which was fitted to self-play without these conventions — so a partner's
ace-then-king said less to it than it should. Retrained on 12,000 rounds in which every seat plays
them, it agrees with the search on 65.2% of decisions against 61.4%, and wins **+0.45** of a round's
share, replicated on two seeds (§5w). It ships, and it is the first gain here from a behaviour the
owner chose rather than one the search found.

---

## 6. Trump selection

### 6.1 The selector

`krass_jass/trump.py`, twin `rust/src/trump.rs`, weights in `krass_jass/data/trump_weights.json`.
For each of the six contracts, a raw score:

- **a suit as trump:** Σ trump rank weights (J, 9, A, K, Q, 10, 8, 7, 6) + a bonus by trump length +
  Σ side-suit rank weights + void and singleton bonuses (only with ≥ 3 trumps);
- **Obenabe / Undenufe:** Σ rank weights (mirrored for Undenufe) + a bonus per card in a run of top
  cards.

Contracts are compared on **(raw − baseline) × multiplier** — the multiplier scales both teams'
points, so it multiplies the *edge*, not the score. Forehand shoves when the best is below a
threshold; the partner, shoved to, must call.

Against random bidding with identical card play (§2, n = 600, `EVAL`): **58.49% ± 14.76** — a
17-point spread, matching the published ~16.

### 6.2 Pricing the calls by simulation

`arena/contracts.py` fixes forehand's hand, deals the other 27 cards at random 16 times, and plays
**all six contracts** on each deal with the card-play bot (ISMCTS, 2,400 iterations, bidding prior
off so play does not depend on who declared). The value of a call is the declaring team's point
difference in game points (multiplied). Because play does not depend on who declared, one table
also prices the shove exactly — it is worth whatever the partner calls on that deal — so any
selector can be scored offline.

3,000 hands × 16 deals = **48,000 deals, 288,000 rounds.**

| value per round, game points | mean ± SE (clustered by hand) |
|---|---|
| random contract | −2.6 ± 0.7 |
| rule-based selector, hand-written weights | 116.6 ± 1.5 |
| per-hand best call, cross-fitted | 132.3 ± 1.9 |
| best contract in hindsight (unattainable) | 240.1 ± 1.5 |

**Regret 15.7 ± 1.4 per round**, concentrated in the ×1 suits: calling Ecken or Schaufel cost 46–56
a round against the alternative, Herz or Kreuz 12; Obenabe, Undenufe and the shove were
under-called.

### 6.3 Fitting the weights

The selector is **linear in its 51 weights**, so all 48,000 deals evaluate as one matrix product
(verified identical to `select_trump`). A coordinate walk searched the weights on half the hands and
was scored on the other half; the JSON's shape is unchanged, so both implementations pick it up.

| | held-out value per round | calls |
|---|---|---|
| hand-written weights | 117.9 | Ecken 18%, Herz 24%, Schaufel 20%, Kreuz 25%, Obenabe 4%, Undenufe 9%; shove 27% |
| **tuned weights** | **152.7 (+34.8 ± 1.8)** | Ecken 11%, Herz 14%, Schaufel 11%, Kreuz 14%, Obenabe 18%, Undenufe 33%; shove 51% |

The held-out gain exceeds the cross-fitted regret because that estimate is conservative (§2).

**In play**, tuned against hand-written weights:

| instrument | result | n | p |
|---|---|---|---|
| **whole games to 1,000** (card play 2,400) | **58.31% ± 26.76** of games | 800 pairs | ~0, t ≈ 8.8 |
| rounds, `HOUSE` (card play 38,400) | **51.73% ± 9.61** of game points | 2,000 deals | 9e-16 |

The tuned weights pass every judgement test in `tests/test_trump.py`. Two are ugly and harmless: the
length bonus for 8 and 9 trumps (65, 56) only decides hands that call trump anyway.

### 6.4 A unit bug that nearly shipped

The first pass multiplied `RoundScore.total` by the multiplier again, scoring every call by the
**square** of its multiplier. That fit called Undenufe 41% of the time, beat the hand-written weights
53.25% in a round match scored the same wrong way, and chose Undenufe on six hearts headed by Puur,
Nell, ace and king. The tell was arithmetic: Herz was valued at 600 on that hand, and the most a ×2
contract can move the score is (157 + 100) × 2 = 514. Every figure above is from the corrected data.

### 6.5 The open question

The tuned selector calls no-trump contracts about half the time. Simulated on the disputed six-heart
hand, Herz (300 ± 17), Obenabe (322 ± 26) and Undenufe (336 ± 31) are within noise of each other.
Whether the shift is a fact about Schieber or about how *our bots* defend a no-trump contract is
invisible bot against bot — both teams are the same bot. It is the first thing to check against
people.

---

## 7. Everything else measured

| lever | result | n | verdict |
|---|---|---|---|
| server bots at 153,600 instead of 2,400 | +0.56 (the §3b figure) | 3,000 | shipped (browser already had it) |
| table conventions on vs off (the first, tie-only version) | 50.15% ± 3.07 | 600 | null; kept (readable to humans) |
| researched conventions, tie window (0.05 of visits, 0.01 of score) | 50.15% ± 4.84 | 1,000 | free (§5u) |
| researched conventions at a price of 0.01 | 50.03% ± 5.71 | 1,000 | **free; shipped** — 73.2% predictable (§5u) |
| researched conventions at a price of 0.02 | 49.49% ± 6.74 | 1,000 | **loss** (p = 0.018) — 79.7% predictable |
| discard-signal reading, voting search | 49.85%, then 50.47% (p = 0.049), then 49.99% | 600, 600, 1,000 | null — did not replicate |
| discard-signal reading, shared tree | 49.645% ± 0.075 SE | 3,000 | **loss**, off |
| bidding prior as sampling tilt | 50.03% ± 6.54 (voting); 50.03% ± 5.72 (shared) | 1,000; 1,500 | null |
| game objective v1 / v2 / v3 (games, target 2,500) | 44.62% / 46.88% / 50.25% | 400 games | v3 kept, no strength claimed |
| `weis_draws` 16 → 64 | 50.06% ± 4.60 | 1,000 | null |
| called-Weis beliefs at equal wall-clock (at 2,400) | 50.11% ± 0.12 SE | 3,000 | null at equal time; shipped because compute was not scarce |

---

## 8. Cost and throughput

| | Python | Rust | Rust → wasm |
|---|---|---|---|
| random rollouts / s | 71,000 | 2,500,000 | — |
| voting-search iterations / s | 35,000 | 1,664,000 | 1,194,000 |
| ms per move at 2,400 iterations | 68.6 | 1.44 | 2.01 |

A move at the shipped 153,600 iterations: median **~144 ms** natively without beliefs (max ~210 ms),
**~670 ms** with beliefs under load (max ~870 ms). The bot service budget is 1,500 ms; the web app's
pacing absorbs search time rather than adding to it. The owner's standing decision (2026-09-15):
strength over speed, a few seconds a move is acceptable.

---

## 9. Threats to validity

1. **Bots against bots, and against themselves.** Every number is our agents playing our agents.
   The play model and the belief network were fitted to those same agents, so the belief gains are
   partly the bots reading their own clones. With random play at the table the offline value fell
   from 0.12 to 0.05 of an oracle. Humans will sit somewhere between.
2. **No human measurement.** The only human figures are external: experienced teams scored 49.5% ±
   14.2% against the published DMCTS over 136 rounds, and humans with a DMCTS partner 44.47% ± 13.74%
   over 832 rounds — five points below all-human teams.
3. **Gains are not additive by assumption.** Trump tuning (+1.73), beliefs (+1.31) and the server
   budget (+0.56) were each measured against a baseline without that change. They act on different
   decisions (bidding, sampling, compute), which makes rough additivity plausible, but it has not
   been measured, and the cheating-agent gap (57.35%) predates both of the large changes.
4. **Conditions vary.** Sections up to §5k ran under `EVAL`, most later ones under `HOUSE`; budgets
   differ between experiments (labels at 2,400, the trump round match at 38,400, beliefs at 153,600).
   Each table states its conditions; comparisons across tables are approximate.
5. **Stale numbers.** Three of the most-cited results (budget saturation, the endgame solver, the
   ladder) were true of the voting search and were carried across the change to ISMCTS without being
   re-taken. Any figure measured before a change to the component it describes should be treated as
   a hypothesis about the current engine.
6. **Multiple comparisons.** Sweeps (exploration, prior weights, risk) report the best of several
   settings. A single p near 0.05 inside a sweep is weak evidence; only replicated results shipped.

---

## 10. Open work, with the size of the question

| question | why it matters | what it takes |
|---|---|---|
| belief network at γ = 1 | offline +0.03, in play 50.15% (p = 0.24) | ~6,000 deals to resolve +0.2; not worth it unless the network improves |
| better beliefs of any kind | three routes, all null in play (§5r) | closed for now: the channel is saturated at the shipped setting |
| no-trump share of the tuned selector | largest unexplained behaviour change | human games, or a stronger defensive bot to re-price contracts |
| tree policy at the full budget | +0.39 lean at equal time | ~6–8 h for 1,000 deals at 153,600 |
| re-take the cheating-agent gap | the ceiling predates the two big gains | ~800 deals |
| any measurement against people | the only strength that matters to a player | an instrumented app, not an arena |
| learning past the search | beliefs from learned models were the only learned gain | expert iteration on self-play, if a GPU is available |
| more from convention self-play | one retrain on convention play was worth +0.45 (§5w); the corpus was 12,000 rounds | a larger corpus, or a model with more than 32 hidden units |

---

## 11. Reproducing

```bash
# A/B any two agent settings; appends to arena/results.jsonl
python -m arena.ab --a belief_alpha=0 bid_alpha=0 --deals 1000 --seed 91 --cfg house

# equal time: give the dearer arm fewer iterations
python -m arena.ab --a tree_policy=true iterations=360 --b iterations=3840 --deals 1000 --cfg house

# trump: price every call, report regret, tune the weights
python -m arena.contracts generate --hands 3000 --deals 16 --out contracts.npz
python -m arena.contracts regret contracts.npz
python -m arena.fit_trump contracts.npz --out trump_weights.json

# play model and beliefs
python -m arena.policy_data --rounds 6000 --iterations 38400 --out decisions.npz
python -m arena.train_policy decisions.npz --out krass_jass/data/play_policy.json
python -m arena.belief_quality --rounds 300 --save-probes probes.pkl
python -m arena.belief_data --rounds 6000 --out beliefs.npz
python -m arena.train_belief beliefs.npz --h1 64 --h2 32 --l2 1e-4 --out belief_net.json
python -m arena.belief_quality --load-probes probes.pkl --belief-net belief_net.json
```

Every deal and every decision seed derives from `(seed, index)`, so any match replays bit for bit.
