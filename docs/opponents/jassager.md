# jassager (d-sbrgr): "Ja$$ager"

- **Source:** github.com/d-sbrgr/jassager @ c35e9cd (2024-12-25).
- **Licence:** **none**: all rights reserved. It runs locally as an opponent only.
- **Runnable:** yes. The code and weights are in the repository and not behind LFS:
  `models/parameters/jass_cnn_{1,2}.pth` (5.6 MB each), `models/trump_predictor.pth`, and
  `models/rl_models/*.pth`. Venv: `venvs/jassager`, Python 3.12, jass-kit 2.0.5 from PyPI,
  torch 2.5.1, pandas, scikit-learn, as its `requirements.txt` pins. The CPU-only torch index was
  blocked by the proxy, so the PyPI (CUDA) wheel is installed. It runs on CPU.
- **Status: not measured.** The session's permission classifier refused to execute the opponent
  code (see `README.md`).

## What it plays

`flask_app.py` serves `jassager` = **FullMCTS** as its main player, plus `jassager_cnn_{01,10,13}` =
MCTSCNNRollout with c = 0.1, 1.0 and 1.3:

- **FullMCTS** (`bots/mcts_bots/full_mcts.py`): ISMCTS with UCB1 (c = 1.3) and random rollouts.
  The reward is the team's points / 157. It plays for points, as we do. Determinization
  (`random_determinization.py`) **is void-aware**: it removes a suit from a seat that did not
  follow it. It **chooses trump by the same ISMCTS** (actions include push). The budget is a
  wall-clock `MAX_SEARCH_DURATION = 9.5` s for every decision. `np.random.seed(1)` is set per search.
- **MCTSCNNRollout**: the same tree, with a CNN (`jass_cnn_1.pth`) for the leaf value in place of
  the rollout. Trump is chosen as in FullMCTS.
- **Rules:** jass-kit's `RuleSchieber`, raw points, no Weis.

Our CLAUDE.md records that "MCTS-based trump selection underperforms because it rarely learns to
shove". This bot is a live test of that. Its search also reads `obs.trick_points`, which the runner
fills from our engine.

## Running it

The budget is scaled to this machine: **2 s a move**. At 9.5 s a move, 100 deals would take ~10
hours of opponent time. It is single-threaded, so run 2 servers and 2 deals at a time on 4 cores:

```sh
python -m arena.opponents.jasskit --bot jassager --deals 100 --seed 1 --start 2 --workers 2
python -m arena.opponents.jasskit --bot jassager-cnn --deals 100 --seed 1 --start 2 --workers 2
python -m arena.opponents.jasskit --report .runs/opp-jassager-1-shipped.jsonl
```

Which of the two is stronger is not documented; measure both and treat the better one as the
result.

## Numbers

None yet.
