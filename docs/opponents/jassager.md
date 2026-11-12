# jassager (d-sbrgr): "Ja$$ager"

- **Source:** github.com/d-sbrgr/jassager @ c35e9cd (2024-12-25).
- **Licence:** **none**: all rights reserved. It runs locally as an opponent only.
- **Runnable:** yes. The code and weights are in the repository and not behind LFS:
  `models/parameters/jass_cnn_{1,2}.pth` (5.6 MB each), `models/trump_predictor.pth`, and
  `models/rl_models/*.pth`. Venv: `venvs/jassager`, Python 3.12, jass-kit 2.0.5 from PyPI,
  torch 2.5.1, pandas, scikit-learn, as its `requirements.txt` pins. The CPU-only torch index was
  blocked by the proxy, so the PyPI (CUDA) wheel is installed. It runs on CPU.
- **Status: measured, 2026-11-12.** Our bot wins clearly against both: **59.7% ± 11.0%** against
  FullMCTS and **67.5% ± 12.2%** against the CNN variant, n = 100 each, p < 1e-15, at 2 s a move.

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

`--start 3 --workers 3` (three single-threaded servers, three deals at a time), 2 s a move, our shipped
bot (40 x 3,840), `EVAL` rules, double rounds on the same seed:

| | FullMCTS (`jassager`) | MCTSCNNRollout, c = 1.3 (`jassager-cnn`) |
|---|---|---|
| our share of points (multiplied) | **59.73% ± 10.98%**, n = 100, p < 1e-15 | **67.53% ± 12.16%**, n = 100, p < 1e-15 |
| our share of raw card points | 58.56% | 66.36% |
| our share when we declare / they declare | 70.8% / 45.5% | 78.7% / 54.3% |
| their declarations under 79 raw | 45 of 100 | 65 of 100 |
| their shoves from forehand | 1 of 100 | 1 of 100 (ours: 61 of 100) |
| opponent errors / fallbacks | 0 | 0 |
| illegal cards | 0 | 1, the jass-kit undertrump bug |
| time | ~50 min | ~52 min |

FullMCTS is the stronger of the two, so it is the result: **59.7%**. The CNN leaf value makes its
card play clearly worse (it keeps 70 raw points on its own contracts against FullMCTS's 82, and lets
us take 120 on ours against 108).

**Diagnosis: it never shoves.** Trump is chosen by the same ISMCTS as the cards, with push as one
more action. It pushed once in 100 forehand rounds; we push in 61. So it declares every weak hand
itself, and **45% of its contracts fall short of half the points** (65% for the CNN variant): Obenabe
5 of 8, Diamonds 10 of 21, Hearts 14 of 30. That is our CLAUDE.md's "MCTS-based trump selection
underperforms because it rarely learns to shove", reproduced on someone else's bot. A likely reason, not
checked in its code: in a determinized tree, a push is valued by the partner's best contract on each
imagined deal, which a random rollout plays badly.

**Its card play is decent.** It is the only one of these bots with void-aware determinization and a
points reward, the same objective as ours. Defending our contracts it concedes 70.8% (dl4g concedes
72.6%). Its worst-deal wins against us are on its own good hands (deal 89: its Hearts makes 264 of
314 multiplied points). In our five worst deals, our contract made under half three times (deals 42,
14, 36; two of those were shoved to us). That is no pattern worth chasing on its own.

**The illegal card** is the jass-kit undertrump bug again (`dl4g_hslu.md`): Spades trump, the trick
H8 S10 SA, and the CNN variant under-trumped the ace with SQ while holding Hearts. The kit measured
SQ against S10, the lower of the two trumps in the trick, not against SA.

Not run: the documented 9.5 s a move (~4 h for 100 deals here, 3 at a time). A 5x budget would sharpen
its card play, but not its trump choice, which is where it loses.
