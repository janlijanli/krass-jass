"""Our bot against pyschieber's players (Murthy10/pyschieber, MIT): `ChallengePlayer`, a rule-based
bot with a card counter and a strategy per contract, and `GreedyPlayer` as a floor rung.

It runs in its own Python process (`bridges/pyschieber_bridge.py`, `python -I`, no network
namespace), which rebuilds the player for every decision and replays to it what
`pyschieber/game.py` would have called up to that point. Nothing of pyschieber is imported here.

    git clone --depth 1 https://github.com/Murthy10/pyschieber /home/user/ext/Murthy10_pyschieber
    python -m arena.opponents.pyschieber --deals 400 --seed 1
    python -m arena.opponents.pyschieber --player GreedyPlayer --deals 100 --seed 1

Seats. pyschieber numbers players 0..3 in play order with partner id+2 (`tournament.py` assigns ids
in seat order, `game.py` plays (start + i) % 4), which is ours: our seat s is their id s. Suits are
symmetric, so ours D/H/S/C are their ROSE/BELL/ACORN/SHIELD in that order; their card values are
6..14 with 10 Banner, 11 Under (the Jack), 12 Ober, 13 Koennig, 14 Ass.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from arena.opponents.common import (
    EXT, Agent, RulesConfig, ask, checked, dealt_hand, forehand_of, log_event, main, trick_winners,
)
from krass_jass.cards import card_list, card_rank, card_suit
from krass_jass.rules import EVAL, SHOVE, Contract

BRIDGE = str(Path(__file__).resolve().parent / "bridges" / "pyschieber_bridge.py")
SUITS = ["ROSE", "BELL", "ACORN", "SHIELD"]
NAMES = {6: "6", 7: "7", 8: "8", 9: "9", 10: "Banner", 11: "Under", 12: "Ober", 13: "Koennig", 14: "Ass"}
VALUES = {v: k for k, v in NAMES.items()}


def ps_card(c: int) -> str:
    return f"<{SUITS[card_suit(c)]}:{NAMES[14 - card_rank(c)]}>"


def our_card_ps(text: str) -> int:
    suit, name = text[1:-1].split(":")
    return SUITS.index(suit) * 9 + 14 - VALUES[name]


def ps_trumpf(contract: Contract) -> str:
    if contract.is_trump:
        return SUITS[int(contract)]
    return "OBE_ABE" if contract == Contract.OBENABE else "UNDE_UFE"


def our_trumpf_ps(name: str):
    if name == "SCHIEBEN":
        return SHOVE
    if name in SUITS:
        return Contract(SUITS.index(name))
    return Contract.OBENABE if name == "OBE_ABE" else Contract.UNDENUFE


def cards(mask_or_list) -> list[str]:
    seq = card_list(mask_or_list) if isinstance(mask_or_list, int) else mask_or_list
    return [ps_card(c) for c in seq]


@dataclass
class Pyschieber(Agent):
    """Picklable: a checkout path, a player class name and a log path."""

    cfg: RulesConfig = EVAL
    checkout: str = str(EXT / "Murthy10_pyschieber")
    player: str = "ChallengePlayer"
    log: str = ".runs/pyschieber-events.jsonl"
    name: str = "pyschieber/ChallengePlayer"

    def _ask(self, request):
        return ask(("unshare", "-n", sys.executable, "-I", BRIDGE, self.checkout, self.player), request)

    def select_trump(self, hand: int, is_forehand: bool):
        try:
            answer = self._ask({"op": "trumpf", "hand": cards(hand), "geschoben": not is_forehand,
                                "seed": hand & 0xFFFFFFFF})
            choice = our_trumpf_ps(answer["trumpf"])
            if choice == SHOVE and not is_forehand:
                raise ValueError("shoved back")
            return choice
        except Exception as e:  # noqa: BLE001 — a broken opponent must not stop the match
            log_event(self.log, {"kind": "trump_error", "error": repr(e)[:300]})
            return super().select_trump(hand, is_forehand)

    def decide(self, obs) -> int:
        request = {
            "op": "card", "seat": obs.seat, "hand": cards(dealt_hand(obs)),
            "trumpf": ps_trumpf(obs.contract), "geschoben": obs.declarer_seat != forehand_of(obs),
            "seed": obs.decision_seed & 0xFFFFFFFF,
            "tricks": [{"leader": lead, "cards": cards(list(cs)), "winner": w}
                       for (lead, cs), w in zip(obs.tricks_played, trick_winners(obs))],
            "leader": obs.trick_leader, "table": cards(list(obs.trick)),
        }
        try:
            answer = self._ask(request)
            card = our_card_ps(answer["card"]) if "card" in answer else None
            why = {} if card is not None else {"error": str(answer.get("error"))[-300:]}
        except Exception as e:  # noqa: BLE001
            card, why = None, {"error": repr(e)[:300]}
        return checked(card, obs, self.log, why)


def _args(ap) -> None:
    ap.add_argument("--player", choices=["ChallengePlayer", "GreedyPlayer"], default="ChallengePlayer")


if __name__ == "__main__":
    main("pyschieber", lambda cfg, args: Pyschieber(
        cfg=cfg, player=args.player, name=f"pyschieber/{args.player}",
        log=f".runs/pyschieber-{args.player}-events.jsonl"), _args)
