# Measurements — M3 / M4

Measured 2026-09-10 on an M2 (8 cores), Python 3.12, Rust search core. `EVAL` rules
(Weis/Stöck/match off), double rounds, paired t-test, agents bidding for trump.

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

That predicts all five nulls at once, and it predicts the sixth. The obvious next idea is
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

## 6. Open

- Nothing measured against a human.
- Weis and Stöck are off in every number here; they are on for human play.
- The saturation result should be re-checked once a learned component exists, since a network
  prior changes what the search is converging to.
