"""Game orchestration: bidding, Weis, nine tricks, scoring, repeat to the target.

Sits above `RoundState`, which owns one round. This owns the sequence of rounds, the phase
machine, and the event log the web layer projects to clients.

It holds no agents and no transport. The caller drives it — asking whose turn it is, feeding
in a decision, reading the events that resulted. That keeps the same object usable from the
web service, the arena and a test without any of them knowing about each other.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from .cards import card_list, format_card
from .events import EventLog, EventType
from .observation import build_observation, derive_decision_seed
from .rules import HOUSE, SHOVE, Contract, RulesConfig
from .scoring import NUM_TEAMS, team_of
from .state import IllegalMove, RoundState
from .trick import NUM_SEATS
from .weis import find_weis, score_stoeck, score_weis


class Phase(str, Enum):
    BIDDING = "bidding"
    PLAYING = "playing"
    ROUND_OVER = "round_over"
    GAME_OVER = "game_over"


@dataclass
class Game:
    cfg: RulesConfig = HOUSE
    seed: int = 0
    game_id: str = "game"
    dealer: int = 0

    scores: list[int] = field(default_factory=lambda: [0, 0])
    round_index: int = 0
    phase: Phase = Phase.BIDDING
    log: EventLog = field(default_factory=EventLog)

    round: RoundState | None = None
    contract: Contract | None = None
    declarer: int = 0
    forehand: int = 0
    shoved: bool = False
    _dealt: list[int] = field(default_factory=lambda: [0, 0, 0, 0])

    def __post_init__(self) -> None:
        self.log.emit(
            EventType.GAME_STARTED,
            {"game_id": self.game_id, "target_score": self.cfg.target_score},
        )
        self.start_round()

    # -- round lifecycle ----------------------------------------------------

    def start_round(self) -> None:
        """Deal and open the bidding.

        The deal RNG is derived from the game seed and the round index, so a game replays
        bit-for-bit — including which cards each seat got.
        """
        rng = random.Random(f"deal:{self.seed}:{self.round_index}")
        deck = list(range(36))
        rng.shuffle(deck)
        hands = [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(NUM_SEATS)]

        self._dealt = list(hands)
        self.forehand = (self.dealer + 1) % NUM_SEATS
        self.declarer = self.forehand
        self.shoved = False
        self.contract = None
        self.round = None
        self.phase = Phase.BIDDING

        self.log.emit(
            EventType.ROUND_STARTED,
            {"round": self.round_index, "dealer": self.dealer, "forehand": self.forehand},
        )
        for seat in range(NUM_SEATS):
            self.log.emit(
                EventType.HAND_DEALT,
                {"seat": seat, "cards": [format_card(c) for c in card_list(hands[seat])]},
                private_to=seat,
            )

    # -- whose turn ---------------------------------------------------------

    @property
    def to_act(self) -> int | None:
        if self.phase is Phase.BIDDING:
            return self.declarer
        if self.phase is Phase.PLAYING and self.round is not None:
            return self.round.to_play
        return None

    def hand_of(self, seat: int) -> int:
        """The seat's current cards. Callers must not hand this to another seat."""
        if self.round is not None:
            return self.round.hands[seat]
        return self._dealt[seat]

    def decision_seed(self, seat: int) -> int:
        trick = len(self.round.tricks_played) if self.round else 0
        return derive_decision_seed(self.seed, self.game_id, seat, self.round_index, trick)

    def observation(self, seat: int, time_budget_ms: int = 1500):
        if self.round is None:
            raise RuntimeError("no round in progress; bidding is not finished")
        return build_observation(
            self.round,
            seat,
            declarer_seat=self.declarer,
            scores=(self.scores[0], self.scores[1]),
            time_budget_ms=time_budget_ms,
            decision_seed=self.decision_seed(seat),
            round_index=self.round_index,
        )

    # -- actions ------------------------------------------------------------

    @staticmethod
    def parse_action(action: Contract | str) -> Contract | str:
        """Accept a Contract, a contract *name*, or SHOVE.

        Clients speak names over the wire, and `Contract` is an IntEnum, so `Contract("HEARTS")`
        raises. Parsing here keeps that detail out of the transport layer and gives one place
        to reject nonsense from a client.
        """
        if isinstance(action, Contract):
            return action
        text = str(action).strip().upper()
        if text == SHOVE:
            return SHOVE
        try:
            return Contract[text]
        except KeyError:
            raise IllegalMove(f"unknown bid {action!r}") from None

    def bid(self, seat: int, action: Contract | str) -> None:
        """Choose a contract, or shove. Only the seat on turn may act."""
        action = self.parse_action(action)
        if self.phase is not Phase.BIDDING:
            raise IllegalMove("not bidding")
        if seat != self.declarer:
            raise IllegalMove(f"seat {seat} is not on turn to bid")

        if action == SHOVE:
            if self.shoved:
                raise IllegalMove("already shoved once")
            if seat != self.forehand and not self.cfg.allow_zurueckschieben:
                raise IllegalMove("only forehand may shove")
            self.shoved = True
            self.declarer = (seat + 2) % NUM_SEATS
            self.log.emit(EventType.BID, {"seat": seat, "action": SHOVE})
            return

        contract = action
        self.contract = contract
        self.log.emit(EventType.BID, {"seat": seat, "action": contract.name})
        self._begin_play()

    def _begin_play(self) -> None:
        assert self.contract is not None
        self.round = RoundState(
            contract=self.contract,
            hands=list(self._dealt),
            cfg=self.cfg,
            leader=self.forehand,
        )
        self.log.emit(
            EventType.CONTRACT_SET,
            {
                "contract": self.contract.name,
                "declarer": self.declarer,
                "multiplier": self.cfg.multiplier(self.contract),
                "leader": self.forehand,
            },
        )
        self._declare_weis()
        self.phase = Phase.PLAYING

    def _declare_weis(self) -> None:
        """Automatic announcement.

        `docs/webapp-plan.md` §6 flags this as a real choice: announcing reveals your
        holding and an experienced player occasionally declines. Automatic is the default
        because it is what a player wants almost always; making it manual is a UI change
        here, not an engine change.
        """
        if not (self.cfg.weis_enabled or self.cfg.stoeck_enabled):
            return
        # `is not None`, not truthiness: Contract.DIAMONDS is 0 and therefore falsy, which
        # would silently turn every diamonds contract into a no-trump one here — no Stöck,
        # and the wrong tie-break for Weis.
        trump = self.contract.trump_suit if self.contract is not None else -1
        points, winner = score_weis(self._dealt, trump, self.cfg, self.forehand)
        stoeck = score_stoeck(self._dealt, trump, self.cfg)

        if winner >= 0:
            for seat in range(NUM_SEATS):
                if team_of(seat) != team_of(winner):
                    continue
                for meld in find_weis(self._dealt[seat], self.cfg, trump):
                    self.log.emit(
                        EventType.WEIS_DECLARED,
                        {
                            "seat": seat,
                            "kind": meld.kind.value,
                            "points": meld.points,
                            "cards": [format_card(c) for c in card_list(meld.cards)],
                        },
                    )
        self._weis = points
        self._stoeck = stoeck

    def play(self, seat: int, card: int) -> None:
        """Play one card. The engine re-validates — a client's move is never trusted."""
        if self.phase is not Phase.PLAYING or self.round is None:
            raise IllegalMove("not playing")
        if seat != self.round.to_play:
            raise IllegalMove(f"seat {seat} is not on turn")

        tricks_before = len(self.round.tricks_played)
        self.round.play(card)   # raises IllegalMove on anything not legal
        self.log.emit(EventType.CARD_PLAYED, {"seat": seat, "card": format_card(card)})

        if len(self.round.tricks_played) > tricks_before:
            leader, cards = self.round.tricks_played[-1]
            self.log.emit(
                EventType.TRICK_WON,
                {
                    "seat": self.round.last_trick_winner,
                    "trick": len(self.round.tricks_played),
                    "cards": [format_card(c) for c in cards],
                },
            )
        if self.round.done:
            self._score_round()

    def _score_round(self) -> None:
        assert self.round is not None
        score = self.round.score(weis=self._weis, stoeck=self._stoeck)
        totals = score.total
        for t in range(NUM_TEAMS):
            self.scores[t] += totals[t]

        self.log.emit(
            EventType.ROUND_SCORED,
            {
                "round": self.round_index,
                "trick_points": list(score.trick_points),
                "last_trick": list(score.last_trick),
                "match": list(score.match),
                "weis": list(score.weis),
                "stoeck": list(score.stoeck),
                "multiplier": score.multiplier,
                "round_total": list(totals),
                "scores": list(self.scores),
            },
        )

        target = self.cfg.target_score
        if target is not None and max(self.scores) >= target:
            winner = 0 if self.scores[0] > self.scores[1] else 1
            self.phase = Phase.GAME_OVER
            self.log.emit(
                EventType.GAME_OVER, {"winner": winner, "scores": list(self.scores)}
            )
        else:
            self.phase = Phase.ROUND_OVER

    def next_round(self) -> None:
        if self.phase is not Phase.ROUND_OVER:
            raise RuntimeError(f"cannot start a round from {self.phase}")
        self.round_index += 1
        self.dealer = (self.dealer + 1) % NUM_SEATS
        self.start_round()

    _weis: tuple[int, int] = (0, 0)
    _stoeck: tuple[int, int] = (0, 0)
