#!/usr/bin/env python3
"""Throughput harness — the number this whole project is gated on.

`docs/plan-review.md` §1 shows that M5 needs a teacher roughly 100x the serve budget, and
whether that is reachable is a throughput question, not an architecture question. So this
runs in CI from M1 onward and its output is meant to be tracked over time.

    python bench/benchmark.py            # human-readable
    python bench/benchmark.py --json     # for CI to record

Reports:
  rounds_per_second    full random rounds played out from the deal
  rollouts_per_second  playouts from a mid-round position, which is what DMCTS actually
                       does and is therefore the number that matters for search budget
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from krass_jass.rollout import make_kernel, play_out  # noqa: E402
from krass_jass.rules import EVAL, Contract  # noqa: E402
from krass_jass.state import RoundState  # noqa: E402

#: DMCTS tuning from the literature (PLAN.md §3.1): 1000 determinizations x 800 iterations.
TUNED_BUDGET = 800_000


def deal(rng: random.Random) -> list[int]:
    deck = list(range(36))
    rng.shuffle(deck)
    return [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]


def bench_rounds(n: int, seed: int = 1) -> float:
    rng = random.Random(seed)
    kernel = make_kernel(Contract.HEARTS, EVAL)
    hands = [deal(rng) for _ in range(n)]
    t = time.perf_counter()
    for h in hands:
        play_out(h, 0, kernel, rng)
    return n / (time.perf_counter() - t)


def bench_rollouts(n: int, tricks_played: int = 4, seed: int = 2) -> float:
    """Playouts from a position `tricks_played` tricks in — the DMCTS case."""
    rng = random.Random(seed)
    kernel = make_kernel(Contract.HEARTS, EVAL)
    positions = []
    for _ in range(64):
        state = RoundState(contract=Contract.HEARTS, hands=deal(rng), cfg=EVAL)
        while len(state.tricks_played) < tricks_played:
            legal = state.legal_moves()
            cards = [c for c in range(36) if legal & (1 << c)]
            state.play(cards[rng.randrange(len(cards))])
        positions.append((list(state.hands), state.leader))

    t = time.perf_counter()
    for i in range(n):
        hands, leader = positions[i & 63]
        play_out(list(hands), leader, kernel, rng)
    return n / (time.perf_counter() - t)


def bench_rust(seed: int = 3) -> dict | None:
    """The Rust core, if it is built. Same workload, so the numbers are comparable."""
    try:
        import krass_jass_core as core
    except ImportError:
        return None

    rng = random.Random(seed)
    hands = deal(rng)

    n = 2_000_000
    t = time.perf_counter()
    core.play_out_many(hands, 0, int(Contract.HEARTS), 1, n)
    rollouts = n / (time.perf_counter() - t)

    def dmcts_rate(threads: int, dets: int, iters: int) -> float:
        t0 = time.perf_counter()
        core.dmcts(
            seat=0, hand=hands[0], unseen=hands[1] | hands[2] | hands[3],
            trick=[], trick_leader=0, contract=int(Contract.HEARTS),
            determinizations=dets, iterations=iters, seed=1, threads=threads,
        )
        return (dets * iters) / (time.perf_counter() - t0)

    single = dmcts_rate(1, 200, 800)
    parallel = dmcts_rate(os.cpu_count() or 8, 1000, 800)
    return {
        "rust_rollouts_per_second": round(rollouts),
        "rust_dmcts_iterations_per_second": round(single),
        "rust_dmcts_iterations_per_second_all_cores": round(parallel),
        "rust_seconds_per_move_at_tuned_budget": round(TUNED_BUDGET / parallel, 3),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--rounds", type=int, default=20_000)
    ap.add_argument("--rollouts", type=int, default=20_000)
    args = ap.parse_args()

    rounds_per_second = bench_rounds(args.rounds)
    rollouts_per_second = bench_rollouts(args.rollouts)

    result = {
        "rounds_per_second": round(rounds_per_second),
        "rollouts_per_second": round(rollouts_per_second),
        "seconds_per_move_at_tuned_budget": round(TUNED_BUDGET / rollouts_per_second, 1),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "cores": os.cpu_count(),
    }
    rust = bench_rust()
    if rust:
        result.update(rust)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"rounds/sec              {result['rounds_per_second']:>12,}")
    print(f"rollouts/sec (mid-round){result['rollouts_per_second']:>12,}")
    print()
    print(
        f"At the tuned {TUNED_BUDGET:,}-rollout budget that is "
        f"{result['seconds_per_move_at_tuned_budget']}s per move, single core."
    )
    print("A web move budget is ~1.5s. See docs/plan-review.md §1.")

    if rust:
        print()
        print("Rust core")
        print(f"  rollouts/sec                {result['rust_rollouts_per_second']:>14,}"
              f"   ({result['rust_rollouts_per_second'] / rollouts_per_second:.0f}x python)")
        print(f"  DMCTS iterations/sec (1)    {result['rust_dmcts_iterations_per_second']:>14,}")
        print(f"  DMCTS iterations/sec ({result['cores']})    "
              f"{result['rust_dmcts_iterations_per_second_all_cores']:>14,}")
        print()
        print(f"  Tuned {TUNED_BUDGET:,}-rollout budget: "
              f"{result['rust_seconds_per_move_at_tuned_budget']}s per move on all cores.")
    else:
        print("Rust core not built — see rust/README.md")
    print(f"[python {result['python']} on {result['machine']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
