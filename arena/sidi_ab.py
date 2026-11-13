"""A/B two `DmctsAgent` configurations at Sidi Barrani, and keep the result.

The Schieber protocol (`arena/ab.py`) carried over: every hand is played twice with the teams
swapped, on the same seed, and the per-hand differences get a paired test. What changes is the
unit. A Sidi hand is written as cards *plus the stake*, so the measure is the **points written**
per hand — A's team minus B's — rather than a share of the 157 card points.

Each seat bids and doubles with its own agent. Arms that differ only in how they play bid
identically in both halves of a pair, so only the play is measured; arms that differ in how they
double (`sidi_double_model`) are measured on the doubling as well.

    python -m arena.sidi_ab --a sidi_alpha=0 --deals 1000 --seed 5

The bidding style is the table's, not an agent's (`RulesConfig.sidi_bid_styles`): `--style-a
feel` seats team A as «Gspürsch mi, füehlsch mi» bidders, and every seat is told so, as at a
real table. `--told-a count` tells team B's seats that A counts while A feels its way — the
price of misreading a style, the nearest thing to a partner who bids as they like.

    python -m arena.sidi_ab --style-a feel --deals 1000 --seed 7
    python -m arena.sidi_ab --style-a feel --style-b feel --told-a count --deals 1000 --seed 8
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.ab import parse  # noqa: E402
from arena.arena import paired_test  # noqa: E402
from krass_jass.agent import DmctsAgent  # noqa: E402
from krass_jass.game import Game, Phase  # noqa: E402
from krass_jass.rules import SIDI_EVAL  # noqa: E402
from krass_jass.sidi_bidding import STYLES  # noqa: E402


def build(pairs: list[str], iterations: int) -> DmctsAgent:
    kw = {"determinizations": 40, "iterations": max(1, iterations // 40), "cfg": SIDI_EVAL,
          "label": ",".join(pairs) or "shipped"}
    kw.update(parse(pairs))
    return DmctsAgent(**kw)


def knock(game: Game, seats: dict, asked: set, heard: dict) -> None:
    """Every seat opposing the standing bid gets to knock, the moment the bid is made.

    A double may come out of turn, and the app asks the bots that way, so the arena does too.
    """
    auction = game.auction
    if game.phase is not Phase.BIDDING or auction is None or auction.high is None or auction.doubled:
        return
    key = (game.round_index, len(auction.calls))
    if key in asked:
        return
    asked.add(key)
    public = game.public_auction()
    for step in (1, 3):
        actor = (auction.high[0] + step) % 4
        if auction.may_double(actor) and seats[actor].sidi_knock(
            game.hand_of(actor), public, actor, heard[actor]
        ):
            game.bid(actor, "DOUBLE")
            return


def play_hand(seed: int, seats: dict, styles: tuple = (), told: tuple = ()) -> list[int]:
    """One Sidi hand to the end; what each team wrote.

    `styles` is how each seat bids; `told` what the *other* team has been told it bids (the
    truth unless given). A seat always knows its own side's style.
    """
    styles = styles or ("count",) * 4
    told = told or styles
    game = Game(cfg=SIDI_EVAL.variant(sidi_bid_styles=styles), seed=seed, game_id=f"sidi-{seed}")
    # What each seat believes the table speaks: the truth about its own side, `told` about the other.
    heard = {
        seat: tuple(styles[s] if (s - seat) % 2 == 0 else told[s] for s in range(4))
        for seat in range(4)
    }
    asked: set = set()
    while game.phase is not Phase.ROUND_OVER:
        knock(game, seats, asked, heard)
        if game.phase is Phase.ROUND_OVER:
            break
        seat = game.to_act
        agent = seats[seat]
        if game.phase is Phase.BIDDING:
            game.bid(seat, agent.sidi_call(
                game.hand_of(seat), game.public_auction(), seat, heard[seat]
            ))
        elif game.phase is Phase.DOUBLING:
            obs = dataclasses.replace(game.observation(seat), bid_styles=heard[seat])
            game.double(seat, agent.sidi_double(obs))
        else:
            obs = dataclasses.replace(game.observation(seat), bid_styles=heard[seat])
            game.play(seat, agent.decide(obs))
    return list(game.last_score["round_total"])


def double_hand(args) -> tuple[float, dict]:
    seed, a, b, style, told = args
    # Team A sits at 0 and 2, then at 1 and 3; its style and what is told about it move with it.
    first = play_hand(
        seed, {0: a, 2: a, 1: b, 3: b},
        (style[0], style[1]) * 2, (told[0], told[1]) * 2,
    )
    second = play_hand(
        seed, {1: a, 3: a, 0: b, 2: b},
        (style[1], style[0]) * 2, (told[1], told[0]) * 2,
    )
    diff = ((first[0] - first[1]) + (second[1] - second[0])) / 2
    return diff, {"a_written": first[0] + second[1], "b_written": first[1] + second[0]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", nargs="*", default=[])
    ap.add_argument("--b", nargs="*", default=[])
    ap.add_argument("--deals", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--iterations", type=int, default=153600)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--log", type=Path, default=Path("arena/results.jsonl"))
    ap.add_argument("--style-a", choices=STYLES, default="count", help="how team A bids")
    ap.add_argument("--style-b", choices=STYLES, default="count", help="how team B bids")
    ap.add_argument("--told-a", choices=STYLES, help="what team B is told A bids (default: the truth)")
    ap.add_argument("--told-b", choices=STYLES, help="what team A is told B bids (default: the truth)")
    args = ap.parse_args()
    style = (args.style_a, args.style_b)
    told = (args.told_a or args.style_a, args.told_b or args.style_b)

    a, b = build(args.a, args.iterations), build(args.b, args.iterations)
    jobs = [(args.seed * 100_000 + i, a, b, style, told) for i in range(args.deals)]
    t = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        out = list(ex.map(double_hand, jobs, chunksize=4))
    elapsed = time.time() - t
    diffs = [d for d, _ in out]
    a_total = sum(x["a_written"] for _, x in out)
    b_total = sum(x["b_written"] for _, x in out)
    _, p = paired_test(diffs)
    mean, sd = statistics.fmean(diffs), statistics.stdev(diffs)
    share = a_total / (a_total + b_total)
    print(
        f"{','.join(args.a) or 'shipped'} [{style[0]}] vs {','.join(args.b) or 'shipped'} [{style[1]}]   "
        f"{mean:+.2f} points a hand ± {sd:.1f}   written share {share:.2%}   "
        f"n={args.deals}  p={p:.2e}  ({elapsed / 60:.1f} min)"
    )
    record = {
        "mode": "sidi", "a": args.a, "b": args.b, "deals": args.deals, "seed": args.seed,
        "style": list(style), "told": list(told),
        "iterations": args.iterations, "points_per_hand": mean, "std": sd, "p": p,
        "a_written_share": share, "minutes": round(elapsed / 60, 1),
        "when": time.strftime("%Y-%m-%d %H:%M"),
    }
    with args.log.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
