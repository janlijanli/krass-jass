"""Serve jass-mu-zero over the jass-kit player protocol — run this in the OPPONENT'S venv only.

This file imports jass-mu-zero (no licence: all rights reserved) and, through it, jass-kit-py
(GPL-3.0) and jass-kit-cpp. It is a launcher, not part of our dependency graph: nothing under
`krass_jass/` or the rest of `arena/` imports it, and our side (`arena/opponents/mu_zero.py`)
only talks to it over HTTP. It mirrors how the author's own `scripts/evaluate_agents.py` builds an
agent from an experiment directory, which their `host_agents` cannot do for a MuZero agent.

    /home/user/ext/mzvenv/bin/python arena/opponents/mu_zero_server.py \
        --checkout /home/user/ext/jass-mu-zero --run 1653237674 --port 9910

Defaults are the author's strongest evaluated configuration, "MCTS-100-S"
(`resources/evaluation/experiment-4/mcts-S.json`): 100 iterations, greedy (temperature 0.05,
no Dirichlet noise), terminal function on, on run 1653237674.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkout", type=Path, required=True)
    ap.add_argument("--run", default="1653237674")
    ap.add_argument("--port", type=int, default=9910)
    ap.add_argument("--iterations", type=int, default=100)
    ap.add_argument("--threads", type=int, default=1, help="TensorFlow intra-op threads")
    ap.add_argument("--policy", action="store_true", help="the raw policy network, no search")
    args = ap.parse_args()
    sys.path.insert(0, str(args.checkout))
    logging.basicConfig(level=logging.WARNING)

    import tensorflow as tf

    # The SavedModels were written on a GPU; on CPU, Grappler's remapper fuses BatchNorm+Tanh
    # into an op with no CPU kernel ("Fusion is not implemented: [FusedBatchNorm,Tanh]").
    tf.config.optimizer.set_experimental_options({"remapping": False})
    tf.config.threading.set_intra_op_parallelism_threads(args.threads)
    tf.config.threading.set_inter_op_parallelism_threads(1)

    from jass_mu_zero.agent.agent_from_cpp import AgentFromCpp
    from jass_mu_zero.environment.networking.worker_config import WorkerConfig
    from jass_mu_zero.environment.service.player_service_app import PlayerServiceApp
    from jass_mu_zero.factory import get_agent, get_features, get_network

    run = args.checkout / "resources" / "results" / args.run
    cfg = WorkerConfig()
    cfg.load_from_json(run / "worker_config.json")
    cfg.network.feature_extractor = get_features(cfg.network.feature_extractor)
    cfg.agent.__dict__.update(type="policy" if args.policy else "mu-zero-mcts",
                              iterations=args.iterations, terminal_func=True, player_func=True)
    network = get_network(cfg, str(run / "latest_network.pd"))
    agent = AgentFromCpp(agent=get_agent(cfg, network, greedy=True))
    app = PlayerServiceApp("jass_mu_zero")
    app.add_player("mu-zero", agent)
    # One search at a time per process; the client holds a lock per server as well.
    app.run(host="127.0.0.1", port=args.port, threaded=False)


if __name__ == "__main__":
    main()
