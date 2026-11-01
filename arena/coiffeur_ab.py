"""Whole Coiffeur games between two row choices — step 5 of `docs/coiffeur-plan.md`.

Both sides play cards with the same search; only how they choose rows (and shove) differs. Each
seed is played twice with the sides swapped, so both see the same deals and the same random sheet
from both ends. The pair contributes the difference of A's total and B's total across the two
games — the Coiffeur is decided by the sheet's sum, so that is the quantity to test — and the
share of games A won is reported beside it.

Usage::

    python -m arena.coiffeur_ab --games 200 --baseline-weights old.json
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.arena import paired_test  # noqa: E402
from krass_jass.agent import DmctsAgent  # noqa: E402
from krass_jass.game import Game, Phase  # noqa: E402
from krass_jass.rules import COIFFEUR  # noqa: E402

CFG = COIFFEUR


def play(a, b, seed: int) -> tuple[int, int]:
    """One game, `a` on team 0. Returns the two totals."""
    seats = {0: a, 2: a, 1: b, 3: b}
    game = Game(cfg=CFG, seed=seed, game_id=f"c{seed}")
    while game.phase is not Phase.GAME_OVER:
        if game.phase is Phase.ROUND_OVER:
            game.next_round()
            continue
        seat = game.to_act
        agent = seats[seat]
        if game.phase is Phase.BIDDING:
            game.bid(seat, agent.coiffeur_choice(game.hand_of(seat), game.legal_choices(), game.row_multipliers))
        elif game.phase is Phase.BLOCK:
            game.choose_block(seat, agent.coiffeur_block(game.hand_of(seat), game.legal_blocks()))
        else:
            game.play(seat, agent.decide(game.observation(seat)))
    return game.scores[0], game.scores[1]


def _chunk(args):
    a, b, seed, indices = args
    out = []
    for i in indices:
        a0, b0 = play(a, b, seed + i)
        b1, a1 = play(b, a, seed + i)
        out.append((a0 + a1 - b0 - b1, (a0 > b0) + (a1 > b1) + 0.5 * ((a0 == b0) + (a1 == b1))))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--iterations", type=int, default=2400)
    ap.add_argument("--baseline-weights", type=Path, required=True, help="B's coiffeur_weights.json")
    ap.add_argument("--weights", type=Path, default=None, help="A's (default: the shipped file)")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = ap.parse_args()

    base = DmctsAgent(determinizations=40, iterations=args.iterations // 40, cfg=CFG,
                      read_bidding=False, bid_alpha=0.0, tree_policy=False, label="search")
    a = copy.copy(base)
    a.label = "A"
    a.coiffeur_weights = json.loads(args.weights.read_text()) if args.weights else None
    b = copy.copy(base)
    b.label = "B"
    b.coiffeur_weights = json.loads(args.baseline_weights.read_text())

    chunks = [range(i, args.games, args.workers) for i in range(args.workers)]
    rows = []
    with ProcessPoolExecutor(args.workers) as pool:
        for part in pool.map(_chunk, [(a, b, args.seed * 100_000, c) for c in chunks if c]):
            rows.extend(part)
    diffs = [d for d, _ in rows]
    wins = sum(w for _, w in rows) / (2 * len(rows))
    t, p = paired_test(diffs)
    mean = sum(diffs) / len(diffs)
    print(f"{len(rows)} paired games: A - B = {mean / 2:+.1f} points a game, t = {t:.2f}, p = {p:.3f}; "
          f"A wins {wins:.1%} of games")


if __name__ == "__main__":
    main()
