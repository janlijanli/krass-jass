# The other RL / supervised opponents: triage (2026-11-11)

Only `luegl/JassAI` ships both code and trained weights (`luegl.md`). The rest, checked at their
default branches (shallow clones under `/home/user/ext`, outside the repo):

| Repo | Licence | Code | Trained weights | Runnable as a bot? |
|---|---|---|---|---|
| **luegl/JassAI** (2026) | none (all rights reserved) | PPO, PyTorch | **yes**, `checkpoints/*.pt` | **yes**: see `luegl.md` |
| AlessioVerardo/jass-reinforcement-learning (2026) | MIT (`pyproject.toml`; no LICENSE file) | DQN+PER, Rainbow, PPO (CTDE), AlphaZero-PIMC, **PIMC**, rule-based | **no**: no checkpoints in the repo | The learned agents: **no**. Their **PIMC** (K=20 worlds × 50 UCB1 sims, `c=1.41`) needs no weights and is runnable; their README puts PPO ≈ PIMC. A second candidate, not yet adapted. |
| gregunz/JassAI | MIT | DQN (linear), greedy, random; README says WIP | **no** | No. Untrained DQN; greedy/random are below our floor. |
| andieder/pyschieberSLJassBot (HSR thesis, Kistler/Eder) | MIT | Keras SL/RL players on pyschieber | **no**: `*.h5` paths in `train.py` (`trumpf_network_model_final__2018-06-18_112248.h5`, ...) are not in the repo | No. Weights missing; training data (human games) not shipped. |
| pajai/JassBot-Reinforcement-Learning (2016) | none | Q-learning MLP (Keras 1.0.4), own toy engine | yes: `data/2016-06-29-231553-{model,weights}.json` (weights are HDF5 despite the name) | Technically, with Keras 1 rebuilt by hand. Its engine draws **trump at random** (no bid, no Obenabe/Undenufe), and its own note says "about 55% score against the random bot". Not worth a seat. |
| FR8803/JassOpenAIGym (2021) | none | TF-Agents DQN (180 inputs, 9 outputs = hand slot) on its own gym, trained on Colab TPU | yes, but in **Git LFS** (`Data_BA/{Game,Round,Trick,Hybrid,Hybrid random}/rl_jass/saved_model.pb`, 81 KB). The LFS fetch was refused because the repo is not attached to this session. | Possibly: needs the LFS objects (attach the repo for read) plus TensorFlow + tf-agents, and its gym for the observation encoding. Trained against random partners and opponents. |
| JoelNiklaus/gym-jass | MIT | gym environment over pyschieber | no agent | No (an environment). |
| Murthy10/pyschieber | MIT | engine + simple players | no learned agent | Not an opponent; only the shared base of andieder/gym-jass. |

None of the runnable candidates sits on pyschieber, so no pyschieber translation was needed. The
shared bridge (`arena/opponents/bridge.py`) is format-neutral: each opponent's server script does
its own translation.

Next candidates, in order of value: AlessioVerardo's PIMC (a real search bot, MIT, no weights
needed), then FR8803 if its LFS weights can be fetched.
