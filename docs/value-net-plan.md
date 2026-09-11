# Plan: a learned value at the leaves

> **Superseded by its own Phase 0.** The probe ran and lost nine points at every split
> (`docs/measurements.md` §5g). The reason is architectural, not a detail of the fit: the
> playout's error is zero-mean and the search averages it over 2,400 samples down to ~0.019,
> while any static evaluator's error is bias and survives the averaging untouched. A drop-in
> replacement would need RMSE below ~0.02 on a quantity whose standard deviation is ~0.3.
>
> The plan below is kept because the constraint analysis in it is still correct and still
> useful — a network is affordable at play time, and the cost is training throughput. What is
> wrong is the *shape*: a value network cannot be swapped into a voting search. It belongs
> with a policy prior and an aggregation that is not a vote over perfect-information worlds,
> which means it comes after ISMCTS, not before it.

## Why this one

Today's measurements closed every cheaper door. The search is not compute-bound (saturates at
2,400 iterations, 333× more buys nothing — §3), not sampling-bound (five priors, and §5e says
why none of that family can work), and not allocation-bound (§3a: flat across an 8× range of
splits). The gap to perfect information is ~6 points and search does not pay it.

§5e also says where points *are*: to gain you must change decisions the search currently rates
far apart, and a prior cannot, because it never changes what a world is *worth*. The leaf
evaluator does nothing else. And ours is **a single random playout** — the crudest component
in the engine, deciding the value of every world.

## The constraint, measured first

| | |
|---|---|
| one random playout | **0.40 µs** |
| one move at 2,400 iterations | **1.68 ms** |
| what the app actually allows per move | ~1 s (bots are paced for realism) |
| therefore affordable per leaf evaluation | **~417 µs** |

| network | pessimistic (4 GFLOP/s) | with SIMD (15 GFLOP/s) |
|---|---|---|
| 336-64-1 | 10.8 µs | 2.9 µs |
| 336-128-128-1 | 29.8 µs | 7.9 µs |
| 336-256-256-1 | 75.9 µs | 20.2 µs |

**At play time this is not a latency problem.** Even a 256×256 net at the pessimistic figure
is 76 µs against a 417 µs ceiling — five times the headroom. The naive worry (a net is 190×
a playout, so it cannot replace one) is answered by the fact that we spend 1.68 ms of a
1,000 ms allowance.

The cost lands somewhere else: **training-throughput**. Self-play for data needs millions of
rounds, and there the 190× is real. So the design keeps random playouts for bulk data
generation and uses the network only for play.

## Phase 0 — the probe, before any of it (≈1 day)

Do not build a network to find out whether a better evaluator helps. Fit a **linear model on
hand-written features** (trump length per seat, tops held, tricks taken, points banked, cards
remaining), plug it in where the playout goes, and measure.

It has a sharp prediction attached. §3a found the search collapses below ~30 iterations per
world — 240×10 scored 47.56%, 600×4 scored 41.41%. If that floor exists because the tree needs
many rollouts merely to average out *rollout noise*, then a low-variance evaluator should move
the floor down, and 240×10 should stop being bad. That is a falsifiable claim about the
mechanism, testable in one sweep, and it tells us whether the premise of this whole plan is
right.

**Kill criterion.** If a linear evaluator does not beat random playouts by >1% at equal
iterations over n=1000, the premise is wrong and the plan stops here. A network would be
fitting a better function to a problem that is not function-limited.

## Phase 1 — data

Positions from self-play with the current bot, labelled with the realised outcome from that
position. Perfect-information state, because that is what a node inside a determinization
*is*: four hands, current trick, leader, contract, points so far.

- ~5M positions to start; the engine makes rounds at tens of thousands per second.
- Sample one position per trick to limit within-round correlation, then shuffle.
- Label = the team's final round points from that position, on the same [0, 1] scale the
  search already uses (`objective::reward` with `target: 0`).
- Hold out by *round*, never by position — plays from one round are correlated, and the thesis
  we cite was careful about exactly this.

## Phase 2 — train

MLP, 336 inputs → two hidden layers → one output. Start at 128×128; the table above says even
256×256 fits the budget, so capacity is not the binding constraint and the right size is
whatever validates best.

Encoding: card ownership as 36×5 (four hands plus played), current trick, contract one-hot,
seat to play, points so far. ~336 floats.

## Phase 3 — integrate

Inference in Rust, no Python in the hot loop. Weights exported as a flat `f32` blob, loaded at
start. Replaces `play_out` at the leaf; keep both behind a flag so the A/B is a flag flip, as
with `signal_reading` and `adversarial`.

**The wasm build is a real constraint, not an afterthought.** A 256×256 net is ~151k
parameters — 600 KB as `f32` against a current payload of 190 KB. Either quantise to int8
(~150 KB) or ship a smaller net to the browser. Decide before training, because it changes
what size is worth training.

## Phase 4 — evaluate

Both instruments, because they answer different questions:

- **equal iterations** — is the value actually better?
- **equal wall-clock** — is it worth what it costs?

A net can win the first and lose the second; only the second decides whether it ships.
Round-level `arena.py` under EVAL for card play, and `arena/games.py` for whole games, because
a round metric scores position-for-points trades backwards (§5d).

## Phase 5 — expert iteration, only if 0–4 worked

Regenerate self-play with the network in the loop, retrain, repeat. This is where a policy
prior for PUCT joins. Not before: each round of it costs days and is worth nothing until the
value is known to help.

## What this does and does not fix

It attacks **evaluation**. It does not fix **strategy fusion** — inside a determinization the
search still knows all four hands, and a perfect-information value estimator is still a
perfect-information estimator. That is deliberate: fusion is the aggregation problem, ISMCTS
is the candidate for it, and mixing the two changes would leave neither measurable.

One variant worth its own experiment later: train the value on the *information set* (the
observation) rather than the perfect-information state. Its estimate would then be an average
over consistent worlds by construction, which partially de-fuses the evaluation from inside.
It also muddles the semantics of a determinized node, so it is a separate question with a
separate measurement — not a free upgrade.
