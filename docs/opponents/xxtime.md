# xXTime-OnXx/dl4g-jass-bot — heuristics, then flat Monte Carlo for 9.5 s

**Result: our bot takes 65.7% ± 11.6% of the points (n = 100 deals, p < 1e-15).** No illegal
cards, no fallbacks; one mapping mismatch, the undertrump rules difference.

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

## How it was run

    # venv: $OPPONENTS_DIR/venvs/tf (Python 3.11, tensorflow-cpu 2.15 / Keras 2, numpy 1.26, jass-kit 2.0.5)
    python -m arena.opponents.run --opponent xxtime --deals 100 --seed 1 --workers 3

Our bot `build([], 153_600, EVAL)`, `EVAL` rules, double rounds, same seed both halves, paired
test. 105 minutes on 3 workers; it spends 75 s a half (its heuristics skip the search on some
moves), ours 18.6 s.

## Numbers

| | |
|---|---|
| our share | **65.65%** ± 11.61% (std), se 1.16% |
| deals | 100 |
| p | < 1e-15 |
| fallbacks / illegal cards | 0 / 0 |
| mapping mismatches | 1 — jass-kit allows an undertrump our strict rule forbids |

| | rounds | our share |
|---|---:|---:|
| we declare | 100 | 74.0% |
| they declare | 100 | 53.4% |

It **never shoved** (0 of 100 forehand hands: P(shove) never passed 0.8) and, as the source says,
never called Obenabe or Undenufe: 31 Clubs, 33 Hearts, 19 Diamonds, 17 Spades. Its own contracts
come out near level (46-57% for us per suit); it is strongest in its Spades.

Worst deal (9, 32.9%): our shoved partner calls Obenabe and loses it 78:393 (x3). Deals 58 and 28
are shoved Undenufe calls that lost against other opponents too (`rico.md`, `tedmanners.md`).
