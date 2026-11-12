# The other RL / supervised opponents: triage (2026-11-11)

Only `luegl/JassAI` ships both code and trained weights (`luegl.md`). The rest, checked at their
default branches (shallow clones under `/home/user/ext`, outside the repo):

| Repo | Licence | Code | Trained weights | Runnable as a bot? |
|---|---|---|---|---|
| **luegl/JassAI** (2026) | none (all rights reserved) | PPO, PyTorch | **yes**, `checkpoints/*.pt` | **yes**: see `luegl.md` |
| AlessioVerardo/jass-reinforcement-learning (2026) | MIT (`pyproject.toml`; no LICENSE file) | DQN+PER, Rainbow, PPO (CTDE), AlphaZero-PIMC, **PIMC**, rule-based | **no**: no checkpoints in the repo | The learned agents: **no**. Their **PIMC** (K=20 worlds × 50 UCB1 sims, `c=1.41`) needs no weights: **adapted**, see `verardo-pimc.md`. Suit trumps only. |
| gregunz/JassAI | MIT | DQN (linear), greedy, random; README says WIP | **no**: none anywhere in its history | No. Untrained DQN; greedy/random are below our floor. |
| andieder/pyschieberSLJassBot (HSR thesis, Kistler/Eder) | MIT | Keras SL/RL players on pyschieber | **no**: `*.h5` paths in `train.py` (`trumpf_network_model_final__2018-06-18_112248.h5`, ...) were never committed (checked over the whole history), and the repo has no releases | No. Weights missing; training data (human games) not shipped. |
| pajai/JassBot-Reinforcement-Learning (2016) | none | Q-learning MLP (Keras 1.0.4), own toy engine | yes: `data/2016-06-29-231553-{model,weights}.json` (weights are HDF5 despite the name) | **Not run.** The code is Python 2 (`sorted(cmp=...)`) on Keras 1.0.4 + pandas + IPython, so it would need a Python 2.7 / Keras 1 / Theano stack. The other route, porting its feature code into our repo, is ruled out because it has no licence. Its engine draws **trump at random** (no bid, no Obenabe/Undenufe), and its own note says "about 55% score against the random bot". |
| FR8803/JassOpenAIGym (2021) | none | TF-Agents DQN (180 inputs, 9 outputs = hand slot) on its own gym, trained on Colab TPU | yes, but in **Git LFS** (`Data_BA/{Game,Round,Trick,Hybrid,Hybrid random}/rl_jass/saved_model.pb`, 81 KB). The LFS fetch was refused because the repo is not attached to this session. | **Runnable, measured**: see `fr8803.md`. The LFS files come over HTTPS from `media.githubusercontent.com`. Its 8-output net can only ever name ♦A…♦7; everything else, trump included, is random. |
| JoelNiklaus/gym-jass | MIT | gym environment over pyschieber | no agent | No (an environment). |
| Murthy10/pyschieber | MIT | engine + simple players | no learned agent | Not an opponent; only the shared base of andieder/gym-jass. |

None of the runnable candidates sits on pyschieber, so no pyschieber translation was needed. The
shared bridge (`arena/opponents/bridge.py`) is format-neutral: each opponent's server script does
its own translation.

Every repo with both code and weights has now been seated, except pajai (see its row).
