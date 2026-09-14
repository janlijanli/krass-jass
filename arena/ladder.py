#!/usr/bin/env python3
"""Run the baseline ladder.

`PLAN.md` §4: keep the whole ladder alive forever. The bottom rungs are not there to be
impressive, they are there so that when a change makes the top rung worse you find out.

    python arena/ladder.py --deals 100
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.arena import match  # noqa: E402
from arena.cheating import CheatingAgent  # noqa: E402
from krass_jass.agent import DmctsAgent, GreedyAgent, RandomAgent  # noqa: E402
from krass_jass.rules import EVAL  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deals", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument(
        "--workers", type=int, default=0, help="processes across deals; 0 = all cores"
    )
    args = ap.parse_args()

    workers = args.workers or (os.cpu_count() or 1)

    # The ladder's whole claim is that its rungs compare *card play*. RandomAgent's own
    # default is to bid at random, which makes every rung above it a measurement of bidding
    # as well — and the recorded figures in docs/measurements.json describe the opposite
    # ("rule-based trump selection for all agents"). Code and artifact disagreed; the code
    # now does what the artifact says.
    floor = RandomAgent()
    floor.trump_policy = "rules"

    small = DmctsAgent(determinizations=40, iterations=60, cfg=EVAL, label="dmcts(small)")
    large = DmctsAgent(determinizations=200, iterations=200, cfg=EVAL, label="dmcts(large)")

    cheat = CheatingAgent(iterations=4000, cfg=EVAL)

    pairs = [
        (GreedyAgent(), floor),
        (small, floor),
        (small, GreedyAgent()),
        (large, small),
        # The gap here is the cost of hidden information — the part search cannot fix.
        (cheat, large),
    ]

    print(
        f"{args.deals} double rounds each, {workers} workers, "
        f"Weis/Stöck/match off, paired t-test\n"
    )
    for a, b in pairs:
        t0 = time.perf_counter()
        result = match(a, b, deals=args.deals, seed=args.seed, workers=workers)
        print(f"{result}   [{time.perf_counter() - t0:.1f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
