# RubenNunez/deep-jass — "agent_final": random rollouts without a deal

**Result: our bot takes 67.1% ± 12.3% of the points (n = 100 deals, p < 1e-15) — but 813 of its
~3,600 card plays (23%) crashed inside its own code and were played by our fallback.** Not a
faithful measurement of what its authors intended; it is what the repository does.

- Source: github.com/RubenNunez/deep-jass @ `0507e6c` (2021-12-15).
- Licence: **none**: all rights reserved. Run locally as an opponent only.
- Weights: `deep-jass-project/models/trained_trumper.joblib` (a scikit-learn MLP, pickled with
  1.0.1; loads in 1.2.2 with a version warning).

## What it plays (`agent_combined.AgentFinal`: card play of `AgentGen5`, trump of `AgentGen6`)

- **Card play:** 15 votes; each vote scores every legal card by one random rollout (depth <= 10)
  and votes for the best; the most-voted card is played. **The rollouts are not dealt a world:**
  `sync_state_obs` sets every other seat's hand to all zeros ("we can not know what the others
  have"), so as soon as a rollout reaches a seat with no cards, numpy raises
  (`'a' cannot be empty`) and the move fails. Our adapter logs that and plays our fallback card
  (the last of our legal cards in card order). See Numbers for how often.
- The two class-level `ProcessPoolExecutor`s break once forked (a `KeyError` in the pool's manager
  thread, then `BrokenProcessPool` on every move). The registry entry swaps them for
  `ThreadPoolExecutor`s before building the agent — the same code, GIL-bound.
- **Trump:** the MLP over hand + "player < 1" (their stand-in for forehand), top-2 of 7 classes;
  as forehand it avoids shoving; as rearhand it can return a shove, which is not allowed.
- Rules: jass-kit 2.0.5.

## How it was run

    # venv: $OPPONENTS_DIR/venvs/old (Python 3.11, numpy 1.23.5, scikit-learn 1.2.2, matplotlib)
    python -m arena.opponents.run --opponent rubennunez --deals 100 --seed 1 --workers 3

Our bot `build([], 153_600, EVAL)`, `EVAL` rules, double rounds, same seed both halves, paired
test. 21 minutes on 3 workers.

## Numbers

| | |
|---|---|
| our share | **67.14%** ± 12.28% (std), se 1.23% |
| deals | 100 |
| p | < 1e-15 |
| fallbacks (its own exceptions) | 813 of ~3,600 card plays, ~23% |
| illegal cards | 0 |
| mapping mismatches | 1 — the undertrump rules difference (see `sobrinth.md`) |

| | rounds | our share |
|---|---:|---:|
| we declare | 100 | 78.4% |
| they declare | 100 | 55.6% |

It never shoved (0 of 100) and called Obenabe/Undenufe in half its contracts (49 of 100).
