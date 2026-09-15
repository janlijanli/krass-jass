"""Decisions from self-play *with the true deal*, for training `rust/src/beliefnet.rs`.

The belief network predicts where the hidden cards are, so its labels are the hands the other
seats actually held. Every simulated round knows them — no cheating agent is involved, only
the arena, which already owns the true deal (like `cheating.py` and `oracle.py`, this lives in
`arena/` and nothing that serves a game imports it).

What is stored splits cleanly in two:

- **inputs** — only what the deciding seat could see: its hand, the play history, the proven
  constraints, the cards a Weis showed, the values called, the bid;
- **labels** — `truth`, the four hands at that moment, used for nothing but the loss.

HOUSE rules with Weis on, so the calls and the shown cards the network learns to read are the
ones a real table produces. The players are the shipped search, the same bots the play model
was fitted to.

Usage::

    python -m arena.belief_data --rounds 6000 --iterations 38400 --out beliefs.npz
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


def public_inputs(obs, agent: DmctsAgent) -> dict:
    """The belief network's inputs, from an observation alone."""
    forbidden, _ = agent._beliefs(obs)
    history = agent._play(obs)["history"]
    known = [0, 0, 0, 0]
    for s, c in obs.known_cards:
        known[s] |= 1 << c
    called = [-1, -1, -1, -1]
    for s, points in obs.weis_announced:
        called[s] = points
    return {
        "seat": obs.seat,
        "hand": obs.hand,
        "history": history,
        "contract": int(obs.contract),
        "declarer": obs.declarer_seat,
        "forehand": obs.forehand,
        "forbidden": list(forbidden),
        "known": known,
        "weis_called": called,
    }


def _chunk(args):
    seed, indices, iterations, belief_pool = args
    agent = DmctsAgent(determinizations=40, iterations=max(1, iterations // 40), cfg=HOUSE,
                       belief_pool=belief_pool)
    seats = {s: agent for s in range(4)}
    rows = []
    for index in indices:
        hands, _, leader, game_seed = deal_spec(seed, index, None)
        contract, declarer = choose_contract(hands, leader, seats, HOUSE)
        _, _, shown, announced = resolve_weis(hands, contract, leader, HOUSE)
        st = RoundState(contract=contract, hands=list(hands), cfg=HOUSE, leader=leader)
        while not st.done:
            seat = st.to_play
            obs = build_observation(
                st, seat, declarer_seat=declarer,
                decision_seed=derive_decision_seed(game_seed, f"belief{index}", seat, 0,
                                                   len(st.tricks_played)),
                known_cards=tuple((s, c) for s, c in shown if st.hands[s] & (1 << c)),
                weis_announced=announced,
            )
            if obs.unseen:
                x = public_inputs(obs, agent)
                hist = np.full((36, 2), -1, dtype=np.int8)
                for i, (s, c) in enumerate(x["history"]):
                    hist[i] = (s, c)
                rows.append((
                    index, x["seat"], x["hand"], hist, x["contract"], x["declarer"],
                    x["forehand"], x["forbidden"], x["known"], x["weis_called"],
                    list(obs.played_by), list(st.hands),
                ))
            st.play(agent.decide(obs))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--iterations", type=int, default=38400)
    ap.add_argument("--belief-pool", type=int, default=4096,
                    help="worlds the recording bots weight per decision; smaller is faster")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    workers = max(1, min(args.workers, args.rounds))
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
        history=np.stack(cols[3]),
        contract=np.array(cols[4], dtype=np.int8),
        declarer=np.array(cols[5], dtype=np.int8),
        forehand=np.array(cols[6], dtype=np.int8),
        forbidden=np.array(cols[7], dtype=np.uint64),
        known=np.array(cols[8], dtype=np.uint64),
        weis_called=np.array(cols[9], dtype=np.int16),
        played_by=np.array(cols[10], dtype=np.uint64),
        truth=np.array(cols[11], dtype=np.uint64),
        iterations=args.iterations,
        seed=args.seed,
    )
    print(f"wrote {len(rows)} decisions from {args.rounds} rounds to {args.out}")


if __name__ == "__main__":
    main()
