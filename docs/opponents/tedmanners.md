# TedMANNERs/dl4g-jass-bot — "migrosoft": ISMCTS with rule-based rollouts, 5 s

**Result: our bot takes 70.1% ± 11.6% of the points (n = 100 deals, p < 1e-15).** No illegal
cards, no fallbacks, no mapping mismatches in ~3,600 of its moves.

- Source: github.com/TedMANNERs/dl4g-jass-bot @ `53111a2` (2020-12-15).
- Licence: **GPL-3.0** (the repository is a fork of jass-kit-py). Run in its own venv through the
  bridge; nothing of it is imported by our code.

## What it plays (`AgentMonteCarlo(5.0)`, served as `migrosoft_ismcts`)

- **Card play:** single-observer ISMCTS, one tree over the information set, a fresh uniformly
  dealt world per iteration (`mcts/sampler.py`, card counts respected, no void inference), UCB1
  with c = 1, **rule-based rollouts** (`HeuristicTurnAction`), for 5 s a move. The move returned
  is the root child with the largest *accumulated payoff*, not the most visits. Each selection
  step `print`s, which costs iterations.
- Variants in the repo: `AgentDeepTrumpMonteCarlo` (the same search with a Keras trump network,
  `models/trump0631`, SavedModel, present) and `AgentDeepMonteCarlo` (network rollouts). The
  served one uses the rule-based trump: card-point sum per contract, shove under 55.
- Rules: jass-kit Schieber.

## How it was run

    # venv: $OPPONENTS_DIR/venvs/old (Python 3.11, numpy 1.23.5: its vendored jass-kit uses np.str)
    python -m arena.opponents.run --opponent tedmanners --deals 100 --seed 1 --workers 3

Our bot `build([], 153_600, EVAL)`, `EVAL` rules, double rounds, same seed both halves, paired
test. 122 minutes on 3 workers; it spends 90 s a half (5 s x 18 moves), ours 17.5 s.

## Numbers

| | |
|---|---|
| our share | **70.13%** ± 11.55% (std), se 1.16% |
| deals | 100 |
| p | < 1e-15 |
| fallbacks / illegal cards / mapping mismatches | 0 / 0 / 0 |

| | rounds | our share |
|---|---:|---:|
| we declare | 100 | 81.2% |
| they declare | 100 | 57.0% |
| they declare, shoved | 61 | 58.9% |
| they declare, own choice | 39 | 53.3% |

It shoves in 61% of forehand hands (its "shove under 55 card points" rule), the same rate as ours
by coincidence: the two agree on the shove in 64 of 100 deals. Its own contracts come out near
level (49-56% for us in each colour); its Undenufe is where it loses most (66% for us).

Worst deal (28, 38.6%): we call Undenufe after a shove and lose it 280:348, and its shoved
Diamonds holds 134:23. No pattern across the worst five.
