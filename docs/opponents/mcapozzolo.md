# Mcapozzolo/Jass-bot — "GruppeMarcoPatrik": flat UCB Monte Carlo, 200 iterations

**Result: our bot takes 62.9% ± 13.0% of the points (n = 100 deals, p < 1e-15).**

- Source: github.com/Mcapozzolo/Jass-bot @ `5d7480f` (2025-12-13).
- Licence: **none**: all rights reserved. Run locally as an opponent only.
- Weights: the trump model `Data/trump_model_sw.joblib` is **not in the repo**; the bot catches
  the load error and uses its heuristic trump instead, so this is the bot as anyone cloning it
  gets it, not quite the one its authors served.

## What it plays (`my_agentcomplex.MyAgentcomplex`, the one `start_service.py` serves)

- **Card play:** UCB1 over the root's legal cards only (no tree below), 200 iterations; each
  iteration deals a fresh uniform world (card counts respected, no void inference), plays the
  chosen card and a random rollout, and scores the point *difference*. c = 1.4 on a reward in
  -157..157, so after one visit per card it is greedy on the running mean. Most visits wins.
- **Trump:** Graf-style hand scores, best contract. Its shove test reads `obs.push_allowed`,
  which jass-kit's observation does not have, so it **never shoves** (0 of 100).
- Rules: jass-kit 2.0.5.

## How it was run

    # venv: $OPPONENTS_DIR/venvs/light (Python 3.12, jass-kit 2.0.5, scikit-learn, joblib)
    python -m arena.opponents.run --opponent mcapozzolo --deals 100 --seed 1 --workers 3

Our bot `build([], 153_600, EVAL)`, `EVAL` rules, double rounds, same seed both halves, paired
test. 22 minutes on 3 workers (0.9 s of its time per half-round).

## Numbers

| | |
|---|---|
| our share | **62.88%** ± 12.96% (std), se 1.30% |
| deals | 100 |
| p | < 1e-15 |
| illegal cards / fallbacks | 0 / 0 |
| mapping mismatches | 1 — the undertrump rules difference (see `sobrinth.md`) |

| | rounds | our share |
|---|---:|---:|
| we declare | 100 | 74.9% |
| they declare | 100 | 49.8% |
| they declare Obenabe | 18 | 56.5% |
| they declare Undenufe | 13 | 47.5% |

It holds its own contracts exactly level (49.8% to us), better than Rico's network does, but
loses ours 25:75.

Worst deal, the same one as against Rico: deal 58 (22.3%). Our forehand (seat 1: D10 D8, HA HJ,
SA SQ S10 S9 S8 — five spades without the Jack) shoves; the partner (DA DK DQ, H10 H9 H8, S7 S6,
C8), whose best contract scores below zero on our weights, has to choose and takes **Undenufe x4**,
which they then lose 152:476. The opponents, given the same forehand hand, played Spades and made
94 of 157. Across the four opponents our shoved contracts are weaker in proportion at every
multiplier, so this looks like one bad hand rather than a pattern; it is the deal to replay if
anyone looks at the forced-partner choice.
