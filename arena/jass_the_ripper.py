"""Our bot against JassTheRipper (Joel Niklaus, Fribourg/HSLU), double rounds, paired test.

JassTheRipper is the MCTS bot of the thesis this project's research section cites. It runs as its own
process — a Java REST server (`./gradlew startServer` in a local checkout of
github.com/JoelNiklaus/JassTheRipper, port 80) — and this module seats it at *our* engine's table
through that interface: `select_trump` and `play_card`, in the HSLU jass-kit request format. Our engine
stays authoritative; every card it returns is checked against our legal moves.

Nothing of JassTheRipper is imported or vendored: the repository has no licence file, so it is run
locally as an opponent and talked to over HTTP, nothing more.

    python -m arena.jass_the_ripper --deals 400 --seed 1                 # the shipped bot
    python -m arena.jass_the_ripper --deals 400 --seed 1 --ours belief_alpha=0 bid_alpha=0
    python -m arena.jass_the_ripper --report .runs/jtr-1-shipped.jsonl .runs/jtr-1-belief_alpha=0-bid_alpha=0.jsonl

Per-deal results go to a JSON-lines file as each deal finishes, and a rerun resumes from it. Arms on
the same seed play the same deals, so two arms compare deal by deal (`--report`).

Seats. HSLU numbers seats the other way round (the player after seat j is j-1), so our seat s is
their seat -s mod 4; partners stay partners. Their dealer is the seat after forehand in their
numbering. Their server asserts that the seat it reconstructs from the dealer and the played cards
is the seat we say is to play, so a wrong mapping fails loudly rather than quietly.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.ab import build  # noqa: E402
from arena.arena import deal_spec, double_round, paired_test  # noqa: E402
from krass_jass.agent import Agent  # noqa: E402
from krass_jass.cards import RANK_CHARS, SUIT_CHARS, card_list, card_rank, card_suit  # noqa: E402
from krass_jass.rules import EVAL, HOUSE, SHOVE, Contract, RulesConfig  # noqa: E402

CFGS = {"eval": EVAL, "house": HOUSE.variant(target_score=None)}
PUSH = 10  # their code for shoving


def jtr_card(c: int) -> str:
    rank = RANK_CHARS[card_rank(c)]
    return SUIT_CHARS[card_suit(c)] + ("10" if rank == "T" else rank)


def our_card(text: str) -> int:
    suit = SUIT_CHARS.index(text[0])
    rank = "T" if text[1:] == "10" else text[1:]
    return suit * 9 + RANK_CHARS.index(rank)


def jtr_seat(seat: int) -> int:
    return (-seat) % 4


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass
class JassTheRipper(Agent):
    """An opponent behind JassTheRipper's REST server. Picklable: only a URL and a log path."""

    cfg: RulesConfig = EVAL
    url: str = "http://localhost:80"
    endpoint: str = "runs-100000"
    illegal_log: str = ".runs/jtr-illegal.log"
    lock_file: str = ".runs/jtr.lock"
    name: str = "JassTheRipper"

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(
            f"{self.url}/{self.endpoint}/{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        # Their server is not thread-safe: two requests at once corrupt each other's search (it
        # answered with cards from the other request's hand). Every call goes through one lock,
        # across all worker processes; it still uses every core inside a move.
        with open(self.lock_file, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with _OPENER.open(req, timeout=600) as resp:
                return json.loads(resp.read())

    @staticmethod
    def _request(hand: int, current: int, dealer: int, tss: int, trump: int, tricks: list) -> dict:
        players = [{"hand": []} for _ in range(4)]
        players[current] = {"hand": [jtr_card(c) for c in card_list(hand)]}
        body = {
            "version": "V0.1", "dealer": dealer, "currentPlayer": current, "tss": tss,
            "tricks": tricks, "player": players, "jassTyp": "SCHIEBER", "gameId": "krass-jass",
            "seatId": current,
        }
        if trump >= 0:
            body["trump"] = trump
        return body

    def select_trump(self, hand: int, is_forehand: bool):
        # Only the hand and whether it was shoved matter to the choice, so seat it where the
        # server's own bookkeeping expects: forehand at 0 (dealer 1), or shoved-to partner at 0.
        forehand = 0 if is_forehand else 2
        body = self._request(hand, 0, (forehand + 1) % 4, 0 if is_forehand else 1, -1, [])
        code = self._post("select_trump", body)["trump"]
        if code == PUSH:
            return SHOVE
        return Contract(code)

    def decide(self, obs) -> int:
        forehand = obs.tricks_played[0][0] if obs.tricks_played else obs.trick_leader
        if not obs.tricks_played and not obs.trick:
            forehand = obs.trick_leader
        tss = int(obs.declarer_seat != forehand)
        tricks = [
            {"cards": [jtr_card(c) for c in cards], "points": 0, "win": 0, "first": jtr_seat(lead)}
            for lead, cards in obs.tricks_played
        ]
        if obs.trick:
            tricks.append({"cards": [jtr_card(c) for c in obs.trick], "points": 0, "win": 0,
                           "first": jtr_seat(obs.trick_leader)})
        body = self._request(obs.hand, jtr_seat(obs.seat), (jtr_seat(forehand) + 1) % 4, tss,
                             int(obs.contract), tricks)
        card = our_card(self._post("play_card", body)["card"])
        if not obs.legal_moves >> card & 1:
            # Our engine decides what is legal. Record the disagreement and play our lowest legal.
            with open(self.illegal_log, "a") as fh:
                fh.write(json.dumps({"card": jtr_card(card), "hand": [jtr_card(c) for c in card_list(obs.hand)],
                                     "trick": [jtr_card(c) for c in obs.trick],
                                     "contract": int(obs.contract)}) + "\n")
            card = card_list(obs.legal_moves)[-1]
        return card


def _deal(args) -> tuple[int, float]:
    ours, theirs, cfg, seed, index = args
    hands, c, leader, game_seed = deal_spec(seed, index, None)
    share, _ = double_round(hands, c, leader, ours, theirs, cfg, game_seed)
    return index, share


def _load(path: Path) -> dict[int, float]:
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {r["deal"]: r["share"] for r in rows}


def report(paths: list[Path]) -> None:
    """Each arm's share against JassTheRipper; with two arms, their per-deal difference, paired.

    The arms play the same deals (same seed), so arm-minus-arm per deal cancels the deal's luck
    the way a double round does inside one match.
    """
    arms = [_load(p) for p in paths]
    for p, arm in zip(paths, arms):
        shares = list(arm.values())
        t, pv = paired_test([s - 0.5 for s in shares])
        print(f"{p.name}: {statistics.fmean(shares):.2%} ± {statistics.stdev(shares):.2%}  "
              f"n={len(shares)}  p={pv:.2e}")
    if len(arms) == 2:
        common = sorted(set(arms[0]) & set(arms[1]))
        diff = [arms[0][i] - arms[1][i] for i in common]
        t, pv = paired_test(diff)
        print(f"{paths[0].name} - {paths[1].name}: {statistics.fmean(diff):+.2%} "
              f"± {statistics.stdev(diff) / len(diff) ** 0.5:.2%} (se)  n={len(diff)}  p={pv:.2e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deals", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--endpoint", default="runs-100000")
    ap.add_argument("--cfg", choices=sorted(CFGS), default="eval")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--ours", nargs="*", default=[], help="DmctsAgent field=value pairs, as arena.ab")
    ap.add_argument("--out", type=Path, help="per-deal results, one JSON line each; a rerun resumes")
    ap.add_argument("--report", type=Path, nargs="+", help="report one or two --out files and stop")
    args = ap.parse_args()
    if args.report:
        report(args.report)
        return

    cfg = CFGS[args.cfg]
    ours = build(args.ours, 153_600, cfg)  # 40 x 3,840, as served, unless --ours says otherwise
    theirs = JassTheRipper(cfg=cfg, endpoint=args.endpoint)
    out = args.out or Path(f".runs/jtr-{args.seed}-{'-'.join(args.ours) or 'shipped'}.jsonl")
    done = _load(out)
    todo = [i for i in range(args.deals) if i not in done]
    print(f"{out}: {len(done)} done, {len(todo)} to play", flush=True)
    t = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool, out.open("a") as fh:
        futures = [pool.submit(_deal, (ours, theirs, cfg, args.seed, i)) for i in todo]
        for n, f in enumerate(as_completed(futures), 1):
            index, share = f.result()
            fh.write(json.dumps({"deal": index, "share": share}) + "\n")
            fh.flush()
            if n % 10 == 0:
                print(f"  {n}/{len(todo)} ({(time.time() - t) / 60:.0f} min)", flush=True)

    shares = list(_load(out).values())
    tstat, pv = paired_test([s - 0.5 for s in shares])
    mean, std = statistics.fmean(shares), statistics.stdev(shares)
    print(f"{ours.name} vs JassTheRipper/{args.endpoint}: {mean:.2%} ± {std:.2%}  n={len(shares)}  p={pv:.2e}")
    record = {
        "a": args.ours or ["shipped"], "b": [f"JassTheRipper/{args.endpoint}"], "deals": len(shares),
        "seed": args.seed, "iterations": ours.determinizations * ours.iterations, "cfg": args.cfg,
        "a_share": mean, "std": std, "p": pv, "se": std / len(shares) ** 0.5,
        "minutes": round((time.time() - t) / 60, 1), "when": time.strftime("%Y-%m-%d %H:%M"),
    }
    with Path("arena/results.jsonl").open("a") as fh:
        fh.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
