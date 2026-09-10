# Measurements — M4

Measured 2026-09-10, M2 (8 cores), Python 3.12, Rust core. Weis/Stöck/match off (`EVAL`),
double rounds, paired t-test.

**These are hand-recorded and will go stale.** `docs/documentation-plan.md` §3 specifies the
CI-artifact pipeline that replaces this file. Until that exists, treat every number here as
dated rather than current.

**The load-bearing caveat, stated once and applying to everything below:** there is no trump
selection yet (M3 is owed), so the arena picks a contract at *random* per deal. Real play
chooses trump, which makes hands far more playable and gives skill more room to express
itself. Random contracts plausibly compress every difference reported here. Nothing on this
page should be treated as settled until the sweep is repeated with a real trump selector.

---

## 1. Baseline ladder

n=60 double rounds.

| Matchup | Share | p |
|---|---|---|
| greedy vs random | 48.88% ± 9.27 | 0.35 — **not significant** |
| dmcts(small) vs random | 66.35% ± 8.85 | ≈0 |
| dmcts(small) vs greedy | 67.51% ± 8.70 | ≈0 |
| cheating vs dmcts(large) | 57.54% ± 7.81 | 7e-14 |

**Greedy is indistinguishable from random.** Not a bug: "play your highest-value legal card"
dumps aces into tricks it was never going to win. Keep it as a floor, never cite it as a
meaningful rung.

---

## 2. Search budget saturates, and early

Each budget played against a fixed reference of 40×60 = 2,400 iterations, endgame solver
off, n=400.

| Budget (dets × iters) | Share vs ref | p |
|---|---|---|
| 6 × 10 = 60 | 43.06% ± 8.71 | ≈0 |
| 12 × 20 = 240 | 47.42% ± 7.49 | 5e-12 |
| 20 × 40 = 800 | 49.47% ± 7.28 | 0.14 — not significant |
| 40 × 60 = 2,400 *(the reference itself)* | **50.00% ± 0.00** | 1.00 |
| 80 × 100 = 8,000 | 50.33% ± 7.60 | 0.39 — not significant |
| 200 × 200 = 40,000 | 50.24% ± 7.66 | 0.53 — not significant |

The reference row is a harness check, not a result: an agent playing itself under a double
round must score exactly half with zero variance, and it does.

**The knee is around 800 iterations.** By 800 the agent is within half a point of the 2,400
reference; past 2,400 the curve is flat. Separately measured at higher budgets:

| Matchup | Share | n | p |
|---|---|---|---|
| dmcts(large 40k) vs dmcts(small 2.4k) | 50.30% ± 7.31 | 1000 | 0.20 |
| dmcts(tuned 800k) vs dmcts(large 40k) | 49.60% ± 6.27 | 300 | 0.27 |

At n=1000 the standard error is 0.23%, so the 16× comparison resolves effects above roughly
0.5%. This is a well-powered null, not a failure to measure.

**333× compute from 2,400 to 800,000 iterations buys nothing measurable.**

### This contradicts the plan

`PLAN.md` §3.1 and `CLAUDE.md` both record "~1000 determinizations × 800 iterations" as the
settled sweet spot, under a heading saying not to rediscover it. That figure does not
reproduce here. Possible reasons, in order of how much they worry me:

1. **No trump selection** (see the caveat above). The most likely explanation and the
   cheapest to eliminate.
2. Their setup had no exact endgame solver, so late-round accuracy had to come from search.
3. The published figure may be *budget allocation* guidance — how to split a fixed 800k
   rollout budget between determinizations and iterations — rather than a claim that 800k
   is needed at all. Re-read the thesis before concluding anything.

Do not update the plan's guidance yet. Do not delete it either.

---

## 3. The gap to perfect information does not close with search

| Matchup | Share | n | p |
|---|---|---|---|
| cheating vs dmcts(40×60) | 56.75% ± 8.07 | 250 | ≈0 |
| cheating vs dmcts(200×200) | 56.23% ± 7.05 | 250 | ≈0 |

A 16× search increase moves the gap by 0.5%, which is about one standard error — nothing.

**~6.5% of points is the price of playing with hidden information, and search does not pay
it down.** This is the most important number the project has produced so far, and it is the
target for anything that comes after M4.

Two things it is not:

- It is not a hard bound. The cheating agent is itself DMCTS with one determinization, not
  an optimal perfect-information player, so the true cost of hidden information is *at
  least* this.
- It is not evidence about human play. Nothing here has been measured against a human.

### Why this is the expected shape

Determinized search has a known ceiling — strategy fusion. Each determinization is solved as
if the hidden cards were known, so the search never values an action for what it *reveals*
or *conceals*; averaging over more determinizations converges faster to the same fixed,
suboptimal policy. The measured signature is exactly that: steep gains to ~800 iterations,
then a plateau no amount of compute moves.

**Consequence:** the remaining gap is not a search problem, and the earlier conclusion holds
for a second, now-measured reason — getting past DMCTS needs learning, not compute.

---

## 4. What this changes

**Serve budget is a solved problem.** ~2,400 iterations is indistinguishable from 800,000,
and costs single-digit milliseconds in the Rust core. The latency budget question left open
since M0 is effectively answered: it does not bind.

**The Rust port's stated justification was partly wrong.** `docs/plan-review.md` §1 argued
M5 needs a teacher ~100× the student's search. On this evidence a 100× teacher is not
stronger, so distilling one buys nothing over distilling a cheap one. The port still earns
its keep — reinforcement learning needs *millions of games*, and 2,400 iterations × 36 moves
× millions is still far beyond Python — but the reason is throughput of *games*, not depth
of *search*. Recorded here rather than quietly amended there.

**M3 moved up.** Trump selection is now both the largest known gain still available (~16
points of win rate, `PLAN.md` §3.1) and the largest confound in every number above. It
should be the next thing built.
