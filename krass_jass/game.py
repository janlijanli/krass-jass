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
from .tables import STOECK_MASK
from .weis import STOECK_POINTS, best_weis, find_weis, score_stoeck, score_weis


class Phase(str, Enum):
    BIDDING = "bidding"
    WEIS = "weis"
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
        self.weis_summary = []
        self.stoeck_seats = []
        self.weis_choices = {}
        self.weis_offers = {}
        self._stoeck_holders = set()

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
        if self.phase is Phase.WEIS:
            pending = [s for s in sorted(self.weis_offers) if s not in self.weis_choices]
            return pending[0] if pending else None
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
        if self.cfg.weis_enabled and self.cfg.weis_manual:
            trump = self.contract.trump_suit if self.contract is not None else -1
            self.weis_offers = {
                seat: sum(m.points for m in find_weis(self._dealt[seat], self.cfg, trump))
                for seat in range(NUM_SEATS)
            }
            self.weis_offers = {s: p for s, p in self.weis_offers.items() if p}
            if self.weis_offers:
                self.phase = Phase.WEIS
                return
        self._declare_weis()
        self.phase = Phase.PLAYING

    def _declare_weis(self) -> None:
        """Automatic announcement, in the two stages the real game uses.

        At the table everyone calls the *value* of their best Weis; only the team holding
        the best one then shows the actual cards. That staging is not decoration — it is
        what keeps a losing team's holding secret. Emitting cards for every seat would leak
        three hands at the top of every round.

        `docs/webapp-plan.md` §6 flags automatic-versus-manual as a real choice: announcing
        reveals your holding and an experienced player occasionally declines. Automatic is
        the default because it is what a player wants nearly always, and making it manual is
        a UI change here rather than an engine one.
        """
        # `is not None`, not truthiness: Contract.DIAMONDS is 0 and therefore falsy, which
        # would silently turn every diamonds contract into a no-trump one here — no Stöck,
        # and the wrong tie-break for Weis.
        trump = self.contract.trump_suit if self.contract is not None else -1

        self.weis_summary = []
        if self.cfg.weis_enabled:
            # A declined Weis is not merely hidden — it is not in the contest at all, so it
            # cannot win the comparison for its team either.
            declined = {s for s, keep in self.weis_choices.items() if not keep}
            hands = [0 if seat in declined else h for seat, h in enumerate(self._dealt)]
            points, winner = score_weis(hands, trump, self.cfg, self.forehand)
            per_seat = {
                seat: find_weis(hands[seat], self.cfg, trump) for seat in range(NUM_SEATS)
            }

            # Stage one: everyone calls a value. Public, and carries no cards.
            for seat in range(NUM_SEATS):
                total = sum(m.points for m in per_seat[seat])
                if total:
                    self.log.emit(
                        EventType.WEIS_ANNOUNCED,
                        {"seat": seat, "points": total, "melds": len(per_seat[seat])},
                    )
                    self.weis_summary.append(
                        {
                            "seat": seat,
                            "points": total,
                            "cards": None,
                            "winner": False,
                            "best": False,
                        }
                    )

            # Stage two: only the winning team shows what it holds.
            if winner >= 0:
                for seat in range(NUM_SEATS):
                    if team_of(seat) != team_of(winner):
                        continue
                    for meld in per_seat[seat]:
                        self.log.emit(
                            EventType.WEIS_DECLARED,
                            {
                                "seat": seat,
                                "kind": meld.kind.value,
                                "points": meld.points,
                                "cards": [format_card(c) for c in card_list(meld.cards)],
                            },
                        )
                self.log.emit(
                    EventType.WEIS_RESOLVED,
                    {"seat": winner, "team": team_of(winner), "points": list(points)},
                )
                # The winning *team* scores all of its Weis, but only the single best one
                # is shown — it is what has to be proved. Everyone else's holding, partner
                # included, stays private.
                best_meld = best_weis(per_seat[winner], trump, self.cfg)
                for entry in self.weis_summary:
                    if team_of(entry["seat"]) == team_of(winner):
                        entry["winner"] = True
                    if entry["seat"] == winner and best_meld is not None:
                        entry["best"] = True
                        entry["cards"] = [format_card(c) for c in card_list(best_meld.cards)]
            self._weis = points
        else:
            self._weis = (0, 0)

        # Stöck is *held* now but announced later — when the second of King/Queen is
        # actually played (see `_check_stoeck`). Announcing it here would tell the table
        # who holds the trump King and Queen before a card is down.
        stoeck = score_stoeck(self._dealt, trump, self.cfg)
        if trump >= 0:
            mask = STOECK_MASK[trump]
            self._stoeck_holders = {
                seat for seat in range(NUM_SEATS) if self._dealt[seat] & mask == mask
            }
        self._stoeck = stoeck

    def choose_weis(self, seat: int, announce: bool) -> None:
        """Answer the announce-or-decline question for one seat (manual mode only)."""
        if self.phase is not Phase.WEIS:
            raise IllegalMove("not choosing Weis")
        if seat not in self.weis_offers:
            raise IllegalMove(f"seat {seat} has no Weis to announce")
        self.weis_choices[seat] = bool(announce)
        if set(self.weis_choices) >= set(self.weis_offers):
            self._declare_weis()
            self.phase = Phase.PLAYING

    def play(self, seat: int, card: int) -> None:
        """Play one card. The engine re-validates — a client's move is never trusted."""
        if self.phase is not Phase.PLAYING or self.round is None:
            raise IllegalMove("not playing")
        if seat != self.round.to_play:
            raise IllegalMove(f"seat {seat} is not on turn")

        tricks_before = len(self.round.tricks_played)
        self.round.play(card)   # raises IllegalMove on anything not legal
        self.log.emit(EventType.CARD_PLAYED, {"seat": seat, "card": format_card(card)})
        self._check_stoeck(seat, tricks_before)

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

    def _check_stoeck(self, seat: int, trick_index: int) -> None:
        """Announce Stöck at the moment the second of King/Queen of trumps goes down.

        That is when a player calls it at the table, and the timing is information: holding
        both is worth knowing, and revealing it early is a choice a real player would rather
        make themselves. Every card gets played over nine tricks, so a held Stöck is always
        eventually announced — the change is *when*, not whether it scores.
        """
        if seat not in self._stoeck_holders or self.contract is None:
            return
        trump = self.contract.trump_suit
        if trump < 0:
            return
        mask = STOECK_MASK[trump]
        # Both halves gone from the hand means the second one has just been played.
        if self.round is not None and self.round.hands[seat] & mask == 0:
            self._stoeck_holders.discard(seat)
            self.log.emit(
                EventType.STOECK,
                {"seat": seat, "points": STOECK_POINTS, "trick": trick_index},
            )
            self.stoeck_seats.append({"seat": seat, "points": STOECK_POINTS, "trick": trick_index})

    def _claim_sequence(self, score) -> list[tuple[int, int]]:
        """Points in the order they are claimed: **Stöck, Weis, Stich**.

        This only matters when both teams would cross the target in the same round — then
        whoever gets there first in this order wins, regardless of the final totals. Counting
        the whole round at once produces the right totals and can name the wrong winner.

        Tricks are counted one at a time in the order they were taken, with the last-trick
        bonus on the ninth and the match bonus after it. The multiplier scales each claim as
        it lands, exactly as it scales the round.
        """
        assert self.round is not None
        multiplier = score.multiplier
        parts: dict[str, list[tuple[int, int]]] = {"stoeck": [], "weis": [], "stich": []}

        for team in range(NUM_TEAMS):
            if score.stoeck[team]:
                parts["stoeck"].append((team, score.stoeck[team] * multiplier))
            if score.weis[team]:
                parts["weis"].append((team, score.weis[team] * multiplier))

        last = len(self.round.trick_results) - 1
        for index, (winner, points) in enumerate(self.round.trick_results):
            team = team_of(winner)
            if index == last:
                points += self.cfg.last_trick_bonus
            if points:
                parts["stich"].append((team, points * multiplier))
        for team in range(NUM_TEAMS):
            if score.match[team]:
                parts["stich"].append((team, score.match[team] * multiplier))

        sequence: list[tuple[int, int]] = []
        for key in self.cfg.claim_order:
            sequence.extend(parts.get(key, []))
        return sequence

    def _score_round(self) -> None:
        assert self.round is not None
        score = self.round.score(weis=self._weis, stoeck=self._stoeck)
        totals = score.total

        # Apply the round claim by claim, so that a simultaneous finish is decided by who
        # reaches the target first rather than by who ends up with more.
        target = self.cfg.target_score
        sequence = self._claim_sequence(score)

        claimed = [0, 0]
        for team, points in sequence:
            claimed[team] += points
        if claimed != list(totals):
            raise AssertionError(
                f"claim sequence {claimed} does not reproduce the round total {totals} — "
                "a claim was dropped or double-counted"
            )

        first_across = -1
        for team, points in sequence:
            self.scores[team] += points
            if target is not None and first_across < 0 and self.scores[team] >= target:
                first_across = team

        self.last_score = {
            "round": self.round_index,
            "contract": self.contract.name if self.contract is not None else None,
            "multiplier": score.multiplier,
            "trick_points": list(score.trick_points),
            "last_trick": list(score.last_trick),
            "match": list(score.match),
            "weis": list(score.weis),
            "stoeck": list(score.stoeck),
            "round_total": list(totals),
            "scores": list(self.scores),
        }
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

        if target is not None and max(self.scores) >= target:
            self.phase = Phase.GAME_OVER
            self.log.emit(
                EventType.GAME_OVER,
                {
                    "winner": first_across,
                    "scores": list(self.scores),
                    # Named so a close finish is explicable rather than surprising.
                    "decided_by": "claim_order" if first_across >= 0 else "score",
                    "claim_order": list(self.cfg.claim_order),
                },
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
    #: UI-ready projections, built where the facts already are rather than re-derived by
    #: the web layer from the event log.
    weis_summary: list = field(default_factory=list)
    stoeck_seats: list = field(default_factory=list)
    last_score: dict | None = None
    #: seat -> True/False once decided, in manual mode
    weis_choices: dict = field(default_factory=dict)
    #: seats holding K+Q of trumps that have not yet played the second of the two
    _stoeck_holders: set = field(default_factory=set)
    #: seat -> points on offer, for the seats that actually hold something
    weis_offers: dict = field(default_factory=dict)
