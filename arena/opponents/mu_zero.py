"""Our bot against jass-mu-zero (Andrin Bürli, HSLU), double rounds, paired test.

jass-mu-zero (github.com/andrinbuerli/jass-mu-zero) is MuZero for the Schieber: a learned model
(representation, dynamics, prediction networks, ResNet, TensorFlow) and an MCTS over its latent
states — no determinisation, the network imagines the hidden cards. Trained weights are in the
repository under `resources/results/<run>/latest_network.pd` (Git LFS). The run its author rated
strongest is `1653237674` ("MCTS-100-S": 100 iterations, greedy, terminal function on), which beat
the smaller run 66% and its own raw policy 53% in the author's evaluation, and that is the default
here.

It runs as its own process — `arena/opponents/mu_zero_server.py`, started *in the opponent's own
venv* — which serves the HSLU jass-kit player protocol (`/<name>/action_trump`,
`/<name>/action_play_card`, the `GameObservation.to_json` body). This module only speaks HTTP to
it: nothing of jass-mu-zero (no licence file: all rights reserved) or of jass-kit-py (GPL-3.0) is
imported here or anywhere under `krass_jass/`. Our engine stays authoritative; every card it
returns is checked against our legal moves.

    python -m arena.opponents.mu_zero --deals 100 --seed 1 --urls http://127.0.0.1:9910 ...
    python -m arena.opponents.mu_zero --report .runs/muzero-1-shipped.jsonl

Seats. jass-kit numbers seats the other way round (`next_player = [3, 0, 1, 2]`: the player after
j is j-1), so our seat s is their seat -s mod 4; partners stay partners. Their dealer is the seat
*after* forehand in their numbering (forehand = next_player[dealer]). `forehand` in the body is -1
while forehand has yet to choose or shove, 1 when forehand declared, 0 when it shoved; their side
derives the declarer from it. Completed tricks carry winner and points (their features read the
running score), and the trick about to be led carries its `first` seat, as `to_json` writes it.

Card ids need no mapping: jass-kit and we both number cards suit*9 + rank with suits D H S C and
ranks A K Q J 10 9 8 7 6, and contracts 0-5 are the same six in the same order (10 = shove).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import statistics
import sys
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from arena.ab import build  # noqa: E402
from arena.arena import deal_spec, paired_test, play_round  # noqa: E402
from krass_jass.agent import Agent  # noqa: E402
from krass_jass.cards import RANK_CHARS, SUIT_CHARS, card_list, card_rank, card_suit  # noqa: E402
from krass_jass.rules import EVAL, HOUSE, SHOVE, Contract, RulesConfig  # noqa: E402
from krass_jass.tables import CARD_VALUES, STRENGTH  # noqa: E402
from krass_jass.trick import trick_winner  # noqa: E402

# "flat": every contract counts once, as in jass-kit, which is what the network was trained under.
# Our EVAL keeps our multipliers (Obenabe x3, Undenufe x4, ...), which its bidding never saw.
CFGS = {"eval": EVAL, "house": HOUSE.variant(target_score=None),
        "flat": EVAL.variant(multipliers={c: 1 for c in Contract})}
PUSH = 10  # jass-kit's code for shoving (PUSH_ALT = 6 is internal to their agent)
RESULTS = Path("arena/opponents/results.jsonl")


def kit_card(c: int) -> str:
    rank = RANK_CHARS[card_rank(c)]
    return SUIT_CHARS[card_suit(c)] + ("10" if rank == "T" else rank)


def our_card(text: str) -> int:
    suit = SUIT_CHARS.index(text[0])
    rank = "T" if text[1:] == "10" else text[1:]
    return suit * 9 + RANK_CHARS.index(rank)


def kit_seat(seat: int) -> int:
    return (-seat) % 4


def observation_body(hand: int, seat: int, forehand: int, forehand_flag: int, contract: int,
                     tricks_played, trick, trick_leader: int) -> dict:
    """A jass-kit `GameObservation.to_json` body, in their seat numbering. Seats in, ours."""
    tricks = []
    for lead, cards in tricks_played:
        winner = trick_winner(list(cards), lead, STRENGTH[Contract(contract)][card_suit(cards[0])])
        points = sum(CARD_VALUES[Contract(contract)][c] for c in cards)
        if len(tricks) == 8:
            points += 5
        tricks.append({"cards": [kit_card(c) for c in cards], "points": points,
                       "win": kit_seat(winner), "first": kit_seat(lead)})
    if len(tricks) < 9 and (trick or contract >= 0):
        entry = {"first": kit_seat(trick_leader)}
        if trick:
            entry["cards"] = [kit_card(c) for c in trick]
        tricks.append(entry)
    me = kit_seat(seat)
    players = [{"hand": []} for _ in range(4)]
    players[me] = {"hand": [kit_card(c) for c in card_list(hand)]}
    return {
        "version": "V0.2", "trump": contract, "dealer": (kit_seat(forehand) + 1) % 4,
        "currentPlayer": me, "playerView": me, "forehand": forehand_flag,
        "tricks": tricks, "player": players, "jassTyp": "SCHIEBER",
    }


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass
class MuZero(Agent):
    """An opponent behind `mu_zero_server.py`. Picklable: only URLs and log paths.

    Several servers (one per port) can share the load: a worker process picks one by its pid and
    holds that server's lock for the call, because one server process runs one search at a time.
    """

    cfg: RulesConfig = EVAL
    urls: tuple[str, ...] = ("http://127.0.0.1:9910",)
    player: str = "mu-zero"
    error_log: str = ".runs/muzero-errors.log"
    name: str = "jass-mu-zero"
    timeout: float = 600.0

    def _post(self, path: str, body: dict) -> dict:
        i = os.getpid() % len(self.urls)
        url = self.urls[i]
        req = urllib.request.Request(f"{url}/{self.player}/{path}", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with open(f".runs/muzero-{i}.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with _OPENER.open(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())

    def _log(self, kind: str, **data) -> None:
        with open(self.error_log, "a") as fh:
            fh.write(json.dumps({"kind": kind, **data}) + "\n")

    def select_trump(self, hand: int, is_forehand: bool):
        # Only the hand and whether it was shoved matter to the choice: seat it at our 0 as
        # forehand, or at our 2 when our 0 shoved to it.
        seat = 0 if is_forehand else 2
        body = observation_body(hand, seat, 0, -1 if is_forehand else 0, -1, (), (), 0)
        try:
            code = int(self._post("action_trump", body)["trump"])
        except Exception as e:  # a dead or failing server must not stall the match
            self._log("trump-error", error=repr(e))
            return super().select_trump(hand, is_forehand)
        if code == PUSH and is_forehand:
            return SHOVE
        if 0 <= code <= 5:
            return Contract(code)
        self._log("trump-illegal", code=code, forehand=is_forehand)
        return super().select_trump(hand, is_forehand)

    def decide(self, obs) -> int:
        # Forehand leads the first trick, so it is that trick's leader, played or in play.
        forehand = obs.tricks_played[0][0] if obs.tricks_played else obs.trick_leader
        flag = 1 if obs.declarer_seat == forehand else 0
        body = observation_body(obs.hand, obs.seat, forehand, flag, int(obs.contract),
                                obs.tricks_played, obs.trick, obs.trick_leader)
        try:
            card = our_card(self._post("action_play_card", body)["card"])
        except Exception as e:
            self._log("card-error", error=repr(e))
            return card_list(obs.legal_moves)[-1]
        if not obs.legal_moves >> card & 1:
            # Our engine decides what is legal. Record the disagreement and play our lowest legal.
            self._log("card-illegal", card=kit_card(card), hand=[kit_card(c) for c in card_list(obs.hand)],
                      trick=[kit_card(c) for c in obs.trick], contract=int(obs.contract))
            card = card_list(obs.legal_moves)[-1]
        return card


@dataclass
class _Spy(Agent):
    """Records the bidding and the contract of a half, then defers to the agent it wraps."""

    inner: Agent = None
    side: str = ""
    rec: dict = field(default_factory=dict)

    def __post_init__(self):
        self.cfg = self.inner.cfg
        self.name = self.inner.name

    def select_trump(self, hand: int, is_forehand: bool):
        action = self.inner.select_trump(hand, is_forehand)
        self.rec.setdefault("bids", []).append(
            [self.side, "shove" if action is SHOVE or action == SHOVE else Contract(action).name])
        return action

    def decide(self, obs) -> int:
        if "contract" not in self.rec:
            self.rec["contract"] = Contract(obs.contract).name
        return self.inner.decide(obs)


def _deal(args) -> dict:
    """`arena.double_round`, with the bidding of each half written down for the diagnosis."""
    ours, theirs, cfg, seed, index = args
    hands, c, leader, game_seed = deal_spec(seed, index, None)
    halves, totals = [], [0, 0]   # [ours, theirs]
    for ours_team in (0, 1):
        rec: dict = {}
        a, b = _Spy(inner=ours, side="ours", rec=rec), _Spy(inner=theirs, side="theirs", rec=rec)
        seats = {s: (a if s % 2 == ours_team else b) for s in range(4)}
        pts = play_round(hands, c, leader, seats, cfg, game_seed)
        totals[0] += pts[ours_team]
        totals[1] += pts[1 - ours_team]
        rec.update(ours=pts[ours_team], theirs=pts[1 - ours_team], declarer=rec["bids"][-1][0],
                   shoved=len(rec["bids"]) == 2)
        halves.append(rec)
    total = sum(totals)
    share = 0.5 if total == 0 else totals[0] / total
    return {"deal": index, "share": share, "halves": halves}


def _load(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {r["deal"]: r for r in rows}


def diagnose(rows: list[dict]) -> None:
    """Per contract and declaring side, shove rates, and the deals we lost most."""
    by = defaultdict(lambda: [0, 0, 0])   # (declarer, contract) -> [halves, ours, theirs]
    shoves = defaultdict(lambda: [0, 0])  # side -> [forehand decisions, shoves]
    for r in rows:
        for h in r["halves"]:
            k = (h["declarer"], h["contract"])
            by[k][0] += 1
            by[k][1] += h["ours"]
            by[k][2] += h["theirs"]
            first = h["bids"][0][0]
            shoves[first][0] += 1
            shoves[first][1] += h["shoved"]
    print("\n declarer  contract     halves  our share   ours/half  theirs/half")
    for side in ("ours", "theirs"):
        rows_side = sorted((k for k in by if k[0] == side), key=lambda k: -by[k][0])
        tot = [0, 0, 0]
        for k in rows_side:
            n, o, t = by[k]
            tot = [tot[0] + n, tot[1] + o, tot[2] + t]
            print(f" {side:<9} {k[1]:<12} {n:6d}  {o / max(1, o + t):8.1%}   {o / n:8.1f}  {t / n:10.1f}")
        n, o, t = tot
        if n:
            print(f" {side:<9} {'(all)':<12} {n:6d}  {o / max(1, o + t):8.1%}   {o / n:8.1f}  {t / n:10.1f}")
    for side, (n, s) in shoves.items():
        print(f" shove rate as forehand, {side}: {s}/{n} = {s / max(1, n):.1%}")
    print("\n deals lost most:")
    for r in sorted(rows, key=lambda r: r["share"])[:5]:
        desc = "; ".join(f"{h['declarer']} {h['contract']}{' (shoved)' if h['shoved'] else ''} "
                         f"{h['ours']}-{h['theirs']}" for h in r["halves"])
        print(f"  deal {r['deal']:4d}: {r['share']:.1%}  {desc}")


def report(paths: list[Path], diag: bool = True) -> None:
    arms = [_load(p) for p in paths]
    for p, arm in zip(paths, arms):
        shares = [r["share"] for r in arm.values()]
        t, pv = paired_test([s - 0.5 for s in shares])
        print(f"{p.name}: {statistics.fmean(shares):.2%} ± {statistics.stdev(shares):.2%}  "
              f"n={len(shares)}  p={pv:.2e}")
        if diag:
            diagnose(list(arm.values()))
    if len(arms) == 2:
        common = sorted(set(arms[0]) & set(arms[1]))
        diff = [arms[0][i]["share"] - arms[1][i]["share"] for i in common]
        t, pv = paired_test(diff)
        print(f"{paths[0].name} - {paths[1].name}: {statistics.fmean(diff):+.2%} "
              f"± {statistics.stdev(diff) / len(diff) ** 0.5:.2%} (se)  n={len(diff)}  p={pv:.2e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deals", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--cfg", choices=sorted(CFGS), default="eval")
    ap.add_argument("--urls", nargs="+", default=["http://127.0.0.1:9910"],
                    help="one mu_zero_server.py per URL; workers spread over them")
    ap.add_argument("--workers", type=int, default=None, help="default: one per URL")
    ap.add_argument("--ours", nargs="*", default=[], help="DmctsAgent field=value pairs, as arena.ab")
    ap.add_argument("--out", type=Path, help="per-deal results, one JSON line each; a rerun resumes")
    ap.add_argument("--report", type=Path, nargs="+", help="report one or two --out files and stop")
    args = ap.parse_args()
    if args.report:
        report(args.report)
        return

    Path(".runs").mkdir(exist_ok=True)
    cfg = CFGS[args.cfg]
    ours = build(args.ours, 153_600, cfg)  # 40 x 3,840, as served, unless --ours says otherwise
    theirs = MuZero(cfg=cfg, urls=tuple(args.urls))
    out = args.out or Path(f".runs/muzero-{args.seed}-{'-'.join(args.ours) or 'shipped'}.jsonl")
    done = _load(out)
    todo = [i for i in range(args.deals) if i not in done]
    print(f"{out}: {len(done)} done, {len(todo)} to play", flush=True)
    t = time.time()
    with ProcessPoolExecutor(max_workers=args.workers or len(args.urls)) as pool, out.open("a") as fh:
        futures = [pool.submit(_deal, (ours, theirs, cfg, args.seed, i)) for i in todo]
        for n, f in enumerate(as_completed(futures), 1):
            fh.write(json.dumps(f.result()) + "\n")
            fh.flush()
            if n % 10 == 0:
                print(f"  {n}/{len(todo)} ({(time.time() - t) / 60:.0f} min)", flush=True)

    rows = list(_load(out).values())
    shares = [r["share"] for r in rows]
    tstat, pv = paired_test([s - 0.5 for s in shares])
    mean, std = statistics.fmean(shares), statistics.stdev(shares)
    errors = Path(theirs.error_log).read_text().splitlines() if Path(theirs.error_log).exists() else []
    print(f"{ours.name} vs jass-mu-zero: {mean:.2%} ± {std:.2%}  n={len(shares)}  p={pv:.2e}  "
          f"errors/illegal logged: {len(errors)}")
    diagnose(rows)
    record = {
        "a": args.ours or ["shipped"], "b": ["jass-mu-zero/1653237674/mcts-100"], "deals": len(shares),
        "seed": args.seed, "iterations": ours.determinizations * ours.iterations, "cfg": args.cfg,
        "a_share": mean, "std": std, "p": pv, "se": std / len(shares) ** 0.5, "errors": len(errors),
        "minutes": round((time.time() - t) / 60, 1), "when": time.strftime("%Y-%m-%d %H:%M"),
    }
    with RESULTS.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
