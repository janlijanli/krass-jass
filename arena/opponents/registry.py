"""The external opponents we can seat, and how each one is started.

Every entry is a checkout under `$OPPONENTS_DIR` (default `/home/user/ext`), cloned with
`GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1`, and a venv under `$OPPONENTS_DIR/venvs`. None of
their code is in this repository; see `docs/opponents/<name>.md` for each one's setup.

`--set key=value` on the runner overrides a field, e.g. `--set agent='mod:Agent(budget=2)'`.
"""

from __future__ import annotations

import os

from arena.opponents.jasskit import JassKitBot

EXT = os.environ.get("OPPONENTS_DIR", "/home/user/ext")
LIGHT = f"{EXT}/venvs/light/bin/python"  # 3.12: numpy, jass-kit 2.0.5, scikit-learn, onnxruntime
TF = f"{EXT}/venvs/tf/bin/python"        # 3.11: the same plus tensorflow-cpu 2.15 (Keras 2)
OLD = f"{EXT}/venvs/old/bin/python"      # 3.11: numpy 1.23 (np.str), sklearn 1.2, tensorflow-cpu 2.12

OPPONENTS: dict[str, dict] = {
    # Greedy: plays the highest-valued legal card; trump by card points, shoves under 55.
    "sobrinth": dict(python=OLD, repo=f"{EXT}/sobrinth-dl4g-bot",
                     agent="dominik.jass4fun_agent:Jass4FunAgent()"),
    # A policy network (ONNX, 120 inputs -> 36), argmax over legal cards; Graf trump table.
    "rico": dict(python=LIGHT, repo=f"{EXT}/Rico-Uttinger-DL4G",
                 agent="maxOnnxNeuronAgent2:MaxOnnxNeuronAgent2()"),
    # Flat UCB over the root's cards, one determinization + random rollout per iteration, 200 it.
    "mcapozzolo": dict(python=LIGHT, repo=f"{EXT}/Mcapozzolo-Jass-bot",
                       agent="my_agentcomplex:MyAgentcomplex()"),
    # 15 random rollouts per card, majority vote; sklearn trump classifier.
    "rubennunez": dict(python=OLD, repo=f"{EXT}/RubenNunez-deep-jass", cwd="deep-jass-project",
                       # Their class-level ProcessPoolExecutors break once forked (KeyError in the
                       # pool's manager thread); thread pools run the same code, GIL-bound.
                       agent="agent_combined:[setattr(AgentGen5, k, __import__('concurrent.futures').futures"
                             ".ThreadPoolExecutor(5)) for k in ('executor', 'card_values_executor')] and None"
                             " or AgentFinal()"),
    # specialT: a dense play network (Keras h5) + logistic-regression trump.
    "nolonar-specialT": dict(python=TF, repo=f"{EXT}/Nolonar-HSLU_JassBot", path=("CasualTea",),
                             agent="main:Jass(trump_strategy.LogisticRegression, play_strategy.DeepNeuralNetwork)"),
    # casualT, their default: flat UCB Monte Carlo for 9 s a move + logistic-regression trump.
    "nolonar-casualT": dict(python=TF, repo=f"{EXT}/Nolonar-HSLU_JassBot", path=("CasualTea",),
                            agent="main:Jass(trump_strategy.LogisticRegression, play_strategy.Monte_Carlo_Tree_Search)"),
    # Heuristic overrides, then flat Monte Carlo for 9.5 s a move; Keras trump network.
    "xxtime": dict(python=TF, repo=f"{EXT}/xXTime-OnXx-dl4g-jass-bot",
                   agent="mcts_ucb_dltrump:AgentDLTrumpUCBMCTSSchieber()"),
    # ISMCTS with heuristic rollouts, 5 s a move ("migrosoft_ismcts"); rule-based trump.
    "tedmanners": dict(python=OLD, repo=f"{EXT}/TedMANNERs-dl4g-jass-bot",
                       agent="jass.agents.agent_monte_carlo:AgentMonteCarlo(5.0)"),
    # DMCTS with jass-kit-cpp's simulator (jasscpp, built with CMake from
    # github.com/thomas-koller/jass-kit-cpp into $OPPONENTS_DIR/jass-kit-cpp/build/source), worlds
    # spread over cpu_count()+1 processes, each searched for cutoff_time s; Keras trump network v7.
    # Served as dmcts5 = 400 worlds x 0.1 s (dmcts2 = 100 x 0.9 s).
    "theoliver7": dict(python=OLD, repo=f"{EXT}/theoliver7-hslu-dl4g",
                       path=(f"{EXT}/jass-kit-cpp/build/source",),
                       agent="players.determinization_mcts_cpp_agent:DeterminizationCppMCTSAgent("
                             f"determinizations=400, cutoff_time=0.1, model_location='{EXT}/theoliver7-models/v7')"),
    # "DeAentlibuecher": 10 threads, each UCT on one dealt world for 9 s (Cython build of
    # mcts_cythonized.pyx), visits summed; rule-based trump. The 2018 jass-kit 1.0 API.
    "faikue": dict(python=OLD, repo=f"{EXT}/FAIKUE-DL4G/source", api="v1",
                   agent="jass.player.mcts.mcts_player:MCTSPlayer()"),
}


def make(name: str, cfg, overrides: list[str] = ()) -> JassKitBot:
    spec = dict(OPPONENTS[name])
    for kv in overrides:
        k, _, v = kv.partition("=")
        spec[k] = v
    return JassKitBot(name=spec.pop("name", name), cfg=cfg, **spec)
