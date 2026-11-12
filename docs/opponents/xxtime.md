# xXTime-OnXx/dl4g-jass-bot — heuristics, then flat Monte Carlo for 9.5 s

**Status: set up, not run.** The adapter entry is in `arena/opponents/registry.py` (`xxtime`, the
`tf` venv), but running new opponent code was refused by this session's permission classifier.

- Source: github.com/xXTime-OnXx/dl4g-jass-bot @ `3a73859` (2025-01-05).
- Licence: **none**: all rights reserved. Run locally as an opponent only.

## What it plays (`mcts_ucb_dltrump.AgentDLTrumpUCBMCTSSchieber`, the served `rule` player)

- **Card play, in order:** (1) if the trick holds >= 15 "points" (Graf trump-table scores, not
  card points) and a trump card would take the lead, play it; (2) otherwise, if *any* legal card
  would take the lead, play the first such card; (3) only if neither fires, flat Monte Carlo for
  **9.5 s**: deal a uniformly random world (card counts respected, no void inference), score each
  legal card by UCB1 (c = 2 on raw points) over random rollouts, play the best mean. The inner
  UCB loop itself runs until the 9.5 s are up, so the outer loop over worlds runs once: **one
  world per move**, i.e. a perfect-information guess. Despite the file name there is no tree.
  Its "can I win the trick" helper compares raw card indices for non-trump suits and ignores
  Obenabe/Undenufe ordering.
- **Trump:** `trump_model_592.h5`, a Keras network over hand + forehand flag. Shoves (returning
  6, `PUSH_ALT`, also as rearhand, where our adapter logs it and falls back) when P(shove) > 0.8;
  otherwise the best of the four suits — it **never chooses Obenabe or Undenufe**.
- Rules: jass-kit Schieber.

## How to run it

`tf` venv (Python 3.11, tensorflow-cpu 2.15 / Keras 2, numpy 1.26, jass-kit 2.0.5).

    python -m arena.opponents.run --opponent xxtime --deals 100 --seed 1 --workers 4

At 9.5 s on the moves where its heuristics do not fire, budget ~3-4 min of its time a deal per
worker: ~1.5 h for 100 deals on 4 workers.
