# Measurements — M3 / M4

Measured 2026-09-10 to 2026-09-15 on an M2 (8 cores), Python 3.12, Rust search core. Double
rounds, paired t-test, agents bidding for trump. Sections up to §5k ran under `EVAL`
(Weis/Stöck/match off); from §5l on, most ran under `HOUSE`, and each table says which.

**For the current state in one place, read `docs/engine-report.md`.** This file is the dated
record, in the order things were measured, with superseded results left in and marked.

**Hand-recorded and therefore perishable.** `docs/documentation-plan.md` §3 specifies the
CI-artifact pipeline that should replace this file. Until it exists, read every number as
dated rather than current.

---

## 1. Baseline ladder

n=300 double rounds. Rule-based trump selection for **all** agents, so these compare card
play only.

| Matchup | Share | p |
|---|---|---|
| greedy vs random | 49.90% ± 8.82 | 0.84 — **not significant** |
| dmcts(2.4k) vs random | 65.33% ± 8.11 | ≈0 |
| dmcts(2.4k) vs greedy | 66.75% ± 7.54 | ≈0 |
| cheating vs dmcts(2.4k) | 56.01% ± 7.40 | ≈0 |
| cheating vs dmcts(40k) | 55.73% ± 6.73 | ≈0 |

**Greedy is still indistinguishable from random**, now with trump selection held constant so
the comparison is purely card play. "Play your highest-value legal card" dumps aces into
tricks it was never going to win. Keep it as a floor; never cite it as a rung that means
anything.

---

## 2. Trump selection is worth what the research said

Identical card play on both sides, only the bidding differs. n=600.

| Matchup | Share | p |
|---|---|---|
| rule-based trump vs random trump | **58.49% ± 14.76** | ≈0 |

58.49 against 41.51 is a **17-point spread**. `PLAN.md` §3.1 puts it at ~16. **Reproduces.**

Note the standard deviation: 14.76%, roughly double what card-play comparisons show. Trump
choice is high-variance — a bad contract loses the deal before a card is played. Budget more
deals for any experiment that varies bidding.

This result matters beyond its own conclusion: reproducing one published finding on our own
engine is evidence the harness is sound, which makes §3 harder to wave away as our bug.

---

## 3. Search budget saturates near 2,400 iterations

> **Superseded.** §3b re-ran this and the budget keeps paying to 64x — +0.56 of a round's
> share under HOUSE and +0.70 under EVAL, both over 3,000 deals. These figures were taken
> on the voting search that §5h replaced, and the number was carried across that change
> without being re-taken. It set the app's budget until then.

Every budget played against a fixed 40×60 = 2,400-iteration reference, endgame solver off,
agents bidding, n=500.

| Budget (dets × iters) | Share vs ref | p |
|---|---|---|
| 6 × 10 = 60 | 43.71% ± 7.71 | ≈0 |
| 20 × 40 = 800 | 49.14% ± 7.58 | 0.011 |
| 40 × 60 = 2,400 *(reference)* | — | — |
| 80 × 100 = 8,000 | 50.03% ± 6.12 | 0.92 — not significant |
| 200 × 200 = 40,000 | 50.23% ± 6.54 | 0.43 — not significant |

And at the top end, with the endgame solver on:

| Matchup | Share | n | p |
|---|---|---|---|
| dmcts(40k) vs dmcts(2.4k) | 50.30% ± 7.31 | 1000 | 0.20 |
| dmcts(800k) vs dmcts(40k) | 49.60% ± 6.27 | 300 | 0.27 |

At n=1000 the standard error is 0.23%, so the 16× comparison resolves anything above about
0.5%. These are well-powered nulls, not failures to measure.

**333× compute from 2,400 to 800,000 iterations buys nothing measurable.**

### Two hypotheses tested and rejected

- **"The endgame solver masks it"** — it plays tricks 5–9 identically for both agents, so
  only four decisions could differ. Rerun with the solver disabled: 50.00%, p=0.99, n=400.
  Not the explanation.
- **"Random contracts hide it"** — the original sweep drew contracts at random because trump
  selection did not exist. Rerun with real bidding: the low end sharpened slightly (800
  iterations went from p=0.14 to p=0.011) but everything above 2,400 stayed flat. Not the
  explanation either, and this was the one I expected to be right.

A third check rules out a broken search: 2,400 iterations beats 60 by 5.4% (p≈0, n=400), and
the sweep's low end is steep. Search works. It simply stops paying after ~2,400.

### This contradicts the plan, deliberately left in place

`PLAN.md` §3.1 and `CLAUDE.md` record "~1000 determinizations × 800 iterations" as settled,
under a heading saying not to rediscover it. It does not reproduce here. Remaining
explanations, now that the cheap ones are gone:

1. ~~The published figure may be **budget allocation** guidance — how to split a fixed 800k
   rollout budget between determinizations and iterations.~~ **Ruled out, see §3a.** The split
   is flat across an 8× range either side of ours.
2. Their evaluation differed (no exact endgame solver, different opponents, Weis on).
3. Our search converges to its ceiling faster than theirs for a reason not yet identified.

### 3a. How the budget is split, at a fixed budget

The saturation above was measured at one allocation — 40 worlds × 60 iterations — which
leaves the obvious objection that what saturated was *that split*. It did not. A fixed 2,400
iterations, endgame solver off, each split played 600 double rounds against the shipped one:

| split | share | p |
|---|---|---|
| 4 × 600 | 48.89% ± 7.13 | 1.3e-04 |
| 10 × 240 | 49.65% ± 6.74 | 0.20 |
| 20 × 120 | 50.39% ± 6.79 | 0.16 |
| **40 × 60** | reference | — |
| 80 × 30 | 50.27% ± 6.41 | 0.30 |
| 240 × 10 | 47.56% ± 7.71 | 1e-14 |
| 600 × 4 | **41.41%** ± 8.33 | ~0 |

An inverted U with a broad flat top and two hard floors. The search needs **at least ~10
worlds and at least ~30 iterations in each**; given both, nothing in between matters, and
depth varies 8× across the plateau with no measurable effect. Four worlds overfits the sample
of hidden cards; four iterations barely solves a world at all and costs 8.6 points.

So there is nothing to win by re-splitting, the shipped setting is already mid-plateau, and
the allocation explanation for the discrepancy with the published figure is closed.

Do not delete their figure. Do not adopt ours as universal.

---

## 3b. §3's saturation does not hold — and not for the reason first given

§3 is the most-cited number in this file: the search saturates near 2,400 iterations, and
333x more buys nothing. Every budget decision since has leaned on it, including the one in
the app.

It does not hold under HOUSE.

| budget | vs 2,400 | deals | p |
|---|---|---|---|
| 9,600 (4x) | 50.41% | 600 | 0.096 |
| 38,400 (16x) | **50.370% ± 0.113** | **3,000** | **0.001** |
| **153,600 (64x)** | **50.560% ± 0.118** | **3,000** | **2e-06** |
| 614,400 (256x) | 50.64% ± 6.05 | 600 | 0.0096 |

Four seeds, pooled within each budget, all against the same 2,400 reference. The curve rises
to 64x and is flat after it: 256x costs 4.7x more and is worth at most +0.08, inside its own
noise.

### The explanation I first gave, and the control that killed it

The obvious reading was that the conditions differ: §3 ran under `EVAL`, which switches Weis
off, so nothing constrained which worlds got imagined and extra iterations bought more
guesses from the same flat distribution. Under HOUSE every world is rejection-sampled
against what the table called — §5m measured that rejecting **80.4%** of them — so extra
iterations would buy more *accepted* worlds, the belief lever of §5k.

It is wrong. The same sweep, run under EVAL on today's code:

| | share | deals | p |
|---|---|---|---|
| EVAL, 153,600 vs 2,400 | **50.695% ± 0.121** | 3,000 | **8.3e-09** |
| HOUSE, 153,600 vs 2,400 | 50.560% ± 0.118 | 3,000 | 2e-06 |

The budget pays *slightly more* under EVAL, not less. The Weis constraints have nothing to
do with it, and §3 is not condition-dependent — it is simply wrong for the engine that runs
today.

**The candidate that fits.** §3 predates ISMCTS. It measured a search that built a fresh
tree per imagined deal and voted, and saturation is what that design should do: past some
point each new world's private tree is solved well enough that another one changes no votes.
ISMCTS (§5h) shares **one** tree across worlds, so an extra iteration deepens the same
statistics instead of starting over — and there is no reason for that to level off at the
same place. §3 was a correct measurement of a search that was replaced four sections later,
and its number was carried across the change without being re-taken. That is the more
uncomfortable failure of the two: not a wrong experiment, a stale one.

And that one holds. The same sweep, same conditions, same budgets, with `ismcts=False`:

| search | 153,600 vs 2,400, EVAL | deals | p |
|---|---|---|---|
| PIMC — a tree per world, then a vote | **50.140% ± 0.146** | 2,000 | **0.34** |
| ISMCTS — one shared tree | **50.695% ± 0.121** | 3,000 | **8.3e-09** |

The voting search saturates and the shared tree does not, under identical conditions. The
difference between them is +0.55 ± 0.19, p≈0.004. §3 measured a real property of a real
search; that search was replaced in §5h and the number was not re-taken.

**The lesson is about bookkeeping, not about search.** A measurement is only valid for the
thing it was taken on, and §3 carried its authority across a change to the very component
it described — for four sections, into the app's budget, and into three later arguments that
cited "the search saturates" as settled. Nothing in the file marked it as depending on the
algorithm, because when it was written there was only one. Every figure taken before §5h
deserves the same question asked of it.

**What ships.** The app moves from 2,400 to 153,600. In wasm that is roughly half a second
a move against the 550–1500 ms the app was already spending on an artificial pause, so the
pause now *absorbs* the search instead of being added to it: measured at 1.0–1.2 s between
bot moves, the same band as before. A stronger bot that felt slower would have been a bad
trade; this one does not feel different at all.

---

## 3c. What the bigger budget did *not* unlock

§3b raised the budget 64x, so two constants that were set when a move had to cost
milliseconds were worth re-asking at the new one. Both survive unchanged.

| lever | at 153,600 | share | deals | p |
|---|---|---|---|---|
| `resample_every` 4 -> 1 | a fresh world every iteration | 50.125% ± 0.098 | 2,000 | 0.20 |
| `weis_draws` 16 -> 64 | buy down the worlds that ignore the calls | 50.06% ± 4.60 | 1,000 | 0.66 |

**`resample_every` stays at 4.** §5h set it there as a *cost* compromise — drawing a world
costs far more than an iteration, and 1 was 1.95x the price for the same gain. The obvious
guess was that with 64x the budget the compromise had stopped being necessary and world
diversity would now be cheap enough to buy. It is cheap enough, and it is worth nothing:
the search already sees 38,400 distinct worlds at `resample_every=4`, which is evidently
past the point where more of them tell it anything.

**`weis_draws` stays at 16.** §5m capped the rejection sampling at 16 draws and noted that
at 80.4% rejection this leaves ~3% of worlds contradicting what the table called. Quadrupling
the cap removes most of that 3% and changes nothing measurable — the residue is concentrated
in the rare loud calls, which are exactly the ones where a single seat's holding is nearly
pinned by the shown cards anyway.

Both are the same shape of result and worth naming as such: a constant chosen under a
constraint does not automatically become wrong when the constraint lifts. §3b's budget was
stale because the *algorithm* underneath it changed; these two were only ever cost
compromises, and the thing they traded away turns out not to have been worth much.

---

## 3d. A deeper exact solve makes it worse

The endgame solver replaces the search with an exact double-dummy solve once few enough
cards remain, at five each. With 64x the budget available, six looked affordable — a 6-card
solve is roughly 20x a 5-card one, about 2.4 s a move at 40 determinizations, which the
paradigm now allows.

| | share | deals | p |
|---|---|---|---|
| `endgame_cards` 5 -> 6 | **49.350% ± 0.110** | 2,000 | **3.2e-09** |

**-0.65 of a round's share, and consistent across both seeds** (chi-squared 0.41 on 1 df).
Not a null — a loss, and a large one by this file's standards. It is the mirror image of
§5h and the same mechanism read backwards.

An exact solve is *perfect information inside the world it is given*. Deepening it does not
reduce error, it buys certainty about worlds that are mostly wrong, and then holds an
election between those certainties. That is precisely the strategy fusion §5h measured
ISMCTS beating: a shared tree has to commit to one move across every world it cannot tell
apart, and a vote over exact solves does not. Solving each imagined deal *better* makes the
fusion worse, because the per-world answers grow more confident and more divergent at once.

So the thing to be careful about generalising from §3b is this: more thinking is not
uniformly good. More thinking **in the shared tree** pays to 64x. The same compute spent
making each imagined world individually exact costs two thirds of a point.

**The open question this opens.** If six is worse than five, five may already be too deep.
`endgame_cards=0` — no solver at all, ISMCTS to the last card — is the test that says whether
the solver is earning its place or has been a small standing liability since it was written.
That run is in flight.

---

## 3e. The exact endgame solver was the single biggest thing wrong

§3d found a *deeper* exact solve losing two thirds of a point and asked the obvious next
question: if six is worse than five, is five too deep? It is. So is four. So is one.

| `endgame_cards` | vs 5, at 153,600 | deals | p |
|---|---|---|---|
| 6 | 49.350% ± 0.110 | 2,000 | 3.2e-09 |
| 4 | 50.50% ± 3.70 | 1,000 | 1.8e-05 |
| **0 — no solver at all** | **51.707% ± 0.074** | **4,000** | **~1e-118** |

Monotone in depth, three seeds at zero agreeing to chi-squared 1.47 on 2 df, and **+1.71 of
a round's share** — larger than ISMCTS's +1.15 (§5h), larger than everything else in this
file put together. It is also not a budget artefact: at the *old* 2,400-iteration budget it
is +1.41 (n=1,000). It has been true the whole time.

### Why a provably optimal component made the bot worse

The solver is not wrong. Given four hands it returns the exact double-dummy value, and
nothing beats exact. The error is in what it is exact *about*.

Below the threshold the search stops being ISMCTS and becomes: deal a world, solve it
perfectly, vote. That is PIMC — the design §5h measured ISMCTS beating by 1.15 — and making
each vote *perfect* does not fix it, it sharpens it. Every world yields a confident answer
to a question about a deal that is mostly wrong, and the election between confident wrong
answers is worse than one shared, hedged policy over all of them. The solver replaced the
one part of the engine that handles hidden information with the one part that cannot.

**The same root cause as §3b, for the third time tonight.** The endgame solver was written
when the search voted, and against a voting search it was a clear improvement. §5h changed
the algorithm and nothing that depended on the old one was re-taken: not §3's saturation,
not this. Both survived because they were correct when written and nobody asked the question
again.

What ships is a deletion: `endgame_cards` defaults to **0**, the browser bot runs ISMCTS to
the last card, and a move gets *cheaper* as well as stronger. The flag and `endgame.rs` stay,
because the solver remains the right answer for a search that votes — and because the next
person to wonder should be able to re-run it rather than rebuild it.

---

## 3f. The pre-§5h sweep: what else changed when the algorithm did

§3b, §3d and §3e were all the same failure — a figure taken on the voting search and left
standing after §5h replaced it. So the rest of the pre-§5h results were re-run against
today's engine (shared tree, no endgame solver, 153,600 iterations).

| | then, on PIMC | now, on the shared tree | deals | p |
|---|---|---|---|---|
| `signal_reading` on | null, twice (§5c) | **49.645% ± 0.075** | 3,000 | **2.3e-06** |
| `read_bidding` on | null (§5e) | 50.03% ± 5.72 | 1,500 | 0.82 |

**`signal_reading` is not null any more — it is a loss.** Reading the discard convention into
which worlds get imagined costs **0.36** of a round's share, replicated across two seeds at
chi-squared 0.36 on 1 df. It has been off since §5c on the strength of two nulls; it stays
off, now for a positive reason rather than an absence of one. The mechanism is presumably the
one §3e made vivid: the shared tree pools statistics across worlds, so skewing *which* worlds
turn up biases one policy rather than being averaged out across independent votes. A prior
that was harmless noise to a voting search is a systematic tilt to this one.

**`read_bidding` survives unchanged.** Still null, and still on — the one pre-§5h verdict in
this sweep that transfers. §5e's reasoning about why (a prior only flips decisions the
search already rates within 0.008 of each other) is untouched by any of tonight's results.

### The ladder, re-taken — and why its old figures are not carried forward

`arena/ladder.py` describes its rungs as comparing *card play*, and
`docs/measurements.json` says so: "rule-based trump selection for all agents". The code did
not do that. `RandomAgent` bids at random by default, so every rung above the floor was
measuring bidding as well. Running the ladder as it stood put `greedy vs random` at 57.55%
against a recorded 49.90% — a seven-point move in a rung where neither side searches at all.
Forcing the stated condition brings the floor back to **50.46%**, which is the recorded
number. The code now enforces what the artifact claims.

Re-taken at n=300, seed 1, on today's engine:

| | share | p |
|---|---|---|
| greedy vs random | 50.46% ± 8.70 | 0.36 |
| dmcts(2.4k) vs random | 67.27% ± 8.04 | ~0 |
| dmcts(2.4k) vs greedy | 67.79% ± 8.22 | ~0 |
| dmcts(40k) vs dmcts(2.4k) | 50.31% ± 6.26 | 0.39 |
| cheating vs dmcts(2.4k) | 58.59% ± 6.55 | ~0 |
| cheating vs dmcts(40k) | 57.58% ± 6.05 | ~0 |

**The old figures are not carried forward, and no trend should be read against them.** They
do not reconcile: this bot is independently measured as 1.75 stronger than the one those
numbers describe (`endgame_cards` 0 vs 5 under EVAL at 2,400 — 51.75% ± 4.89, n=1,500), which
should have *narrowed* the cheating rung, and instead it reads wider. Either the recorded run
used a configuration nobody wrote down, or something else moved with it. The provenance is
not recoverable from the artifact, so the honest thing is to replace the numbers and say why
rather than to explain the difference.

One number from it does survive being re-asked, and it is the one worth keeping: **40,000
iterations still beats 2,400 by nothing** (50.31%, p=0.39) — while 153,600 beats it by 0.56
(§3b). The budget curve is real but shallow until it is large.

### Where the bot stands against perfect information

| | share | deals |
|---|---|---|
| cheating vs us, both with no endgame solver, 153,600 iterations | 57.35% ± 6.46 | 800 |

**This is not comparable to §4's 56.01%** and must not be read as the gap having widened.
§4 ran both sides on the voting search with the solver in and at very different budgets; this
runs both on the shared tree with it out. Two numbers measured on two engines. Restating §4
properly means re-running its whole ladder, which is the obvious next job and has not been
done. What can be said is the narrow thing: measured today, against this bot, seeing all four
hands is worth about seven points of a round's share.

---

## 4. The cost of hidden information, and search does not pay it

| Matchup | Share | n |
|---|---|---|
| cheating vs dmcts(2.4k) | 56.01% ± 7.40 | 300 |
| cheating vs dmcts(40k) | 55.73% ± 6.73 | 300 |

**~6% of points is the price of playing with hidden cards.** A 16× search increase moves it
by 0.28% — under half a standard error.

Two things this is not:

- **Not a hard bound.** The cheating agent is itself DMCTS with a single determinization, not
  an optimal perfect-information player. The true cost is *at least* this.
- **Not evidence about humans.** Nothing here has been measured against a person.

### The expected shape

Determinized search has a known ceiling: strategy fusion. Each determinization is solved as
though the hidden cards were known, so the search never values an action for what it
*reveals* or *conceals*, and averaging more determinizations converges faster to the same
fixed, suboptimal policy. Steep gains to ~2,400 iterations, then a plateau no compute moves,
is exactly that signature.

**The remaining gap is not a search problem.** Closing it needs learning — see
`docs/value-net-plan.md`, which starts from §5e's conclusion that only the leaf evaluator and
the aggregation can move decisions the search holds a strong opinion about.

### An external measurement of the partner half

Niklaus §13 ran a second human experiment we had not recorded: **47 humans playing with a
DMCTS partner scored 44.47% ± 13.74% over 832 rounds**, about five points below the all-human
team's 49.5%. A human is worse off with a bot partner than with a person — which is the
partner gap stated from the outside, and stronger evidence for it than anything measured here,
since everything in this file is bots against bots.

---

## 5. What this changes

**Serve 2,400 iterations.** Indistinguishable from 800,000, and single-digit milliseconds in
the Rust core. The latency-budget question open since M0 does not bind and can be closed.

**The Rust port's stated justification was partly wrong.** `docs/plan-review.md` §1 argued M5
needs a teacher ~100× the student's search. On this evidence a 100× teacher is no stronger,
so distilling one buys nothing over distilling a cheap one. The port still earns its keep —
reinforcement learning needs *millions of games*, and 2,400 iterations × 36 moves × millions
remains far beyond Python — but the reason is throughput of **games**, not depth of
**search**. Recorded here rather than quietly amended there.

**M5 needs rethinking before it is built.** As written it distils a high-budget DMCTS teacher
for serving speed. Speed is not the problem, and the teacher is not stronger. The version
worth building is the one that gets *past* DMCTS rather than compressing it — expert
iteration, per the discussion of team play and signalling.

---

## 5b. Table conventions cost nothing

The bot now orders moves the search rated the same by two table conventions: it discards the
sister suit of the one it wants led (`♦/♥` and `♠/♣` are the colour pairs), and it cashes a
side-suit winner when the opponents are *proven* out of trump. Both are about being readable
to a human partner rather than about winning the trick in front of it — determinized search
is a strong individual player and a poor partner, and that does not change here.

The conventions only reorder moves the search could not separate, so the claim worth testing
is the negative one.

| | share | n | p |
|---|---|---|---|
| conventions on vs off, same budget | **50.15% ± 3.07** | 600 | 0.22 |

Standard error 0.13%, so a cost larger than about a quarter of a point would have shown.
It did not. The conventions fire on roughly 5% of decisions at the serve budget; the rest of
the time the search had a preference and keeps it.

What is *not* implemented is reading the convention back. A human playing it at the bot will
not be understood, which is the same partner-modelling gap §5 describes and the reason expert
iteration is the interesting direction rather than more search.

---

## 5c. Reading the signal is worth nothing — twice

The other half of a convention is reading it. `krass_jass/reading.py` turns a seat's discards
into a per-suit prior (threw Ecken → short in Ecken, asking for Herz) and `determinize.rs`
samples the imagined worlds accordingly, weighted `2^affinity` and bounded four-to-one either
way so that no world is ever removed. Against a partner who ignores the convention it costs
sampling efficiency, never correctness — which is the property a hard constraint would not
have, and the reason this is not the learned-distribution idea PLAN §3.1 warns about.

It does not help.

| | share | n | p |
|---|---|---|---|
| reading vs blind, our own bots as partner | 49.85% ± 4.96 | 600 | 0.46 |
| reading vs blind, a *disciplined* signaller as partner | 50.47% ± 5.87 | 600 | **0.049** |
| the same, fresh seed | 49.99% ± 5.64 | 1000 | 0.95 |

The middle row is the interesting one, and it is why the third exists. The first null had an
obvious candidate explanation — our bots only apply the convention among moves the search
rated the same, so most of their discards carry no intent and there is nothing to read. So
the sender was replaced with one that plays the convention on *every* discard, which is what
a human who signals deliberately does. That came back at p = 0.049, in the predicted
direction.

It did not replicate. A borderline p found on the second look, after a null, is exactly the
result most likely to be noise, and it was: the same match on a fresh seed and a larger
sample is dead flat. **Reported as a null.** Had the replication been skipped, this section
would be claiming a discovery.

So the published negative result stands even for a prior built from a convention rather than
fitted to a corpus. The reading is off by default and stays behind a flag
(`DmctsAgent.signal_reading`, and `READ_SIGNALS` in `wasm_api.rs`) so the next person to have
the idea re-runs the match instead of rebuilding the machinery.

**Where this leaves partner play.** The gap is real and neither convention closed it. What
the search optimises is one round's *share of card points* — `pts[team] / (pts[0] + pts[1])`,
including the five for the last trick and the match bonus. Nothing in that objective knows
the game score or the target, so at 940 chasing 1000 the bot still maximises share when it
needs exactly 60 points, and the Stöck-Weis-Stich ordering that decides a shared crossing is
invisible to it. That is a bigger and more promising target than signal reading.

---

## 5d. Playing for the game, not the round — three tries to get to harmless

The search maximised its **share of one round's card points**. That is the right objective for
a round played alone and the wrong one for a game: at 940 chasing 1000 a team needs sixty
points, not as many as possible, and a share objective is linear so it cannot tell a certain
sixty from a gamble on ninety-or-twenty.

Measuring it needed a new instrument. `arena.py` plays single double-rounds with
`target_score=None` — there is no line to play to, so the objective under test does not exist
there — and worse, a points metric scores the change *backwards*, because a bot that takes a
safe sixty gives up points on purpose. `arena/games.py` plays whole games to the target,
paired with the sides swapped, and counts games won.

| version | target 1000 | target 2500 |
|---|---|---|
| v1 — logistic scaled to one round | 50.75% (p=0.48) | **44.62%** (p=3e-06) |
| v2 — scale by √(rounds left) | 50.50% (p=0.66) | **46.88%** (p=0.004) |
| v3 — projection only near the line | 49.38% (p=0.58) | 50.25% (p=0.78) |

**v1** saturated. A fixed scale of one round's points put any real lead at ~0.99, so every
move scored the same and the search had no gradient. The longer the game the more of it was
spent in that dead zone, which is the 1000-against-2500 split.

**v2** fixed the scale — a lead is worth what is left to happen to it, and points accumulate
like a random walk, so the spread of the remainder grows with √(rounds remaining). Still lost.
That second failure is what said the *shape* was wrong rather than the constants: with
twenty-five rounds to play one round genuinely barely moves the win probability, so nearly
every rollout comes back at ~0.5 and UCT has nothing to separate the moves with. **A correct
objective with no variance is a worse search than a proxy with plenty.**

**v3** only lets the projection take over as the line comes into reach — beyond four rounds
out the reward is the round's share, bit for bit the old bot, which is why it cannot give
ground where the first two did.

Null, then, not a gain: it acts only in the last round or two of a game, and at n=400 games
the interval is ±2.2%. It is kept because playing for the round when the game has a finishing
line is wrong regardless of whether the wrongness is detectable, and because v3 provably
reduces to the previous behaviour everywhere else. **No strength is claimed for it.**

Two gaps left in it deliberately: both teams crossing at once is scored ½, because who wins
depends on the Stöck-Weis-Stich ordering the search cannot see; and Stöck is left out of the
projection, since it is private until the second honour is played and feeding it to the agent
would hand it information the table does not have. Weis is public once called, and is in.

---

## 5e. Why a determinization prior cannot help — with the mechanism

Five different priors have now been put on the world sampler. All five measured nothing:
void constraints were already in and are exact, and on top of those came the discard
convention (§5c, two nulls), and the bidding — which is the strongest signal available.

| prior | share | n | p |
|---|---|---|---|
| reads the bidding vs ignores it | 50.03% ± 6.54 | 1000 | 0.88 |

That last one should have worked. Unlike a convention it is *forced* — everybody bids — it is
there from the first card rather than accumulating, and the effect in the hands is large.
Measured over 40,000 hands put through the actual bidder:

| bid | frequency | aces (average 1.00) | cards in the chosen suit (random 2.25) |
|---|---|---|---|
| Obenabe | 2.8% | **2.66** | — |
| Undenufe | 7.1% | **0.53** | — |
| Schieben | 26.7% | 0.72 | — (and flat: 3.22 longest vs 3.63) |
| a suit | 63.5% | ~1.10 | **3.7** |

It still measured zero, so the next question is why — because five nulls is a pattern and a
pattern invites a sixth attempt.

**The mechanism.** Instrument the decisions the prior changes:

| | vote margin | |
|---|---|---|
| decisions the prior changed | **9.6 points** | 20% of decisions |
| decisions it left alone | **48.0 points** | 80% |

and the score gap between the two cards, as the *unprimed* search itself rated them, is
**0.0081** on a 0–1 scale — around 1.3 card points in 162.

A prior does not change what a world is worth. It changes which worlds get looked at, so it
can only move a decision whose vote was nearly split — and a nearly split vote is, by
definition, one where the search rated both cards the same. **It moves the answer exactly
where the answer does not matter**, and the direction it moves is inside the search's own
noise.

That predicts all five nulls at once, and it predicts the sixth.

**Qualified by §5k.** What this shows is that a *weak* belief correction can only reach
near-ties. It does not show that belief work is futile: replacing a fifth of the imagined
worlds with the truth is worth 2.52 points, far more than anything else measured here. The
priors above failed because they were small, not because beliefs do not matter. The obvious next idea is
reading the *lead* — a declarer who does not draw trumps is thinner in them, and our own bots
do play it: leading trump they hold 3.43 trumps, leading a side suit 2.76. Real, and about
half the strength of the bidding signal that already measured zero. It is not worth building.

**What this leaves.** To gain points you have to change decisions that currently have
48-point margins, and no prior can. Two places can:

- **the evaluation** — what a leaf is worth. It is a *random playout*, which sets the value of
  every world and is the crudest component in the engine.
- **the aggregation** — how worlds become one choice. Voting discards the constraint that
  makes the game hard: one card has to work across worlds you cannot tell apart.

Both move large-margin decisions. Neither is a prior. That is the same conclusion §5c reached
about partner play, arrived at from a different direction.

---

## 5f. Risk aversion in the reward buys nothing

Determinized search is over-optimistic by construction: inside every imagined world it knows
the layout, so it believes it can dodge disasters it cannot see coming. A risk-averse reward
is the obvious counter-bias — dislike the rounds where you get buried, more than linearly.

The obvious *form* of it is a trap worth writing down. A penalty of
`(ours - λ·theirs) / total` expands to `(1 + λ)·share - λ`, an **affine** transform of the
share, and MCTS picks the child with the highest mean reward — so it cannot change which
child that is. It would measure exactly nothing. (It does rescale the value against UCT's
unscaled exploration term, so it is a disguised exploration-constant change. That constant is
1.5, inherited from the published work and never tuned here: a separate, untested experiment.)

What was tested instead is a kink — slope `1 + λ` below a 40% share, `1` above, which is
concave and therefore risk-averse. At λ=1 a certain 0.4 scores 0.571 against a coin flip on
0.2/0.6 at 0.500.

| λ | share | p |
|---|---|---|
| 0.25 | 50.34% ± 6.58 | 0.21 |
| 0.5 | 49.53% ± 6.14 | 0.059 |
| 1.0 | 49.60% ± 6.82 | 0.15 |
| 2.0 | 49.68% ± 6.92 | 0.25 |

n=600 each, EVAL, paired, against the linear reward. All null, no dose-response upward, and
the nearest thing to a signal is on the losing side. **The optimism is either not large or not
reachable by reshaping the reward.** Kept behind `DmctsAgent.risk_lambda`, default 0.

**What this does and does not say about §5e.** It changes what a world is worth, so it is not
a prior — but it changes the reward's *shape*, not the leaf estimate's *accuracy*. A monotone
reshape can only move decisions where the outcome distributions differ between cards; a better
evaluator moves decisions where the search is simply wrong about a position. Different sets,
so `docs/value-net-plan.md` is not undermined by this. What it weakly supports is that the
~6-point gap lives in the **policy** — strategy fusion — rather than in the valuation, which
argues for ISMCTS alongside the value work rather than after it.

---

## 5g. The leaf evaluator: the kill criterion fired, and said something bigger

`docs/value-net-plan.md` Phase 0 fitted a 14-feature linear evaluator to replace the random
playout, deliberately targeting **the playout's own mean** so the experiment would isolate
variance and nothing else. It carried a prediction: §3a's collapse below ~30 iterations per
world should lift, if that floor is rollout noise.

| split | share | p |
|---|---|---|
| 40 × 60 | 40.87% ± 7.70 | ~0 |
| 240 × 10 | 41.07% ± 8.26 | ~0 |
| 600 × 4 | 43.47% ± 8.54 | ~0 |

Nine points worse, at every split, and the floor did not lift. The kill criterion fired.

**Why, quantitatively.** A single playout has RMSE 0.4299 against its own mean; the fitted
evaluator reaches 0.2315 — nearly twice as accurate *per call*, which is what made this look
promising. But the search does not use one call:

| split | per-world error | votes | after voting | evaluator |
|---|---|---|---|---|
| 40 × 60 | 0.118 | 40 | **0.019** | 0.232 |
| 240 × 10 | 0.288 | 240 | **0.019** | 0.232 |
| 600 × 4 | 0.430 | 600 | **0.018** | 0.232 |

The playout's error is **zero-mean**, so it washes out twice — averaging inside a world, and
again across every determinization's vote. The evaluator's error is **bias**: the same
position returns the same number in every world, so voting never removes any of it. Twelve
times worse in effect, and identical at all three splits, which is why the loss is the same
nine points at all three. (Votes are not perfectly independent, so 0.019 is optimistic — but
not by the order of magnitude that would change the conclusion.)

**This also re-reads §3a.** If estimator error after voting is flat across the splits, the
floor at ~30 iterations is not noise. It is that four iterations cannot build a tree: the
world is evaluated fine and never *searched*. Prediction made, prediction falsified, and the
mechanism turns out to be a different one.

**The architectural consequence, which outlives this experiment.** For a learned value to be a
drop-in replacement here it would need RMSE below ~0.02 against the true value. That is not a
hard target, it is an absurd one — the quantity being estimated has a standard deviation
around 0.3. **No value network will beat a 2,400-sample unbiased Monte Carlo estimator at
being that estimator.**

So "replace the playout with a learned value" is the wrong shape, and
`docs/value-net-plan.md` is wrong as written. A value network earns its place the way it does
in AlphaZero-style systems: with *far fewer* simulations, a policy prior carrying the load,
and an aggregation that is not a vote over perfect-information worlds. It is not a component
that can be swapped into this search — it comes with the aggregation change or not at all.
Which puts ISMCTS first, and the value with it rather than before it.

---

## 5h. Information Set MCTS — the first thing that made the bot stronger

Everything above this is a null or a correctness fix. This one moves.

`search.rs` builds a fresh tree per imagined deal, solves each as a perfect-information game,
and votes. That is PIMC, and the searching player effectively picks a different card for every
world it imagines and then holds an election. A real player cannot: they must choose one card
that serves every world they cannot tell apart. ISMCTS puts that in the data structure — **one
tree**, shared across every determinization, where a node is reached by a sequence of played
cards. Those are public, so a node *is* an information set, and it carries one set of
statistics and therefore one policy.

The correctness detail that makes it work: different worlds make different cards legal, so a
child counts how often it was **available** rather than dividing by the parent's visits. Get
that wrong and rarely-dealt cards look unpopular instead of untested.

| | share | n | p |
|---|---|---|---|
| ismcts vs random | 76.39% ± 12.64 | 300 | ~0 |
| ismcts vs greedy | 68.76% ± 7.31 | 300 | ~0 |
| **ismcts vs dmcts, equal iterations** | **50.72% ± 6.24** | 1000 | 2.4e-04 |
| *replication, fresh seed* | **51.23% ± 6.49** | 1400 | 1.3e-12 |
| *and again* | 51.15% ± 6.74 | 1400 | 2.0e-10 |
| **ismcts vs dmcts, equal wall-clock** | **50.53% ± 6.77** | 1400 | 3.4e-03 |

**+1.15 points at equal iterations, +0.53 at equal wall-clock**, replicated three times. The
equal-time figure is the one that matters and is the smaller one, because ISMCTS costs ~2x per
iteration: it draws a world every iteration where the determinized search draws forty in total.

### The mechanism, checked rather than assumed

If this wins by removing strategy fusion, the gap to a bot that sees all four hands should
narrow — that gap is what fusion costs. Same matchup, same seed, endgame solver off on both:

| | share |
|---|---|
| cheating vs dmcts | 59.13% ± 6.74 |
| cheating vs ismcts | 58.39% ± 6.21 |

It narrows by 0.74, consistent with the head-to-head gain. **So fusion is real and costs
points — and it is only about 8% of the hidden-information penalty.** It had been treated
here as *the* explanation for the ceiling on the strength of being the textbook answer; it is
a contributor. The other eight points remain unexplained, and non-locality is a hypothesis
rather than a measurement.

### Cost, and one wrong diagnosis

Under wasm the first implementation cost 80 ms a move against a native 3.6 ms — a far worse
ratio than the 1.4x wasm normally pays. The first hypothesis was allocation: ~20,000 `Vec`s
per move at node scope. Replacing them with a stack array improved *native* by 18% and moved
wasm not at all. The cost is `determinize` being called 2,400 times instead of 40, and being
much dearer under wasm's 64-bit arithmetic.

Sharing a world across several iterations recovers most of it. Whether that costs strength is
its own measurement, and it has a cliff in it:

| worlds shared | cost vs dmcts | share vs dmcts | p |
|---|---|---|---|
| 1 (textbook) | 1.95x | 50.59% ± 6.55 | 0.0045 |
| **4** | **1.41x** | **50.64% ± 6.77** | **0.0029** |
| 8 | 1.34x | 50.07% ± 6.62 | 0.74 |
| 16 | 1.30x | 49.82% ± 6.57 | 0.39 |

n=1000 each. The gain survives intact at 4 and is **gone** at 8 — not degraded, gone. So the
shipped default is `resample_every=4`: the full advantage at 1.41x instead of 1.95x, with 600
distinct worlds against the determinized search's 40.

That cliff is worth respecting rather than tuning around. Whatever ISMCTS is buying depends on
seeing many distinct worlds through one tree, and it stops buying it somewhere between 600 and
300 worlds — which is a fact about the mechanism, not about the constant.

---

## 5i. Best-play knowledge, put where it cannot do damage — and it still does nothing

§5g measured what happens when domain knowledge goes into the **value**: a fitted evaluator
whose largest weights were trump counts lost nine points a move, because bias does not average
out. The correct place for the same knowledge is the **selection rule** — a prior changes which
moves are *searched*, never what a position is *worth*, so the value estimate stays unbiased
and the heuristic decays as visits accumulate.

The heuristic is the one the sources describe: draw trumps in proportion to how many you hold,
cash the highest unplayed card of a suit, schmieren onto a trick your partner is taking (and
not with a trump), pay as little as possible into one an opponent is taking, and do not
over-trump. All of it computable without seeing another seat's cards.

| | share | n | p |
|---|---|---|---|
| expansion ordering only | 50.07% ± 6.35 | 1000 | 0.74 |
| PUCT c=0.5 | 49.96% ± 6.35 | 1000 | 0.86 |
| PUCT c=1.0 | 50.40% ± 6.34 | 1000 | 0.049 |
| PUCT c=2.0 | 50.25% ± 6.26 | 1000 | 0.20 |
| PUCT c=4.0 | **49.16%** ± 6.60 | 1000 | 5.3e-05 |
| *c=1.0, fresh seed* | 50.27% ± 6.22 | 1600 | 0.088 |
| *c=2.0, fresh seed* | 49.98% ± 6.51 | 1600 | 0.91 |

The c=1.0 hump was the best of five comparisons, which is where a p of 0.049 comes from about
a quarter of the time by luck alone. It did not reach significance on replication. Both runs
lean positive and pool to about +0.3, but the pooling is contaminated by having picked the
winner first, so it is reported as a null and shipped off. What a real effect looked like on
the same instrument, an hour earlier: ISMCTS at +1.15, p=1e-12, replicated three times.

**The informative row is c=4.0.** Losing at p=5e-05 proves the prior is not inert — it is
steering the search, and when given real weight it steers it *worse*. At 2,400 iterations the
search already knows this material better than a rule distilled from prose does.

Which is the ladder's oldest result restated. §1: **greedy scores the same as random**. A
hand-written rule about which card to play has been worth nothing in this game since the first
day of measurements, and it has now been demonstrated twice more — once in the value (§5g,
nine points) and once in the policy (here, nothing).

So the knowledge was not the problem and neither was the place it was put. Hand-written Jass
heuristics are simply weaker than the search they are advising. The version worth building is
a prior *learned from play* rather than written from prose — and unlike before, it now has a
measured slot to occupy, a baseline to beat, and a demonstration that the slot is wired
correctly.

---

## 5j. A prior learned from play — and why no prior can help here

§5i measured hand-written best-play knowledge in the selection rule at nothing, which left the
obvious excuse: the weights were guessed from prose. So the same slot was filled with weights
**fitted from 40,190 decisions of the search's own play** — distillation, expert iteration's
inner loop. Features of the (state, card) pair with one shared weight vector, because a first
attempt with per-card weight rows over one-hot features reached 1.2819 cross-entropy against
uniform's 1.2861: a linear model cannot represent "this seven is the best card left *because*
the six has gone", which is a product of two features.

The fitted policy is a good model of the search — **48.0% top-1 agreement against a 30.7%
baseline** — and it independently recovers the Swiss conventions nobody encoded into it:

| weight | | |
|---|---|---|
| `takes` | +0.631 | take the trick when you can |
| `over_partner` | **−0.575** | do not trump your own partner's trick |
| `lead_boss` | +0.414 | lead the best card left in a suit |
| `is_trump` | **−0.230** | a general reluctance to play trump — *"du trumpfst zu viel"* |
| `feed` | −0.220 | do not pay into a trick an opponent is taking |
| `lead_trump` | **+0.109** | and drawing trumps is *mild* |

That last row is a disagreement with every source consulted, which all make drawing trumps the
declarer's first job. The hand-written prior encoded it at `0.8 + 0.2 × trumps_held` — about
eight times what the search's own play supports — and that is very likely why §5i's version
actively **hurt** at high weight while this one does not.

| c | learned | hand-written (§5i) |
|---|---|---|
| 0.5 | 50.06% (p=0.76) | 49.96% (p=0.86) |
| 1.0 | 50.44% (p=0.021) | 50.40% (p=0.049) |
| 2.0 | 50.15% (p=0.43) | 50.25% (p=0.20) |
| 4.0 | 49.96% (p=0.83) | **49.16% (p=5e-05)** |

Learning bought **safety, not strength**: correctly calibrated weights do no damage when
trusted, mis-calibrated ones do.

### The control that closes it

Two priors disagreeing 8× on the largest convention both scored ~50.4% at c=1 and nothing
elsewhere. That is the signature of the *content* being irrelevant and the *form* doing the
work — PUCT replaces UCT's `√(ln A / n)` with `P(a)·√A/(1+n)`, a different exploration schedule
whatever `P` holds. All-zero weights softmax to exactly uniform, so the control was free:

| | share | n | p |
|---|---|---|---|
| uniform prior, c=1 | 50.09% ± 6.65 | 1600 | 0.60 |
| learned prior, c=1 | 50.23% ± 6.35 | 1600 | 0.14 |
| learned prior, c=1, fresh seed | 50.02% ± 6.27 | 1600 | 0.89 |

The learned prior did not replicate — 50.44, then 50.23, then 50.02 — the sixth borderline p in
this file to die on a second look. And the uniform control is null too, so it is not the
exploration shape either. **Hand-written prior, learned prior, and PUCT's form: all three
nothing.**

### Why, structurally

A prior exists to allocate attention when a search cannot try everything. Measured over 817
real decisions:

| | |
|---|---|
| average legal moves | **4.20** |
| iterations per move | 2,400 |
| visits per candidate | **~571** |

Every legal move is already examined about five hundred times. Chess has ~35 moves and Go
~250, which is where a prior earns its keep by pruning what the search will otherwise never
reach; Jass has four. **There is nothing to prune.** That one fact explains all three nulls,
and it predicts the same of any future prior, learned or not — including a neural one, which
would be a better model of the same thing nobody needs a model of.

It also says what a policy network *would* still be for: not guiding this search, but replacing
it, or guiding one run at a budget far below 2,400 where the moves are not all visited anyway.
Neither is the thing that was being proposed.

---

## 5k. What better beliefs are worth — the first direction with a large payoff

Strategy fusion turned out to be ~8% of the hidden-information cost (§5h), which left the
remaining ~8 points unexplained and **non-locality** as a hypothesis this file had carried all
day without evidence. Non-locality is a claim about the *belief distribution*: an opponent's
earlier plays were choices, so the deals surviving them are not uniformly likely among the
deals that merely survive the hard voids in `voids.py`.

So measure what the belief distribution is worth. With probability `p` the search imagines the
**true** deal instead of a sampled one, walking it from its own beliefs to perfect ones
(`arena/oracle.py`, which takes the true deal and therefore lives in `arena/` like
`cheating.py`). p=1 reproduces the cheating agent — 57.81% here against 58.39% there, which is
the sanity check.

| p | share | gain | vs linear | per 1% of oracle |
|---|---|---|---|---|
| 0.05 | 50.36% ± 6.45 | +0.36 | 0.39 | 0.072 |
| 0.10 | 51.34% ± 6.21 | +1.34 | 0.78 | **0.134** |
| 0.20 | 52.52% ± 6.50 | **+2.52** | 1.56 | 0.126 |
| 0.35 | 54.14% ± 6.39 | +4.14 | 2.73 | 0.118 |
| 0.50 | 55.24% ± 6.51 | +5.24 | 3.91 | 0.105 |
| 0.75 | 56.75% ± 6.75 | +6.75 | 5.86 | 0.090 |
| 1.00 | 57.81% ± 6.38 | +7.81 | — | 0.078 |

n=800 each. **The curve is concave**: a fifth of the information buys a third of the gap, and
the return per unit peaks around p=0.1–0.2 rather than at the top. Beliefs pay, and they pay
hardest at the margin — which is the opposite of what was expected when this was run.

### What it does and does not license

It measures the value of **injecting exact truth**, which is a much stronger intervention than
any inference can perform. A real inference nudges the distribution; the oracle inserts
certainty into a fraction of the worlds. So this is an upper bound on what better beliefs can
buy, not a forecast.

Read as a bar, it is a demanding one. Each 1% of oracle-equivalent belief accuracy is worth
roughly **0.07–0.13 points**, so beating ISMCTS's +1.15 needs inference worth about **10% of
an oracle**. The priors in §5e and §5j were worth a small fraction of one percent by this
scale, which is why they measured as nothing — and reconciles the two results rather than
setting them against each other.

It also corrects the overreach in §5e. That section's mechanism — a prior only flips decisions
the search rates within 0.008 of each other — is true of weak corrections and was stated as if
it were true of all belief work. It is not. Belief accuracy is the largest lever measured
anywhere in this file; what was missing from the priors was magnitude, not relevance.

**This does not isolate non-locality.** Nothing here separates "the sampling distribution is
wrong" from "not knowing is inherently costly", because even a perfect imperfect-information
player loses to a cheat. The honest statement is about belief accuracy in total.

---

## 5l. The exact belief information that was being thrown away

§5k found belief accuracy to be the largest lever measured anywhere in this file. The first
place to spend that finding is not inference — it is the information the table has already
been *shown*.

When the best Weis is declared its cards are turned face up to prove it. Everyone at the table
sees them. The search was dealing those cards to random seats in every imagined world.

| | |
|---|---|
| rounds where a Weis is shown | **66%** |
| cards pinned, at those decisions | 2.26 |
| **share of the unknown cards pinned** | **17.3%** |

That is proof of the strongest kind — not an inference about a holding, a sighting of it — so
it joins the void masks in `forbidden` rather than the soft priors that §5e and §5j measured at
nothing. `Observation.known_cards` carries `(seat, card)` for shown cards still unplayed; once
played they are public through `played` like anything else.

**Why this hid for so long.** `EVAL` switches Weis off, so every figure in this file before
this section was measured in a world where the information does not exist. The round-level
arena never runs Weis at all. It is invisible to the entire instrument and live in every real
game — which is why measuring it needs `HOUSE` and whole games (`arena/games.py`).

**Two things that are not here.** Stöck contributes nothing: it is announced only when the
*second* of King and Queen is played, by which point both are face up through the ordinary
channel. And the announced *values* from hands that never showed their cards — "I have 100",
unproven — remain unused. That is a real constraint (a seat calling 100 holds four of a kind
or a four-sequence) but it is not a per-card mask, so it needs machinery this does not have.
**§5m builds it** — and finds that the pins measured in this section were mostly being
discarded by a bug in `determinize`, so every figure below came through a lossy channel.

### What it was costing

| instrument | | share | n | p |
|---|---|---|---|---|
| whole games, target 1000 | | 51.38% ± 20.44 | 400 | 0.18 |
| whole games, target 2500 | | 51.25% ± 21.79 | 400 | 0.25 |
| **whole games, target 1000, fresh seed** | | **51.78% ± 23.16** | 1600 | **0.0021** |
| **rounds, HOUSE** | seed 91 | **50.57% ± 4.82** | 1500 | **4.8e-06** |
| | seed 8802 | **50.66% ± 5.08** | 1500 | **5.6e-07** |

**+0.62 ± 0.18 of a round's card points, and +1.78 ± 1.13 of games.** The two are consistent
rather than contradictory: a persistent per-round edge compounds over the ~10 rounds of a
1000-point game, so the game figure is the larger one and is also the one that answers the
question anybody cares about.

This is the second change in the file to make the bot measurably stronger, and it is worth
more than ISMCTS's +1.15. It came from using public information that was being thrown away,
not from a better algorithm.

It is also the one result today that survived, where six borderline p-values did not, and the
difference is in the order of operations: the mechanism was identified first (17.3% of the
unknown cards, in 66% of rounds), the direction was predicted before measuring, and four
independent arms agreed before the confirmation run. The failures all had the opposite shape —
a bump noticed inside a sweep, then defended.

### The instrument had to be built first

The first two rows are underpowered because game win rate carries a ~23% standard deviation
against the round metric's ~5%: roughly twenty times the samples for the same resolution. The
round-level arena could not measure this at all, because `play_round` drives a `RoundState`
directly and never scored Weis — so `EVAL` was the only setting it could run.

`arena/arena.py` now resolves Weis and Stöck for a round and passes the shown cards into the
observation. Every existing figure in this file came through that code path, so the change is
inert by proof rather than by inspection: with `weis_enabled` off, `resolve_weis` returns
zeros and `score(weis=(0,0), stoeck=(0,0))` is identical to `score()`, checked over 300 random
rounds and pinned as a test. A second test checks the dangerous direction — that a pinned card
is genuinely in the hand that showed it — because a wrong pin would have the search reasoning
about worlds that cannot exist, which is the failure `voids.py` exists to prevent.

One duplication comes with it: `resolve_weis` mirrors `Game._resolve_weis`'s automatic path,
so "who shows what" now has two implementations. The arena needs its own because it plays
rounds with injected hands, but it is a drift risk, and the fix is for the arena to route
rounds through `Game`.

---

## 5m. The calls, and a sampler bug that was throwing them away

§5l used the cards a Weis **shows** and left the values it **calls** on the table, with a
reason: "a seat calling 100 holds four of a kind or a four-sequence, but that is not a
per-card mask, so it needs machinery this does not have." This is that machinery, and
building it uncovered something larger than the feature.

### The mechanism, measured before anything was built

Weis is called in two stages. Everyone announces a value as their turn comes round in the
first trick; only the team holding the best one shows cards. The search was using stage two
and ignoring stage one entirely — including the silences, which are the bulk of it.

| | over 40,000 deals, HOUSE |
|---|---|
| a seat calls nothing | **72.3%** |
| calls 20 | 21.1% |
| calls 50 | 3.7% |
| calls 100 or more | 1.8% |
| positive calls per round still unshown after §5l | 0.40 |
| **imagined worlds that contradict what the table said** | **80.4%** |

That last row is the one that matters, and it is far larger than §5l's 17.3% of pinned
cards: four-fifths of the search's imagined worlds were deals the table had already ruled
out loud. The information is overwhelmingly in the **silence** — 2.9 of four seats say
nothing in an average round, and 69% of rounds have no unshown positive call at all.

A value names no card, so it cannot join `forbidden`. It is a predicate over whole hands and
is tested where whole hands are made: `rust/src/announce.rs` deals a world and checks it,
with a cheap exact gate (no run of three, no scoring four of a kind) for the 72% silent case
and `find_weis` only when that cannot decide. A call is a statement about the **nine cards
dealt**, so a mid-round world is put back together with `played_by` before being tested —
without that, every world from trick two onwards is rejected.

Rejection is capped at 16 draws and then the world is used anyway. §5e's arithmetic against
exact rejection sampling applies here too, and lands better: silence accepts at 0.72 a seat,
so a typical move redraws about five times, and the rare call that would cost thirty-six
redraws simply runs out the cap and leaves the search believing what it believed before.

### The bug this found, which was costing more than the feature is worth

Whole games crashed with `ValueError: no candidates` — the search returning **no move at
all**. A 200-game control with the new flag off did not crash and I read that as
exoneration; it was underpowered. At 800 games the control crashed too, so the bug predated
this work and had shipped.

`determinize` deals cards to seats in a random order. A card that only **one** seat may hold
was not placed first, so the pinned seat filled up with other cards and the pins were left
homeless: `pool` did not empty and the entire deal was discarded. A shown Weis pins three to
five such cards. At four pins nearly every draw failed, so a position could exhaust all 600
world draws and return nothing.

**This means §5l's pins were mostly being thrown away as failed determinizations from the day
they landed.** The fix is the standard one — assign every forced card first, to a fixpoint,
because placing one can fill a seat and force the next — and it is pinned by two tests, one
of them the real position from the crash. Both arms of every A/B benefit, so every figure
below was re-run on the corrected sampler and the earlier ones are discarded.

The fix also removed disagreement between seeds that had looked like noise: on the buggy
sampler the four seeds scattered at chi-squared 8.5 on 3 df, on the corrected one 1.9.

### What the calls are worth

Both arms have the §5l pins **on**, so this is what the unproven values add on top of the
proven cards.

| instrument | | share | deals | p |
|---|---|---|---|---|
| rounds, HOUSE | seed 91 | 50.31% ± 6.52 | 1500 | 0.063 |
| | seed 8802 | 50.32% ± 6.22 | 1500 | 0.049 |
| | seed 314 | 50.38% ± 6.37 | 1500 | 0.022 |
| | seed 2718 | 50.59% ± 6.31 | 1500 | 2.7e-04 |
| | **pooled** | **50.400% ± 0.082** | **6000** | **1.1e-06** |
| whole games, target 1000 | seed 5150 | 51.25% ± 22.34 | 800 | 0.11 |
| | seed 77000 | 51.47% ± 21.28 | 1600 | 0.0058 |
| | **pooled** | **51.40% ± 0.44** | **2400** | **0.0015** |
| **rounds, equal wall-clock** | | **50.11% ± 0.12** | 3000 | **0.34** |

For scale, the shown pins re-measured on the same corrected sampler and the same 40x60
budget are **50.405% ± 0.097** over 3,000 deals (p=3.1e-05) — so the called values are worth
about as much again as the cards that get turned face up. That figure is *not* comparable to
§5l's own 50.57/50.66: the budgets differ, as the per-deal standard deviations show, and no
claim is made here that the sampler fix made §5l larger or smaller.

### The equal-time column, and why it does not decide this one

`docs/value-net-plan.md` §Phase 4 says equal wall-clock is the gate that decides shipping. By
that gate this fails: the constraint costs **1.94x a move** (2.06 -> 3.99 ms), and handing the
baseline 4,600 iterations against 2,400 erases the gain.

It ships on anyway, and the reason is in this file's own numbers rather than an exception
made for it. A move costs 4 ms against the ~1 s the app allows a bot for pacing — 250x of
headroom. The search budget is fixed at 2,400 because §3 found it saturating there, so the
time the calls cost is time nothing else would have used. Equal wall-clock is the right gate
for a change that competes with search for a scarce budget; compute is not scarce here.

**One result that does not fit.** If the search truly saturates at 2,400, then 4,600
iterations should buy the baseline nothing and the equal-time column should read like the
equal-iteration one. Instead the baseline recovered about 0.29 of the 0.40. Either saturation
is softer than §3 says under HOUSE with Weis live, or the extra iterations are worth
something specifically when beliefs are wrong. It is recorded rather than explained.

### What is deliberately not here

The call is used as an exact value and nothing more. A seat calling 50 holds a four-card
sequence *somewhere*, and which suits remain possible given its voids is a further
constraint the sampler could use to place cards rather than only to reject worlds. That is
the difference between filtering worlds and generating them, and at 80.4% rejection it is
where the remaining cost is.

---

## 5n. The trump selector, priced by simulation — and a unit bug that nearly shipped

§2 measured the rule-based selector against *random* bidding and nothing else. Its weights were
written by hand and the baseline and shove threshold had never been tuned. `arena/contracts.py`
prices every call the way bridge and Skat engines do: hold forehand's hand, deal the other 27
cards at random, play all six contracts out with the card-play bot (ISMCTS, 2,400 iterations,
`read_bidding` off so that play does not depend on who declared), and record what each call
moved the game score by. 3,000 hands × 16 deals = 48,000 deals, 288,000 rounds.

### The unit bug, first

The first pass multiplied `RoundScore.total` by the contract multiplier — but `total` is
**already multiplied**. Every call was scored by the square of its multiplier. The fit that came
out of it played Undenufe 41% of the time, beat the shipped weights by 53.25% in a round match
scored the same wrong way, and chose Undenufe on six hearts headed by Puur, Nell, ace and king.
That last one is what gave it away: the simulated value of Hearts on that hand was 600, and the
most a ×2 contract can be worth is (157 + 100) × 2 = 514.

It also corrects a claim made while planning this: that a round match's share cannot see the
multiplier. It can. Shares are taken over multiplied totals, and the two halves of a double round
bid independently, so a bidding change is priced in game points by the ordinary instrument.

### What the corrected data says

| | value per round (game points) |
|---|---|
| random contract | −2.6 ± 0.7 |
| rule-based selector, shipped weights | 116.6 ± 1.5 |
| per-hand best call, cross-fitted | 132.3 ± 1.9 |
| best contract in hindsight (unattainable) | 240.1 ± 1.5 |

The selector leaves **15.7 ± 1.4** a round against the best call per hand — and that estimate
is conservative, because it chooses on 8 deals and scores on the other 8. The regret sits in the
×1 suits: calling Ecken or Schaufel costs 46–56 a round against the alternative, calling Herz or
Kreuz 12. Obenabe, Undenufe and the shove are, if anything, *under*-called.

### Fitting the weights

The selector is linear in its weights, so it can be evaluated on all 48,000 deals as one matrix
product and the weights searched directly (`arena/fit_trump.py`, a coordinate walk, fitted on half
the hands and scored on the other half). The shape of `trump_weights.json` does not change, so
the Rust twin picks it up through `include_str!`.

| | held-out, per round | calls played |
|---|---|---|
| shipped weights | 117.9 | Ecken 18%, Herz 24%, Schaufel 20%, Kreuz 25%, Obenabe 4%, Undenufe 9%; shove 27% |
| fitted weights | 152.7 (**+34.8 ± 1.8**) | Ecken 11%, Herz 14%, Schaufel 11%, Kreuz 14%, Obenabe 18%, Undenufe 33%; shove 51% |

It passes every judgement test in `tests/test_trump.py`, including the six-heart hand. Two weights
are ugly and harmless — the length bonus for eight and nine trumps (65, 56) only decides hands
that call trump anyway.

| instrument | fitted vs shipped | n | p |
|---|---|---|---|
| whole games, target 1000, card play at 2,400 | **58.31% ± 26.76** of games | 800 pairs | ~0 |
| rounds, HOUSE, card play at 38,400 | **51.73% ± 9.61** of game points | 2,000 deals | 9e-16 |

t ≈ 8.8 and 8.1. By a wide margin the largest gain in this file, from a component that had been measured
once, against random, and left alone.

What it does not settle is whether the Obenabe/Undenufe share is a fact about Schieber or about
how our bots defend a no-trump contract. Both teams in every figure here are the same bot, so a
weakness in no-trump defence would be invisible to all of them. Against humans that is the first
thing to check.

---

## 5o. A model of how a seat plays, and what it says about the hidden hands

§5k measured belief accuracy as the largest lever in the engine, and every correction tried was a
bounded per-suit tilt. The common practice in trick-taking engines is stronger: weight each
imagined deal by how likely the table's actual plays would have been *holding that deal*. That
needs a model of play conditioned on a seat's own hand.

`rust/src/playmodel.rs` is one: 36 features of the (seat's view, card) pair, a linear term plus a
32-unit ReLU layer, softmaxed over the legal cards. Trained on 161,850 decisions of the shipped
search playing itself at 38,400 iterations, validated on held-out rounds:

| | |
|---|---|
| validation cross-entropy | **0.885** (uniform 1.289) |
| top-1 agreement with the search | **61.4%** (§5j's linear model: 48.0%) |
| Rust vs numpy, largest probability difference | 5e-6 |

### What the beliefs are worth, before playing a match

Scoring a belief by the expected fraction of hidden cards it places in the right hand has an exact
correspondence with §5k: mixing a fraction `p` of true worlds into a sampler of accuracy `u` gives
`u + p(1 − u)`. So a weighted sampler of accuracy `a` is worth an oracle-equivalent
`p = (a − u)/(1 − u)` (`arena/belief_quality.py`). 1,500 decisions, pool 2,048:

| weight on plays α | weight on bid β | oracle-equivalent p, our bots | random card play | median ESS (bots) |
|---|---|---|---|---|
| 0.5 | 0.5 | 0.081 | — | 933 |
| 1.0 | 0 | 0.096 | 0.015 | 504 |
| 1.0 | 1.0 | **0.123** | 0.048 | 351 |
| 2.0 | 1.0 | 0.154 | — | 91 |

By §5k's curve p ≈ 0.12 is worth roughly +1.3–1.5 of a round's share — as much as ISMCTS — and it
climbs through the round, from 0.06 after six cards to 0.21 after twenty-six. Against a table that
plays at random the model is wrong about every play, and the weighting still never does worse than
uniform: the bid carries most of what is left.

### And in play

| | share | deals | p |
|---|---|---|---|
| α = 1, β = 1, pool 4,096, vs shipped — HOUSE, 153,600 iterations | **51.31% ± 5.91** | 1,000 | 2.4e-12 |
| *replication, fresh seed* | **51.32% ± 5.80** | 1,000 | 6.5e-13 |

**+1.31 of a round's share, twice** — the offline number predicted +1.3–1.5 before either match
was run, and it is the same size as ISMCTS. The two seeds agree to a hundredth of a point, which is
the opposite shape from the six borderline results this file has watched die on a second look.
**It ships on**: `belief_alpha = bid_alpha = 1` in `agent.py`, `BELIEFS` in `wasm_api.rs`.

Two limits read off the table. α = 2 buys accuracy by collapsing onto ~90 effective worlds, below
the few hundred §5h found the shared tree needs, so the shipped search uses α = 1 with a pool of
4,096. And our own bots are the easy case — the model was fitted to them. The number that matters
is against people.

---

## 5p. The play model inside the search, and the exploration constant

Both uses of the play model that §5o did not cover: moving the other three seats inside the tree
by the model — holding their own hand in the imagined world — instead of by UCT over statistics
pooled across worlds (`tree_policy`), and finishing each rollout by the model instead of at
random (`rollout_temperature`). Both measured at **equal iterations** against the shipped search,
because both are far dearer per iteration.

| change | iterations, both sides | share | deals | p | cost per move |
|---|---|---|---|---|---|
| `tree_policy` | 38,400 | **51.23% ± 6.08** | 1,000 | 1.4e-10 | ~11x |
| `rollout_temperature = 1` | 9,600 | **51.10% ± 6.80** | 1,000 | 3.3e-07 | ~40x |

Both are real at equal iterations. At ~11x and ~40x a move, what decides shipping is **equal time
at the shipped budget** — the same seconds, not the same iterations. §5h's lesson applies: ISMCTS
was +1.15 at equal iterations and +0.53 at equal time.

| change, at roughly the shipped search's time per move | iterations | vs shipped 153,600 | deals | p |
|---|---|---|---|---|
| `tree_policy` | 14,400 | 50.39% ± 6.65 | 1,000 | 0.066 |
| `rollout_temperature = 1` | 3,840 | 50.15% ± 7.22 | 1,000 | 0.52 |

Both sides with beliefs on (§5o). **Neither survives the price at 2,400-era budgets.** Policy
rollouts are a clean null: +1.10 at equal iterations, and the ~40x cost spends all of it. The tree
policy keeps a lean of +0.39 that does not reach significance.

### The tree policy at the shipped budget

Revisited once the owner settled the latency question (strength over speed, a few seconds a move
acceptable). Equal *iterations* at 153,600 on both sides — the A side costs ~11x the wall clock,
about 1.5–2 s a move natively:

| | share | deals | p |
|---|---|---|---|
| `tree_policy` at 153,600 vs shipped at 153,600 | 50.62% ± 6.16 | 1,000 | 1.4e-03 |
| *replication, fresh seed* | **51.10% ± 6.52** | 1,000 | 8.5e-08 |
| **pooled** | **50.86%, SE 0.14** | 2,000 | ~1e-09 |

**+0.86 of a round's share, replicated.** The effect shrinks with budget — +1.23 at 38,400, +0.86 at
153,600 — which is what a search that eventually works the same thing out for itself should do, and
it is still there at the budget that ships.

**What it fixes.** In the shared tree a node holds one set of statistics for every world, so the
other three seats' choices are pooled across worlds: they are effectively conditioned on the
searcher's *real* hand (it is the same in every world) and blind to their own. Moving them by the
play model, holding the hand that world deals them, is the first change to model the opponents as
seats with their own information rather than as statistics of ours.

**What it costs.** ~11x a move, about 1.5–2 s natively — inside the latency the owner allows, and
the reason the equal-time column is not the gate here. It **ships on** in `agent.py`, which covers
the server and the bot containers. The browser build leaves it off: at ~1.4x native it would be ~5 s
a move and nothing has measured it there.

Two things they say regardless. The pooled-statistics model of the other seats — conditioned on
the searcher's real hand, blind to their own — was costing something, as reading the code
suggested. And random rollouts were not the unbiased estimator they looked like in §5g: they are
unbiased for play at random, and a model of the table's play measures better.

### The exploration constant, finally asked

1.5 was inherited from the published voting search and never tuned for the shared tree (§5f). At
153,600 iterations against it:

| exploration | share | deals | p |
|---|---|---|---|
| 0.7 | 50.08% ± 5.48 | 1,000 | 0.66 |
| 1.0 | 50.05% ± 5.15 | 1,000 | 0.75 |
| 2.5 | 50.09% ± 5.20 | 1,000 | 0.59 |

Flat across 0.7–2.5, standard error ~0.17. **It stays at 1.5** — now for a measured reason.

---

## 5q. A belief network trained on the truth — worth a little, on top

§5o reads the table through a model of play. The other common practice is to learn beliefs
directly: every simulated round knows the true deal, so a network can be trained to say, for each
hidden card, which of the other three seats holds it (`rust/src/beliefnet.rs`). No cheating agent
is needed. Inputs are only what the deciding seat saw — who played what and how (led, followed,
discarded, ruffed), proven voids, shown Weis cards, the value each seat called, the bid — relative
to the observer; seats a card provably cannot be at are masked, not learned.

Trained on 210,000 decisions from 6,000 self-play rounds under HOUSE (`arena/belief_data.py`,
`arena/train_belief.py`), validated on held-out rounds:

| network | per-card accuracy | validation loss | note |
|---|---|---|---|
| uniform over allowed seats | 41.0% | — | |
| 128 → 64 | 45.5% | best at epoch 1, then rising | memorises: 6,000 rounds are 6,000 deals |
| **64 → 32** | **46.0%** | 0.938, still falling | |
| 32 → 16 | 45.2% | 0.943 | |

Scored in worlds on the same 1,500 decisions as §5o (`belief_quality.py --load-probes`), as
oracle-equivalent p:

| weighting of the pool | 128 → 64 | **64 → 32** | 32 → 16 | median ESS (64 → 32) |
|---|---|---|---|---|
| network alone | 0.042 | **0.055** | 0.042 | 858 |
| plays + bid (shipped) | 0.124 | 0.124 | 0.124 | 486 |
| plays + bid + network × 0.5 | 0.137 | **0.139** | 0.136 | 343 |
| plays + bid + network × 1 | 0.143 | 0.149 | 0.144 | 205 |

On its own the network reads far less than the play-model likelihood — a marginal over single cards
cannot carry "these two cards went together", which a replay of the round under a play model can.
On top of it, it adds **+0.015** at a weight that keeps ~340 effective worlds; by §5k's curve that is
roughly +0.15–0.2 of a round's share. Weight 1 buys a little more by dropping below the few hundred
worlds §5h needs.

The 64 → 32 network was still improving when training stopped, so it was limited by data rather
than by size. Tripled — 12,000 more rounds, 630,000 decisions in all — it improves, slowly:

| 64 → 32 network | 6,000 rounds | **18,000 rounds** |
|---|---|---|
| per-card accuracy (uniform 40.8%) | 46.0% | **46.8%** |
| network alone | 0.055 | **0.069** |
| plays + bid + network × 0.5 | 0.139 (ESS 343) | **0.143** (ESS 325) |
| plays + bid + network × 1 | 0.149 (ESS 205) | **0.155** (ESS 197) |

+0.031 on top of plays and bid at weight 1 — roughly +0.3–0.4 of a round's share by §5k — with the
pool at 2,048 here. The search draws 4,096, which roughly doubles the effective worlds and keeps
weight 1 above the few hundred §5h needs.

### In play

| | share | deals | p |
|---|---|---|---|
| plays + bid + network × 1, vs plays + bid — HOUSE, 153,600 iterations | 50.15% ± 5.65 | 2,000 | 0.24 |

**Null.** Standard error 0.126, so the 95% interval is −0.10 to +0.40: the offline prediction sits at
its upper edge, and anything that large would usually have shown. The mapping from oracle-equivalent
*p* to points that predicted §5o to a tenth of a point overstates this one — plausibly because a
network trained on marginals adds accuracy on cards the search's decisions do not turn on, where the
play likelihood sharpens exactly the cards a seat chose to play. Resolving an effect of +0.2 would
take ~6,000 deals; not worth it at this size. It stays behind `DmctsAgent.belief_gamma`, **off**, with
the trained weights in `krass_jass/data/belief_net.json` for native builds only.

---

## 5r. Round two: belief settings, a play model of today's bot, and trump re-priced

Three cheap follow-ups from the research pass, each checked offline before any match.

### Belief settings, swept on saved worlds

`rs_belief_loglik` re-scores the 1,500 saved decisions' worlds under any play-model temperature,
bid temperature and play model without replaying a round (`belief_quality.py --rescore`), so 270
settings took minutes. Oracle-equivalent *p* against median ESS on the 2,048-world pool:

| play T | bid T | α | β | *p* | ESS |
|---|---|---|---|---|---|
| 1.0 | 3.0 | 1.0 | 1.0 | 0.124 | 486 (shipped) |
| 1.0 | 1.0 | 1.0 | 1.0 | 0.134 | 418 |
| 1.0 | 1.0 | 1.5 | 2.0 | **0.158** | 207 |
| 0.75 | 1.0 | 1.5 | 2.0 | 0.166 | 139 |

A frontier, not a free lunch: play temperature and α are near-interchangeable (both scale the
same log-likelihood), sharper weighting buys accuracy with effective worlds, and a **sharper bid
model (T = 1 instead of 3) is better at every setting** — worth about +0.01 at equal ESS. ESS scales
roughly with pool size, so the candidate taken to play is α = 1.5, β = 2, bid T = 1 with a pool of
**8,192**: *p* 0.158, about as many effective worlds in the search as the shipped setting has.

### The play model, retrained on today's bot

§5o's model was fitted to the search *before* beliefs and the tuned trump weights. Re-recorded:
311,683 decisions from 12,000 rounds of today's bot (38,400 iterations, beliefs on, pool 2,048).

| model | validation loss (uniform 1.297) | top-1 |
|---|---|---|
| 32 hidden | 0.880 | 62.3% |
| **64 hidden** | **0.867** | **63.5%** |

Like for like on the same saved worlds (play T 1, bid T 3), the 64-hidden model reads the table
better than the shipped one at every setting:

| bid T | α | β | shipped model | 64 hidden |
|---|---|---|---|---|
| 3.0 | 1.25 | 2.0 | 0.144 (ESS 289) | **0.157** (253) |
| 3.0 | 1.5 | 2.0 | 0.152 (219) | **0.165** (182) |
| 1.0 | 1.5 | 2.0 | 0.158 (207) | **0.173** (169) |

+0.013 to +0.015 oracle-equivalent, at the queued match's settings included. The probes were recorded from our own bots with beliefs on, which is
also who this model was fitted to, so part of the gain is the model matching the table better — as
it would in play against the same bots.

### Trump, re-priced by a card player that reads the table

§5n's labels came from a card player at 2,400 iterations without beliefs. Re-priced with the play
likelihood on (bid likelihood off, so the shove is still priced exactly — forehand and partner are
one team, and the play model reads only the declaring *team*): 1,000 hands × 8 deals.

| value per round, game points | |
|---|---|
| tuned selector (today's weights) | 159.4 ± 3.3 |
| per-hand best call, cross-fitted on 4 deals | 140.7 ± 3.8 |
| refit from today's weights, held out | **+3.2 ± 1.6** |

A tenth of the first fit's +34.8, and within two standard errors of nothing. The no-trump shift
survives the stronger labeller — its per-hand best calls are Obenabe 13%, Undenufe 21%, shove 41% —
so it is not an artefact of a weak card player pricing the calls. **The selector's weights are
near what this feature set and this data can support; no refit, and role-specific features are not
justified by it.**

### In play

| | share | deals | p |
|---|---|---|---|
| α = 1.5, β = 2, bid T = 1, pool 8,192 vs shipped — HOUSE, 153,600 | 50.09% ± 5.20 | 2,000 | 0.43 |
| the 64-hidden play model vs the shipped one, those settings on both sides | 50.12% ± 5.08 | 2,000 | 0.30 |

**Both null.** Standard errors 0.116 and 0.114; the offline predictions (+0.3 to +0.45 and +0.15)
sit at the top edge of the intervals. Nothing from round two ships: not the settings, not the better
model of how the table plays, not a trump refit.

### The offline measure predicts the first step and not the next ones

Four data points now. The play-and-bid likelihood itself, worth +0.034 oracle-equivalent over
uniform sampling, measured **+1.31 twice** and the offline curve predicted it to a tenth of a point
(§5o). Since then: +0.031 from the belief network, **null** (§5q); +0.034 from sharper weights,
**null**; +0.015 from a play model retrained on today's bot — a straightforwardly better model of
the table, 63.5% top-1 against 61.4% — also **null**. The same size of offline gain, four times, and
only the first was worth anything in play.

What separates them is what the extra accuracy is *about*. The first step replaced uniform guessing
with reading the table at all, which moves the worlds the search is unsure about. Sharpening the
same signal, or adding per-card marginals on top, concentrates weight on worlds that are more
likely without being more decision-relevant — and pays for it in effective worlds. So
oracle-equivalent *p* stays a good screen for whether a signal exists at all, and is **not** a
predictor of points beyond that first step. A match still decides, and the offline number no longer
earns one on its own.

The practical reading: **the belief channel is saturated at the shipped setting.** Reading the table
was worth +1.3; reading it better, by three different routes, is worth nothing measurable. What is
left of the ~7-point gap to a cheating agent is not reachable by improving *which worlds are
imagined*.

---

## 5s. Distilling the search into a network: the flat head fails, and why

`docs/neural-plan.md` candidate A: train a network on the search's **visit distributions** and play
it with no search at all. Data: 311,756 decisions from 12,000 rounds of today's bot at 38,400
iterations. Inputs: the ~900 the belief encoder builds. Head: 256 → 256 → **36 independent logits**,
masked to the legal moves.

| | |
|---|---|
| validation cross-entropy (uniform 1.296) | **1.236**, best at epoch 3, rising after |
| top-1 agreement with the search | **51.0%** |

| the network, no search, vs | share | deals | p |
|---|---|---|---|
| random | 59.94% ± 9.79 | 1,000 | ~0 |
| greedy | 62.16% ± 8.87 | 1,000 | ~0 |
| **the shipped search (153,600)** | **42.42% ± 7.36** | 1,000 | ~0 |

It plays legally and beats the floor of the ladder, and it is **7.6 points worse than the search** —
against a gate of 1%. It also loses to the 36-feature linear play model on the same task (63.5%
top-1 versus 51.0%), which is the diagnosis: with 36 independent output logits the network has to
learn what each card means separately, while the small model scores a **(state, card) pair** with
shared weights, so "this is the highest card left" transfers across all 36. Parameter count is not
the problem; the shape of the output is.

### The conditioned head: better, still short, and now data-limited

Same data, same encoder; the state is embedded once and **each legal card scored from that embedding
plus its own 36 features** (`rs_play_features`), so what a card *is* transfers across all 36.

| head | validation cross-entropy | top-1 vs the search |
|---|---|---|
| flat, 36 logits | 1.236 | 51.0% |
| **conditioned** | **1.179** | **60.3%** |
| (for scale) the 36-feature linear play model | — | 63.5% |

+9 points of agreement from the output shape alone, and still short of the 70% gate. Validation
turns up after epoch 4 and training loss keeps falling: on 312k decisions this is now **limited by
data, not by shape** — the published Jass network that matched search strength trained on ~1.8M
human rounds, about a hundred times what is here, and a bigger network on this data would only
overfit sooner.

On the table, 1,000 deals each, no search at all:

| the network vs | flat head | **conditioned head** |
|---|---|---|
| random | 59.94% ± 9.79 | **65.48% ± 9.38** |
| greedy | 62.16% ± 8.87 | **67.66% ± 8.58** |
| the shipped search | 42.42% ± 7.36 (−7.6) | **45.97% ± 7.04 (−4.0)** |

Both gates are missed — the match gate was within 1% of the search — but the conditioned network is
a long way above greedy at **0.18 ms a move** against the search's ~2 s, which is what a difficulty
level is made of. Kept as that, not as a replacement.

**Candidate A stops at its own gate**, without the data to clear it. Recording a hundred times more
self-play is ~40 CPU-hours per 100k rounds at a budget worth distilling, which buys a *cheaper* bot,
not a stronger one. The strength question moves to candidate B — a value network inside a search
small enough for playout noise to still matter (`docs/neural-plan.md` §2B).
---

## 5t. A value network at the leaves — the kill criterion fires

Candidate B of `docs/neural-plan.md`, the last idea on this hardware that could add strength: a
network in place of the random playout, scoring a leaf (a perfect-information position inside an
imagined world) as the share of the *remaining* points the mover's team takes (`rust/src/valuenet.rs`,
295 inputs → 128 → 64 → 1). Unlike §5g it is trained on **what actually happened** — 432,000
positions from 12,000 rounds our own bot played to the end — not on the random playout's average.

### Offline: better than one playout, worse than four

RMSE against the real outcome, 4,000 held-out positions:

| estimator | RMSE |
|---|---|
| constant 0.5 | 0.346 |
| 1 random playout | 0.210 |
| **value network** | **0.188** |
| 4 random playouts | 0.159 |
| 16 | 0.143 |
| 64 | 0.139 |
| 256 | 0.137 |

The random playout is *not* unbiased for the real outcome — its error flattens at ~0.137 however many
are averaged, which is the distance between random play and ours — but that floor is far lower than
the network reaches. The network beats a single playout, which is what a leaf gets in the search, and
that cleared the gate the plan set. It does not beat the average the search builds from many.

### In play

| value network vs playouts | iterations, both sides | share | deals | p |
|---|---|---|---|---|
| small search | 2,400 | 49.85% ± 7.58 | 2,000 | 0.39 |
| shipped budget | 153,600 | 50.40% ± 6.96 | 1,000 | 0.068 |

The plan's kill criterion was the first row: **if a value head cannot beat playouts inside a small
search, the network-inside-the-search line is closed.** It cannot. The second row leans +0.40 without
reaching significance, and it is not free — at 153,600 iterations a move costs **2.64 s against
1.68 s**, 1.6× — so at equal time the lean shrinks further.

### What closes, and what it says

With §5s this finishes the network work that CPU-only hardware allows. A network that *replaces* the
search is 4 points weaker (§5s); one that *judges positions inside* it is worth nothing measurable at a
small budget and a costly lean at the large one. The two gains of this stretch both came from a small
model of **how the other seats play** — reading the table (§5o) and moving them inside the tree (§5p) —
not from a model of what a position is worth. The search already estimates that well; it did not know
how its opponents think.
## 5u. Swiss conventions, and what a predictable partner may cost

*2026-09-18/19.* The owner asked for a partner that plays like a person — aces, then kings, draw the
opponents' trumps — and for the researched Swiss conventions to be implemented (Swisslos Jass-Onkel,
jassverzeichnis.ch and others; `krass_jass/convention.py` lists them). They stay **outside** the
search's score: the search rates the moves, and a convention may only choose among moves it rated
(nearly) the same. The question is how wide "nearly" may be.

**Predictability** is measured offline on 3,892 real decisions from the shipped bot: in the decisions
where a convention names a card, how often the bot plays that card. The search's output does not depend
on the setting, so one run of saved decisions scores every setting at once.

| setting | plays the convention's card | overrides the search's first choice | search's own cost per override |
|---|---|---|---|
| search only | 58.9% | — | — |
| window: 5% of visits, 0.01 of score (previous default) | 65.9% | 10.0% | 0.10 |
| **price λ = 0.01** | **73.2%** | 19.9% | 0.35 |
| price λ = 0.02 | 79.7% | 26.5% | 0.73 |
| price λ = 0.03 | 84.7% | 30.3% | 1.06 |
| price λ = 0.05 | 91.1% | 34.9% | 1.62 |

A *price* λ is the window `(1.0, λ)`: no visit condition beyond a floor of 0.5% of the visits
(`MIN_VISIT_SHARE` — a barely explored move has no reliable score), and a convention card may be up to
λ of a round's share worse by the search's own estimate. The cost column is that estimate, in points of
a round's share; it is noisy, which is why the matches below decide.

**Strength**, each against the same bot with conventions off, shipped budget (153,600, tree policy),
1,000 double deals, seed 91:

| conventions | share | p |
|---|---|---|
| previous window (0.05, 0.01) | 50.15% ± 4.84 | 0.32 |
| **price λ = 0.01** | **50.03% ± 5.71** | **0.86** |
| price λ = 0.02 | 49.49% ± 6.74 | **0.018** |

λ = 0.02 costs half a point — measurably, on one run — and λ = 0.03 was stopped, since it overrides the
search more often at a higher price per override. **λ = 0.01 is free and ships** (`DmctsAgent.convention_slack
= (1.0, 0.01)`, `convention::DEFAULT_SLACK` in the browser build): the partner plays the card a Swiss
player expects in three convention decisions out of four, up from two out of three.

Not yet done: the bot *plays* the conventions but does not *read* them — the play model the beliefs and
the tree policy use was trained on play without them. Retraining it on self-play with conventions is
the next step.

## 5w. The play model, retrained on convention self-play — the first learned gain since §5p

*2026-09-19/20.* §5u shipped the Swiss conventions, and noted that the bot *played* them but could
not *read* them: the play model the beliefs (§5o) and the tree policy (§5p) see the table through
was fitted to self-play in which nobody played them. So the corpus was taken again with them on.

**Data.** 12,000 rounds of the shipped bot playing itself under `HOUSE` at 38,400 iterations, every
seat with conventions at the shipped price — 310,184 decisions (`arena/policy_data.py`), 3.5 h.
Trained exactly as the shipped model was, 32 hidden units, only the data different:

| | shipped model (§5.2) | retrained |
|---|---|---|
| validation cross-entropy | 0.885 | **0.837** (uniform 1.288) |
| top-1 agreement with the search | 61.4% | **65.2%** |

**In play**, against the bot with the shipped model, everything else equal, 1,000 double deals at
153,600 with the tree policy on:

| seed | share | p |
|---|---|---|
| 93 | 50.39% ± 5.43 | 0.024 |
| 94 | **50.50% ± 5.38** | **0.003** |

Replicated, so it ships. About +0.45 of a round's share — small beside §5o's +1.3, and the first
gain in this project that comes from a behaviour the owner chose rather than one the search found:
the model now expects a partner to cash aces before kings and to draw trumps, and reads them that
way inside the tree and in the belief weights. Offline model quality predicted the direction here,
which §5q–§5r warned it would not; one agreement is not a licence to trust it again.

---

## 5v. Sidi Barrani: the first screens

*2026-09-19.* The second game mode (`docs/rules-config.md`, `docs/sidi-plan.md`) measured the Schieber
way — every hand twice with the teams swapped on one seed, a paired test — in **points written a
hand** (cards plus the stake), `arena/sidi_ab.py`, 1,000 double hands at 38,400 iterations each. Both
arms bid with the same rule bidder.

| A vs B | points a hand | written share | p |
|---|---|---|---|
| reading the auction (`sidi_alpha` 1 vs 0) | **+32.02 ± 109.4** | 55.10% | ≈ 0 |
| playing for the bid vs for the cards (`sidi_objective`) | −5.14 ± 73.9 | 49.15% | 0.028 |
| doubling on an estimate vs a stopper count (`sidi_double_model`) | −0.18 ± 80.3 | 49.97% | 0.94 |
| knocking out of turn vs only on turn (`sidi_knock_anytime`) | **−7.61 ± 59.0** | 48.74% | 4.5e-05 |
| the same, but only with nothing left to bid (`sidi_knock_holds_bid`) | **−11.08 ± 67.1** | 48.14% | 1.8e-07 |

Knocking out of turn — a double the moment an opponent bids, which the rules allow and the player
may do — **loses**, and it is the clearest loss measured here. A double ends the auction, so a seat
that knocks early throws away its own contract and whatever its partner still had to say; asking
both opponents after every bid doubled about half of all hands against a third. It is off for the
bots (the player keeps the button, because the rule is the rule at a table). Restricting it to
seats with nothing left to bid did not rescue it — that lost 11.08, worse than the unrestricted
version — so the cost is not the forfeited contract alone: **these bots simply double too often**,
and every extra double doubles a stake their estimate is only roughly right about. What to try
next is the threshold (`sidi_double_below`, 0.35), not the timing.

Reading the auction is on, and is the largest effect in this document — against bidders who speak
the language literally, and with doubling blind to the auction in the B arm as well, so it bounds
what a human partner's bids are worth rather than measuring it. Playing for the bid is off: the
stake's cliff, scaled into the search's [0, 1] reward, starves it of the card-point signal it was
tuned on. The estimate-based double stays (the owner's design, null against the rule). Details and
a replication on a fresh seed, queued, in `docs/sidi-plan.md`.

---

## 6. Open

- **Nothing measured against a human.** Every figure is bots against bots, and two of the largest
  gains — the play-model beliefs and the trump weights — were fitted to those same bots.
- The tuned trump selector calls Obenabe or Undenufe about half the time. Whether that is a fact
  about Schieber or about how our bots defend no-trump contracts cannot be seen bot against bot.
- The belief network at weight 1 is in a match as this is written (§5q).
- The tree policy keeps a +0.39 lean at equal time (§5p); it is where a larger move budget would go
  first, and has not been measured at the full budget.
- The cheating-agent gap (§3f, 57.35%) predates the trump fit and the beliefs; re-take it.
