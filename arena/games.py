"""Whole games, to the target, counted in games won.

`arena.py` measures a *round*: two agents split one deal's points and the unit is a share.
That is the right instrument for card play and the wrong one for anything about the game, and
it cannot measure the game-score objective at all — `EVAL` has `target_score=None`, so in
that setting there is no line to play to and the objective it changes does not exist.

Worse, the round instrument would score the change *backwards*. An agent that takes a certain
sixty instead of gambling on ninety gives up points on purpose; measured in points it looks
worse while winning more games, which is the whole point of the change.

So: full games, paired the same way. Each seed is played twice with the sides swapped, so
both agents see the same deals from both ends, and the pair contributes one number — 1, ½ or
0. The pairing matters more here than in a round match, because a game is a long run of deals
and the luck does not average out inside one.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.arena import paired_test  # noqa: E402
from krass_jass.agent import Agent  # noqa: E402
from krass_jass.game import Game, Phase  # noqa: E402
from krass_jass.rules import HOUSE, RulesConfig  # noqa: E402


@dataclass
class GameResult:
    a: str
    b: str
    games: int
    a_wins: float          #: share of games won by A, ties counted as a half
    std: float
    t_statistic: float
    p_value: float

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05

    def __str__(self) -> str:
        mark = "" if self.significant else "  (not significant)"
        return (
            f"{self.a:>26} vs {self.b:<26} "
            f"{self.a_wins * 100:6.2f}% ± {self.std * 100:4.2f}  "
            f"n={self.games:<6} p={self.p_value:.2e}{mark}"
        )


def play_game(a: Agent, b: Agent, seed: int, cfg: RulesConfig) -> int:
    """One whole game. Returns the team index that won — `a` sits on team 0.

    Bots always announce their Weis: declining is a bluff and a bot that cannot read the
    table has no basis for one.
    """
    seats = {0: a, 2: a, 1: b, 3: b}
    game = Game(cfg=cfg, seed=seed, game_id=f"g{seed}")

    # Nine tricks a round, and a 2500-point game can run long; the bound is a guard against
    # a rule bug turning into a hang, not an expected outcome.
    for _ in range(20000):
        if game.phase is Phase.GAME_OVER:
            break
        if game.phase is Phase.ROUND_OVER:
            game.next_round()
            continue
        seat = game.to_act
        if seat is None:
            break
        agent = seats[seat]
        if game.phase is Phase.BIDDING:
            game.bid(seat, agent.select_trump(game.hand_of(seat), seat == game.forehand))
        elif game.phase is Phase.WEIS:
            game.choose_weis(seat, True)
        else:
            game.play(seat, agent.decide(game.observation(seat)))
    else:
        raise RuntimeError("game did not finish")

    return 0 if game.scores[0] >= game.scores[1] else 1


def _run_chunk(args) -> list[float]:
    a, b, cfg, seed, indices = args
    out = []
    for i in indices:
        # The same two games, sides swapped. Common random numbers: identical deal sequence
        # both ways, so what differs between the halves is only who sat where.
        first = play_game(a, b, seed + i, cfg)
        second = play_game(b, a, seed + i, cfg)
        wins = (1.0 if first == 0 else 0.0) + (1.0 if second == 1 else 0.0)
        out.append(wins / 2.0)
    return out


def game_match(
    a: Agent,
    b: Agent,
    games: int = 100,
    seed: int = 0,
    cfg: RulesConfig = HOUSE,
    workers: int | None = None,
) -> GameResult:
    """Run `games` paired games of A against B."""
    workers = workers or 1
    if workers <= 1:
        shares = _run_chunk((a, b, cfg, seed, range(games)))
    else:
        workers = min(workers, games)
        chunks = [range(i, games, workers) for i in range(workers)]
        payload = [(a, b, cfg, seed, c) for c in chunks]
        shares = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for part in pool.map(_run_chunk, payload):
                shares.extend(part)

    t, p = paired_test([s - 0.5 for s in shares])
    mean = sum(shares) / len(shares)
    var = sum((s - mean) ** 2 for s in shares) / max(1, len(shares) - 1)
    return GameResult(
        a=a.name, b=b.name, games=len(shares), a_wins=mean, std=var**0.5,
        t_statistic=t, p_value=p,
    )


def main() -> int:
    import argparse

    from krass_jass.agent import DmctsAgent

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--target", type=int, default=1000)
    ap.add_argument("--determinizations", type=int, default=40)
    ap.add_argument("--iterations", type=int, default=60)
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args()

    cfg = HOUSE.variant(target_score=args.target)
    budget = dict(determinizations=args.determinizations, iterations=args.iterations)
    # Team A plays for the game; team B plays for the round, which is what every earlier
    # measurement used. `cfg` differs only in what the objective reads off it.
    a = DmctsAgent(cfg=cfg, label="plays for the game", **budget)
    b = DmctsAgent(cfg=cfg.variant(target_score=None), label="plays for the round", **budget)
    print(game_match(a, b, games=args.games, seed=args.seed, cfg=cfg,
                     workers=args.workers or os.cpu_count()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
