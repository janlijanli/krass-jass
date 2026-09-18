"""Positions from self-play, labelled with what actually happened — for `rust/src/valuenet.rs`.

The label is the one §5g did not use. There, a leaf evaluator was fitted to the random playout's
own average, so the best it could become was a lower-variance copy of a random player's opinion.
Here every position is labelled with the fraction of the **remaining** points the team to move
went on to take, in a round our own bot played to the end: the value of the position under good
play.

Every position of every round is kept — the search evaluates leaves mid-trick as well as at trick
boundaries — together with the four hands, which is fine because the value network only ever sees
positions inside an imagined world, where all four hands are known by construction. This lives in
`arena/` like the other recorders that hold the true deal.

Usage::

    python -m arena.value_data --rounds 12000 --out values.npz
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from arena.arena import choose_contract, deal_spec, resolve_weis  # noqa: E402
from krass_jass.agent import DmctsAgent  # noqa: E402
from krass_jass.observation import build_observation, derive_decision_seed  # noqa: E402
from krass_jass.rules import HOUSE  # noqa: E402
from krass_jass.state import RoundState  # noqa: E402


def _chunk(args):
    seed, indices, iterations, belief_pool = args
    # The tree policy is left off: it costs ~6x a move and the labels need volume more than the
    # last point of play quality.
    agent = DmctsAgent(determinizations=40, iterations=max(1, iterations // 40), cfg=HOUSE,
                       belief_pool=belief_pool, tree_policy=False)
    seats = {s: agent for s in range(4)}
    rows = []
    for index in indices:
        hands, _, leader, game_seed = deal_spec(seed, index, None)
        contract, declarer = choose_contract(hands, leader, seats, HOUSE)
        _, _, shown, announced = resolve_weis(hands, contract, leader, HOUSE)
        st = RoundState(contract=contract, hands=list(hands), cfg=HOUSE, leader=leader)
        positions = []
        while not st.done:
            trick = list(st.trick) + [-1] * (3 - len(st.trick))
            positions.append((list(st.hands), trick, st.leader, st.to_play, list(st.trick_points)))
            seat = st.to_play
            obs = build_observation(
                st, seat, declarer_seat=declarer,
                decision_seed=derive_decision_seed(game_seed, f"value{index}", seat, 0,
                                                   len(st.tricks_played)),
                known_cards=tuple((s, c) for s, c in shown if st.hands[s] & (1 << c)),
                weis_announced=announced,
            )
            st.play(agent.decide(obs))
        score = st.score(weis=(0, 0), stoeck=(0, 0))
        final = [score.trick_points[t] + score.last_trick[t] for t in (0, 1)]
        for hands_now, trick, leader_now, to_play, pts in positions:
            remaining = [final[t] - pts[t] for t in (0, 1)]
            total = remaining[0] + remaining[1]
            if total <= 0:
                continue
            rows.append((index, hands_now, trick, leader_now, int(contract),
                         remaining[to_play & 1] / total, total))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=12000)
    ap.add_argument("--seed", type=int, default=41)
    ap.add_argument("--iterations", type=int, default=38400)
    ap.add_argument("--belief-pool", type=int, default=1024)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    workers = max(1, min(args.workers, args.rounds))
    step = max(1, args.rounds // (workers * 20))
    chunks = [list(range(i, min(i + step, args.rounds))) for i in range(0, args.rounds, step)]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for n, part in enumerate(pool.map(_chunk, [(args.seed, c, args.iterations, args.belief_pool)
                                                   for c in chunks])):
            rows.extend(part)
            if n % 20 == 0:
                print(f"  {len(rows)} positions after {n + 1}/{len(chunks)} chunks", flush=True)

    cols = list(zip(*rows))
    np.savez_compressed(
        args.out,
        round_id=np.array(cols[0], dtype=np.int32),
        hands=np.array(cols[1], dtype=np.uint64),
        trick=np.array(cols[2], dtype=np.int8),
        trick_leader=np.array(cols[3], dtype=np.int8),
        contract=np.array(cols[4], dtype=np.int8),
        fraction=np.array(cols[5], dtype=np.float32),
        remaining=np.array(cols[6], dtype=np.int16),
        iterations=args.iterations,
        seed=args.seed,
    )
    print(f"wrote {len(rows)} positions from {args.rounds} rounds to {args.out}")


if __name__ == "__main__":
    main()
