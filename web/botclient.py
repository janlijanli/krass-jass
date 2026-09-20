"""HTTP client for the bot services.

Implements the same `Agent` interface as the in-process agents, so `web/app.py` does not
know or care which it is talking to. That is deliberate: the arena and self-play must keep
importing the library directly, and a client that pretended to be something else would
invite someone to route them through HTTP.

**Threat T4 lives here.** A hung or slow bot must not stall a game. Every call has a hard
timeout, and every failure — timeout, connection refused, malformed answer, an illegal card —
falls back to a random legal move. A game continues even if a bot container is wedged; it
just plays badly, which is visible and recoverable, unlike a stalled table.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

import httpx

from krass_jass.agent import Agent
from krass_jass.cards import card_list, format_card, parse_card
from krass_jass.observation import Observation
from krass_jass.rules import SHOVE, Contract

log = logging.getLogger(__name__)

#: Headroom over the bot's own budget. Beyond this the answer is not worth waiting for.
TIMEOUT_MARGIN_S = 1.5


@dataclass
class RemoteAgent(Agent):
    """One bot container."""

    url: str
    seat: int = 0
    label: str = "bot"
    #: Counts of fallbacks, so a wedged container shows up as a number rather than a vibe.
    failures: int = 0
    _client: httpx.Client | None = field(default=None, repr=False)

    @property
    def name(self) -> str:
        return self.label

    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(base_url=self.url)
        return self._client

    def _fallback(self, legal: int, seed: int, why: str) -> int:
        self.failures += 1
        log.warning("bot %s at %s: %s — playing a random legal card", self.label, self.url, why)
        cards = card_list(legal)
        return cards[random.Random(seed).randrange(len(cards))]

    def select_trump(self, hand: int, is_forehand: bool) -> Contract | str:
        payload = {
            "hand": [format_card(c) for c in card_list(hand)],
            "is_forehand": is_forehand,
            "seat": self.seat,
        }
        try:
            response = self.client().post("/select_trump", json=payload, timeout=TIMEOUT_MARGIN_S)
            response.raise_for_status()
            action = response.json()["action"]
        except Exception as exc:  # noqa: BLE001 — any failure means fall back, by design
            self.failures += 1
            log.warning("bot %s trump selection failed (%s); shoving is not safe, picking", self.label, exc)
            # A shove would hand the decision to a partner who may also be down. Pick.
            from krass_jass.trump import select_trump as rule_based

            return rule_based(hand, is_forehand=False, cfg=self.cfg)

        if action == SHOVE:
            return SHOVE if is_forehand else Contract.HEARTS
        try:
            return Contract[str(action).upper()]
        except KeyError:
            self.failures += 1
            log.warning("bot %s returned unknown bid %r", self.label, action)
            from krass_jass.trump import select_trump as rule_based

            return rule_based(hand, is_forehand=False, cfg=self.cfg)

    def sidi_call(self, hand: int, auction: tuple, seat: int) -> str:
        payload = {
            "hand": [format_card(c) for c in card_list(hand)],
            "auction": [{"seat": s, "call": c} for s, c in auction],
            "seat": seat,
        }
        try:
            response = self.client().post("/sidi_call", json=payload, timeout=TIMEOUT_MARGIN_S)
            response.raise_for_status()
            return str(response.json()["call"])
        except Exception as exc:  # noqa: BLE001 — any failure means fall back, by design
            self.failures += 1
            log.warning("bot %s sidi call failed (%s); passing", self.label, exc)
            return "PASS"   # the engine re-validates; a pass is always legal

    def sidi_knock(self, hand: int, auction: tuple, seat: int) -> bool:
        payload = {
            "hand": [format_card(c) for c in card_list(hand)],
            "auction": [{"seat": s, "call": c} for s, c in auction],
            "seat": seat,
        }
        try:
            response = self.client().post("/sidi_knock", json=payload, timeout=TIMEOUT_MARGIN_S)
            response.raise_for_status()
            return bool(response.json()["knock"])
        except Exception as exc:  # noqa: BLE001 — a bot that cannot answer simply does not knock
            self.failures += 1
            log.warning("bot %s sidi knock failed (%s); not knocking", self.label, exc)
            return False

    def sidi_double(self, obs: Observation) -> bool:
        payload = {
            "hand": [format_card(c) for c in card_list(obs.hand)],
            "contract": obs.contract.name,
            "bid_value": obs.bid_value,
            "seat": obs.seat,
        }
        try:
            response = self.client().post("/sidi_double", json=payload, timeout=TIMEOUT_MARGIN_S)
            response.raise_for_status()
            return bool(response.json()["double"])
        except Exception as exc:  # noqa: BLE001
            self.failures += 1
            log.warning("bot %s sidi double failed (%s); not doubling", self.label, exc)
            return False

    def decide(self, obs: Observation) -> int:
        legal = obs.legal_moves
        payload = {
            "hand": [format_card(c) for c in card_list(obs.hand)],
            "legal_moves": [format_card(c) for c in card_list(legal)],
            "contract": obs.contract.name,
            "declarer_seat": obs.declarer_seat,
            "current_trick": [
                {"seat": (obs.trick_leader + i) % 4, "card": format_card(c)}
                for i, c in enumerate(obs.trick)
            ],
            "trick_leader": obs.trick_leader,
            "tricks_played": [
                {"leader": leader, "cards": [format_card(c) for c in cards]}
                for leader, cards in obs.tricks_played
            ],
            "scores": list(obs.scores),
            "seat": obs.seat,
            "time_budget_ms": obs.time_budget_ms,
            "decision_seed": obs.decision_seed,
            "mode": "sidi" if obs.auction else "schieber",
            "auction": [{"seat": s, "call": c} for s, c in obs.auction],
            "bid_value": obs.bid_value,
            "doubled": obs.doubled,
        }
        timeout = obs.time_budget_ms / 1000 + TIMEOUT_MARGIN_S
        try:
            response = self.client().post("/play_card", json=payload, timeout=timeout)
            response.raise_for_status()
            card = parse_card(response.json()["card"])
        except Exception as exc:  # noqa: BLE001
            return self._fallback(legal, obs.decision_seed, str(exc))

        if not legal & (1 << card):
            # Never trust a bot's move. The engine would reject it anyway; catching it here
            # keeps the game moving instead of raising into the turn loop.
            return self._fallback(legal, obs.decision_seed, f"illegal card {format_card(card)}")
        return card

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
