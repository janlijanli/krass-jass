# theoliver7/hslu-dl4g — DMCTS (C++ kernel) + DNN trump

**Status: triaged, not run.** The strongest-looking bot of DL4G group B, and the one to spend
time on next. Running new opponent code was refused by this session's permission classifier
after the first four opponents had been started, so it was not built here.

- Source: github.com/theoliver7/hslu-dl4g @ `0421b80` (2023-11-09).
- Licence: **none** (no licence file): all rights reserved. Run locally as an opponent only.
- Built on jass-kit 2.x (GPL-3.0) and on `jasscpp`, the Python binding of Thomas Koller's
  jass-kit-cpp (github.com/thomas-koller/jass-kit-cpp, public; not on PyPI).

## What it plays

- **Card play:** determinized MCTS. `DeterminizationCppMCTSAgent` deals `determinizations`
  consistent worlds (`HandSampler2`, which respects the number of cards each seat holds), runs a
  perfect-information UCT search in each with the C++ game simulator and random rollouts, and
  sums the root visit counts across worlds. Worlds are spread over `cpu_count() + 1` processes;
  each search runs for `cutoff_time` seconds (time-limited, not iteration-limited). Reward is the
  team's share of the round's points.
- Served configurations (`service/player_service.py`): `dmcts2` 100 worlds x 0.9 s, `dmcts3`
  200 x 0.4 s, `dmcts4` 300 x 0.2 s, `dmcts5` 400 x 0.1 s; the README cites a 30 s decision window.
  On 4 cores `dmcts2` is ~18 s a move.
- A pure-Python `DeterminizationMCTSAgent` (`dmcts0/1`, 100 worlds x 1 s) and an
  `InformationSetMCTSAgent` (1,000-4,000 iterations) are also served.
- **Trump:** a six-layer dense Keras network on hand + forehand flag (`notebooks/models/v1..v8`,
  SavedModel format, Keras 2 — present in the repo). `PUSH` is class 6; as rearhand it takes the
  third-ranked class, not the second (`np.argsort(...)[2]` on a 1-row max) — looks like a bug.
  Without the model it falls back to Graf's trump table, shoving at <= 68.
- Rules: jass-kit's Schieber (no multipliers in their scoring, no Weis).

## How to run it (not done here)

1. Build `jasscpp` from jass-kit-cpp with pybind11 into a Python 3.11 venv with
   `tensorflow-cpu==2.15` (Keras 2 loads the SavedModel), `numpy<2`, `jass-kit==2.0.5`.
2. `model_location` is hard-coded to `/home/localadmin/dl4g/notebooks/models/v7`: pass the
   checkout's own path through the agent expression.
3. Add to `arena/opponents/registry.py`, e.g.
   `agent="players.determinization_mcts_cpp_agent:DeterminizationCppMCTSAgent(determinizations=100, cutoff_time=0.9, model_location='notebooks/models/v7')"`.
4. It already uses every core per move, so run with `--workers 1`, or (fairer to its clock and
   much faster for us) convert the time limit to an iteration budget and say so.

Expected cost at `dmcts2` on 4 cores: ~36 of its moves a deal x 18 s, ~11 min a deal, ~18 h for
100 deals. `dmcts5` (400 x 0.1 s, ~8 s a move) is ~8 h.
