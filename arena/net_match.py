"""Put the policy network on the table: the ladder rungs and the gate that decides candidate A.

`arena/ab.py` builds `DmctsAgent`s, which is every experiment so far. This one plays the
search-free network (`arena/net_agent.py`) against the ladder and against the search itself, which
is the match gate in `docs/neural-plan.md` §2A:

- beat `random` and `greedy` by the margins the ladder shows for a real player;
- come within **1% of the shipped search's points** while costing ~1 ms a move (the M5 criterion in
  `CLAUDE.md`) — a network that is 3 points worse is not a difficulty level, it is a bug.

Same protocol as everything else: double rounds, common random numbers, paired t-test, HOUSE.

Usage::

    python -m arena.net_match policy_net.npz --deals 1000 --opponents random greedy search
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.arena import match  # noqa: E402
from arena.net_agent import NetAgent  # noqa: E402
from krass_jass.agent import DmctsAgent, GreedyAgent, RandomAgent  # noqa: E402
from krass_jass.rules import HOUSE  # noqa: E402


def opponent(kind: str, iterations: int, cfg):
    if kind == "random":
        a = RandomAgent()
        # The ladder compares card play, so the bidding is held constant — see arena/ladder.py.
        a.trump_policy = "rules"
        return a
    if kind == "greedy":
        return GreedyAgent()
    if kind == "search":
        return DmctsAgent(determinizations=40, iterations=max(1, iterations // 40), cfg=cfg,
                          label=f"search({iterations})")
    raise SystemExit(f"unknown opponent {kind!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model", type=Path)
    ap.add_argument("--deals", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=91)
    ap.add_argument("--iterations", type=int, default=153600, help="the search opponent's budget")
    ap.add_argument("--opponents", nargs="+", default=["random", "greedy", "search"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = ap.parse_args()

    cfg = HOUSE.variant(target_score=None)
    net = NetAgent(model=str(args.model), label=f"net({args.model.stem})")
    for kind in args.opponents:
        t = time.time()
        result = match(net, opponent(kind, args.iterations, cfg), deals=args.deals, seed=args.seed,
                       cfg=cfg, workers=args.workers)
        print(result, f"({(time.time() - t) / 60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
