"""Decisions from self-play, for fitting the play model in `rust/src/playmodel.rs`.

The model is a model of *how a seat plays*, and the players it will be asked about are our
own bots, so the data is the shipped search playing itself: HOUSE rules, Weis on, the rule
selector bidding, conventions on — every choice exactly as it would be made at the table.

What is stored is only what the deciding seat could see, plus the choice. The features are
computed later, in Rust, from those fields — one feature function for training and play.

Usage::

    python -m arena.policy_data --rounds 6000 --iterations 38400 --out decisions.npz
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from arena.arena import deal_spec, play_round  # noqa: E402
from krass_jass import convention  # noqa: E402
from krass_jass.agent import Agent, DmctsAgent  # noqa: E402
from krass_jass.cards import card_list  # noqa: E402
from krass_jass.observation import Observation  # noqa: E402
from krass_jass.rules import HOUSE  # noqa: E402


@dataclass
class RecordingAgent(Agent):
    """Plays exactly as `inner` does, and writes down each decision it had to make."""

    inner: DmctsAgent = field(default_factory=DmctsAgent)
    round_id: int = 0
    records: list = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"recording({self.inner.name})"

    def select_trump(self, hand, is_forehand):
        return self.inner.select_trump(hand, is_forehand)

    def decide(self, obs: Observation) -> int:
        legal = card_list(obs.legal_moves)
        if len(legal) == 1:
            return legal[0]
        candidates = self.inner.trace(obs)
        if self.inner.conventions:
            forbidden, _ = self.inner._beliefs(obs)
            card = convention.choose(candidates, obs, forbidden)
        else:
            card = candidates[0][0]
        visits = [0] * 36
        for c, v, _, _ in candidates:
            visits[c] = v
        trick = list(obs.trick) + [-1] * (3 - len(obs.trick))
        self.records.append((
            self.round_id, obs.seat, obs.hand, obs.hand | obs.unseen, trick, obs.trick_leader,
            int(obs.contract), obs.declarer_seat, obs.legal_moves, card, visits,
        ))
        return card


def _chunk(args):
    seed, indices, iterations, belief_pool = args
    inner = DmctsAgent(determinizations=40, iterations=max(1, iterations // 40), cfg=HOUSE,
                       belief_pool=belief_pool)
    rec = RecordingAgent(inner=inner)
    for i in indices:
        hands, _, leader, game_seed = deal_spec(seed, i, None)
        rec.round_id = i
        play_round(hands, None, leader, {s: rec for s in range(4)}, HOUSE, game_seed, f"policy{i}")
    return rec.records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--iterations", type=int, default=38400)
    ap.add_argument("--belief-pool", type=int, default=4096,
                    help="worlds the recorded bots weight per decision; smaller is faster")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    workers = max(1, min(args.workers, args.rounds))
    # Many small chunks rather than one per worker, so progress is visible and a crash late in
    # a long run loses little.
    step = max(1, args.rounds // (workers * 20))
    chunks = [list(range(i, min(i + step, args.rounds))) for i in range(0, args.rounds, step)]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for n, part in enumerate(pool.map(_chunk, [(args.seed, c, args.iterations, args.belief_pool) for c in chunks])):
            rows.extend(part)
            if n % 20 == 0:
                print(f"  {len(rows)} decisions after {n + 1}/{len(chunks)} chunks", flush=True)

    cols = list(zip(*rows))
    np.savez_compressed(
        args.out,
        round_id=np.array(cols[0], dtype=np.int32),
        seat=np.array(cols[1], dtype=np.int8),
        hand=np.array(cols[2], dtype=np.uint64),
        live=np.array(cols[3], dtype=np.uint64),
        trick=np.array(cols[4], dtype=np.int8),
        trick_leader=np.array(cols[5], dtype=np.int8),
        contract=np.array(cols[6], dtype=np.int8),
        declarer=np.array(cols[7], dtype=np.int8),
        legal=np.array(cols[8], dtype=np.uint64),
        card=np.array(cols[9], dtype=np.int8),
        visits=np.array(cols[10], dtype=np.int32),
        iterations=args.iterations,
        seed=args.seed,
    )
    print(f"wrote {len(rows)} decisions from {args.rounds} rounds to {args.out}")


if __name__ == "__main__":
    main()
