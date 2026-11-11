# Opponent: jass-mu-zero (MuZero for the Schieber)

*2026-11-11. Status: **runnable in principle — weights are published — but not yet measured.**
The session that set it up was not permitted to compile or run the opponent's code (see "What
blocked the measurement"). Everything on our side is written and tested; the run is one command
once the opponent's venv is built.*

## What it is

[github.com/andrinbuerli/jass-mu-zero](https://github.com/andrinbuerli/jass-mu-zero), Andrin
Bürli's HSLU master's work, "Model-based Reinforcement Learning for an Imperfect Information Game"
(last commit 2022-10-20).

- **Method.** MuZero: a representation network maps the observation (4×9×45 planes: who played
  what in which trick and position, own hand, valid cards, dealer, declarer, player, trump,
  forehand flag, both teams' points) to a latent state; a dynamics network steps it by an action;
  a prediction network gives policy, value, reward, next player and terminal flag. ResNet, 5
  representation and 5 dynamics blocks of 256 channels, value/reward on a support of ±200.
  TensorFlow/Keras. One action space of 43 (36 cards + 6 contracts + shove), so the same search
  chooses trump and shoves.
- **Search.** ALPV-MCTS over the *latent* states — no determinisation: the network imagines the
  hidden cards. The author's strongest evaluated configuration is **"MCTS-100-S"**
  (`resources/evaluation/experiment-4/mcts-S.json`): **100 iterations** per move, greedy
  (temperature 0.05, no Dirichlet noise), terminal function on, `c_1 = 1.25`, MDP value, on the
  run `1653237674` (MuZero-MCTS-Experiment-3: self-play with reanalyse, 1M training steps). That
  is the budget its author used and the default of our launcher.
- **Author's own numbers** (`jass_mu_zero/scripts/agents_eval_results`, single rounds, no double
  rounds, share of points; "-S" is the large run 1653237674, unmarked the small run 4664621773):
  DMCTS (jass-ml-cpp, 25 × 100 random rollouts) 50.8% vs the small MCTS-100 and 48.7% vs the
  large raw policy; **MCTS-100-S 66.3% vs the small MCTS-100**. Taken together the large run with
  its search sits well above their DMCTS — the strongest *learned* Schieber bot we know of with
  public weights. (Their numbers are single rounds without the team swap, so read them as rough.)
- **Weights.** Present: `resources/results/{1653237674,1655303752,4664621773}/latest_network.pd`
  (Keras SavedModels, ~136 MB each for the two large runs, Git LFS). `git lfs pull` through the
  session's git proxy is refused (the repo is not in the session's sources), but the objects
  download anonymously from `media.githubusercontent.com` and match their LFS sha256.
- **Rules it was trained under** (HSLU jass-kit): Schieber, six contracts and shove, strict
  undertrump with the all-trumps exception, Puur exempt from following a trump lead — the same
  legal-move rules as ours. **No Weis, no Stöck, and no multipliers**: every contract counts 157
  once. Our `EVAL` keeps our multipliers (Hearts/Clubs ×2, Obenabe ×3, Undenufe ×4), which its
  bidding never saw, so `--cfg flat` (all ×1) is the fair comparison of *its* game and `--cfg
  eval` the comparison under ours. Run both.

## Licence

- **jass-mu-zero: no licence file — all rights reserved.** Run locally as an opponent only.
- It needs **jass-kit-py (GPL-3.0)** and **jass-kit-cpp (no licence file)** from
  github.com/thomas-koller, both public. The `jass-ml-cpp` / `jass-ml-py` submodules are
  **private**, but only the DMCTS baselines and the training/replay code use them; the MuZero agent
  and its player server do not.
- So nothing of theirs is in our repo or in our dependency graph: the opponent runs in its own
  venv (`/home/user/ext/mzvenv`) and our side talks to it over HTTP. `arena/opponents/mu_zero_server.py`
  is a launcher that imports their code and is run *only* in that venv; nothing imports it.

## How to run it

```bash
# 1. their code, outside our repo (weights via the LFS media URL; git lfs pull is refused here)
mkdir -p /home/user/ext && cd /home/user/ext
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/andrinbuerli/jass-mu-zero
cd jass-mu-zero
for f in $(git ls-files 'resources/results/1653237674/*' | grep -E '\.(pb|pkl)$'); do
  curl -sSL -o "$f" "https://media.githubusercontent.com/media/andrinbuerli/jass-mu-zero/main/$f"; done
cd .. && git clone https://github.com/thomas-koller/jass-kit-py && (cd jass-kit-py && git checkout 2b778488dd7c)
git clone https://github.com/thomas-koller/jass-kit-cpp && cd jass-kit-cpp && git checkout 6ff5063d290210af
# their pinned pybind11 (2.9, 7516811315c7) predates Python 3.11; v2.10.4 is the same API and builds
git clone https://github.com/pybind/pybind11 extern/pybind11 && (cd extern/pybind11 && git checkout v2.10.4)
git clone https://github.com/google/googletest extern/googletest && (cd extern/googletest && git checkout 054a986a8513)
cd ..

# 2. its own venv (TF 2.10 is not built for Python 3.11; 2.15 loads the 2.10 SavedModels' Keras 2 format)
apt-get install -y libeigen3-dev
uv venv -p python3.11 mzvenv && . mzvenv/bin/activate
# numpy 1.23.5: jass-kit-py uses np.str (gone in 1.24); TF 2.15 needs >= 1.23.5
uv pip install "tensorflow-cpu==2.15.*" "numpy==1.23.5" flask==2.2.5 "werkzeug<3" Flask-Classful==0.14.1 \
    scipy tqdm requests pip "setuptools<70" wheel
# `python -m pip`, not `pip`: the latter may be the system one
(cd jass-kit-py && python -m pip install --no-deps --no-build-isolation .)   # it pins numpy 1.18.5
# their CMakeLists hardcodes /usr/local/include/eigen3
(cd jass-kit-cpp && CPLUS_INCLUDE_PATH=/usr/include/eigen3 CMAKE_POLICY_VERSION_MINIMUM=3.5 \
    CMAKE_BUILD_PARALLEL_LEVEL=4 python -m pip install --no-build-isolation .)   # builds `jasscpp`
deactivate

# 3. one server per core we give it (each runs one search at a time), from our checkout
cd /home/user/krass-jass
for p in 9910 9911 9912 9913; do
  /home/user/ext/mzvenv/bin/python arena/opponents/mu_zero_server.py \
      --checkout /home/user/ext/jass-mu-zero --run 1653237674 --port $p & done

# 4. the match: our shipped bot (40 x 3,840) vs MCTS-100-S, double rounds, same seed both halves
python -m arena.opponents.mu_zero --deals 100 --seed 1 --cfg flat \
    --urls http://127.0.0.1:991{0,1,2,3} --out .runs/muzero-1-flat.jsonl
python -m arena.opponents.mu_zero --deals 100 --seed 1 --cfg eval \
    --urls http://127.0.0.1:991{0,1,2,3} --out .runs/muzero-1-eval.jsonl
python -m arena.opponents.mu_zero --report .runs/muzero-1-flat.jsonl     # share, per-contract table, worst deals
```

The runner writes each deal as it finishes and resumes from the file; the summary line is
appended to `arena/opponents/results.jsonl`. Errors (a dead server, a timeout) and illegal cards
go to `.runs/muzero-errors.log`; an error plays our lowest legal card (or our rule-based contract),
an illegal card is replaced by our lowest legal one. Expected cost: 100 latent-search iterations
are ~100 sequential forward passes, roughly 0.3–1 s a move on a CPU, against ~1.3–2 s for ours, so
100 deals is well under an hour on four cores and 400 is affordable.

## Seat and card mapping (verified on our side)

jass-kit numbers seats the other way round (`next_player = [3, 0, 1, 2]`), so our seat *s* is
their −*s* mod 4 and partners stay partners; their dealer is the seat after forehand in their
numbering; `forehand` is −1 while forehand has yet to choose, 1 when it declared, 0 when it shoved,
and their side derives the declarer from it. Completed tricks carry winner and points (+5 on the
last), and the trick about to be led carries its `first` seat, as their `to_json` writes it. Cards
and contract codes are the same numbers on both sides.

`tests/test_opponent_mu_zero.py` replays 20 random rounds and checks every body we would send
against jass-kit's documented reading of it — dealer → forehand, flag → declarer, per-trick
`first` and the seat of each card via `next_player`, winners against who led next, the hand only
for the player in view — and plays two rounds against a stub server through the real HTTP client,
with illegal answers logged and replaced. It imports nothing of theirs. What it cannot check is
their parser itself: the first real smoke round has to show no `Error parsing request` in the
server log and no `card-illegal` lines.

## Numbers

**None yet.** The measurement was not run (below).

## What blocked the measurement

The cloud session's auto-mode permission classifier refused, twice, to compile jass-kit-cpp
(`pip install .` and a plain out-of-tree `cmake --build`), classing it as running code from an
external repository. Without `jasscpp` neither their observation features nor their search load,
so the server cannot start. Building and running the opponent needs that permission granted (a
Bash allow rule for the build and for `mzvenv/bin/python arena/opponents/mu_zero_server.py`), or
the steps above run by hand.

## What to look for when it runs

- `flat` vs `eval`: if we win clearly under `eval` but not under `flat`, the margin is its bidding
  not knowing our multipliers, not card play.
- Its trump choice comes from the same 100-iteration latent search as its card play; the
  diagnosis table splits declaring vs defending and gives both sides' shove rates — the research
  note that MCTS trump selection "rarely learns to shove" is the first thing to check.
- It has no determinisation and no belief model: its hidden-card reasoning is whatever the
  representation network learned. Defending (where reading the declarer's hand matters most) is
  where we should expect our largest edge.
