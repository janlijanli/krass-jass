# TedMANNERs/dl4g-jass-bot — "migrosoft": ISMCTS with rule-based rollouts, 5 s

**Status: set up, not run.** The adapter entry is in `arena/opponents/registry.py`
(`tedmanners`, the `tf` venv), but running new opponent code was refused by this session's
permission classifier.

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

## How to run it

    python -m arena.opponents.run --opponent tedmanners --deals 100 --seed 1 --workers 4

~36 of its moves a deal x 5 s: ~3 min of its time a deal per worker, ~1.3 h for 100 deals.
