"""Our bot against JassTheRipper (Joel Niklaus, Fribourg/HSLU), double rounds, paired test.

JassTheRipper is the MCTS bot of the thesis this project's research section cites. It runs as its own
process — a Java REST server (`./gradlew startServer` in a local checkout of
github.com/JoelNiklaus/JassTheRipper, port 80) — and this module seats it at *our* engine's table
through that interface: `select_trump` and `play_card`, in the HSLU jass-kit request format. Our engine
stays authoritative; every card it returns is checked against our legal moves.

Nothing of JassTheRipper is imported or vendored: the repository has no licence file, so it is run
locally as an opponent and talked to over HTTP, nothing more.

    python -m arena.jass_the_ripper --deals 100 --endpoint runs-100000

Seats. HSLU numbers seats the other way round (the player after seat j is j-1), so our seat s is
their seat -s mod 4; partners stay partners. Their dealer is the seat after forehand in their
numbering. Their server asserts that the seat it reconstructs from the dealer and the played cards
is the seat we say is to play, so a wrong mapping fails loudly rather than quietly.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.arena import match  # noqa: E402
from krass_jass.agent import Agent, DmctsAgent  # noqa: E402
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deals", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--endpoint", default="runs-100000")
    ap.add_argument("--cfg", choices=sorted(CFGS), default="eval")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--log", type=Path, default=Path("arena/results.jsonl"))
    args = ap.parse_args()

    cfg = CFGS[args.cfg]
    ours = DmctsAgent(determinizations=40, iterations=3840, cfg=cfg, label="shipped")  # as served
    theirs = JassTheRipper(cfg=cfg, endpoint=args.endpoint)
    t = time.time()
    result = match(ours, theirs, deals=args.deals, seed=args.seed, cfg=cfg, workers=args.workers)
    elapsed = time.time() - t
    print(result, f"({elapsed / 60:.1f} min)")
    record = {
        "a": ["shipped"], "b": [f"JassTheRipper/{args.endpoint}"], "deals": args.deals,
        "seed": args.seed, "iterations": ours.determinizations * ours.iterations, "cfg": args.cfg,
        "a_share": result.a_share, "std": result.std, "p": result.p_value,
        "se": result.std / (args.deals ** 0.5), "minutes": round(elapsed / 60, 1),
        "when": time.strftime("%Y-%m-%d %H:%M"),
    }
    with args.log.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
