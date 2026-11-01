"""Authoritative round state.

The object layer. It is *not* the rollout path — search runs on
:mod:`krass_jass.rollout`, which speaks only in ints. This class exists so the engine, the
tests and the eventual web service have one readable, validating implementation to agree
with.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cards import NUM_CARDS, bit, card_suit
from .legal import legal_moves
from .rules import Contract, RulesConfig
from .scoring import NUM_TEAMS, TRICKS_PER_ROUND, RoundScore, score_round, team_of
from .tables import CARD_VALUES, STRENGTH
from .weis import score_stoeck, score_weis
from .trick import NUM_SEATS, trick_winner


class IllegalMove(ValueError):
    """A move that is not in ``legal_moves``. The engine is authoritative — this is raised
    for bot and client moves alike, and is never swallowed."""


@dataclass
class RoundState:
    #: The contract the round is counted in. For an ordinary round, also the one it is played in.
    contract: Contract
    hands: list[int]
    cfg: RulesConfig = field(default_factory=RulesConfig)
    leader: int = 0
    #: The Coiffeur's extra rows (`krass_jass/schedule.py`): the contract each of the nine tricks
    #: is *played* in — who must follow, who may trump, who takes it. `None`: `contract` for all.
    #: A 3×3's later blocks are `None` until their leader names them (`set_block`).
    schedule: list | None = None
    #: Tutti: every trick is `None` until it is led, and then the trump of the suit led. The first
    #: card also fixes `contract`, what the round is counted in.
    tutti: bool = False

    trick: list[int] = field(default_factory=list)       #: cards played this trick, in order
    tricks_played: list[tuple[int, tuple[int, ...]]] = field(default_factory=list)
    #: (winning seat, card points) per trick, in the order they were taken. Needed for the
    #: Stöck-Weis-Stich ruling, which counts tricks one at a time.
    trick_results: list[tuple[int, int]] = field(default_factory=list)
    trick_points: list[int] = field(default_factory=lambda: [0, 0])
    tricks_won: list[int] = field(default_factory=lambda: [0, 0])
    last_trick_winner: int = -1

    def __post_init__(self) -> None:
        if self.schedule is not None:
            self.schedule = list(self.schedule)
        self._values = CARD_VALUES[self.contract]
        self.trump = self.contract.trump_suit
        #: Weis is announced from the *dealt* hand during the first trick, so the round has
        #: to remember it — by scoring time the hands are empty.
        self.initial_hands = list(self.hands)
        self.forehand = self.leader

    # -- queries ------------------------------------------------------------

    @property
    def to_play(self) -> int:
        return (self.leader + len(self.trick)) % NUM_SEATS

    @property
    def led_suit(self) -> int:
        return card_suit(self.trick[0]) if self.trick else -1

    @property
    def trick_contract(self) -> Contract:
        """The contract the current trick is played in."""
        if self.schedule is None:
            return self.contract
        named = self.schedule[min(len(self.tricks_played), TRICKS_PER_ROUND - 1)]
        if named is None and self.tutti and self.trick:
            return Contract(card_suit(self.trick[0]))
        return self.contract if named is None else named

    @property
    def block_pending(self) -> bool:
        """A 3×3 is between blocks and the next one has not been named: nobody may play."""
        if self.schedule is None or self.tutti or self.trick or self.done:
            return False
        return self.schedule[len(self.tricks_played)] is None

    def block_options(self) -> list[Contract]:
        from .schedule import block_options

        return block_options(self.schedule, len(self.tricks_played)) if self.block_pending else []

    def set_block(self, contract: Contract) -> None:
        """The leader names the 3×3's next block."""
        if contract not in self.block_options():
            raise IllegalMove(f"{contract!r} cannot be named for this block")
        at = len(self.tricks_played)
        for t in range(at, at + 3):
            self.schedule[t] = contract

    @property
    def trick_trump(self) -> int:
        return self.trick_contract.trump_suit

    @property
    def done(self) -> bool:
        return len(self.tricks_played) == TRICKS_PER_ROUND

    def best_trump_strength(self) -> int:
        """Strength of the highest trump in the current trick, or -1. Only meaningful
        while a non-trump lead is in progress, which is the only place it is consulted."""
        trump = self.trick_trump
        if trump < 0 or not self.trick:
            return -1
        strength = STRENGTH[self.trick_contract]
        best = -1
        for c in self.trick:
            if card_suit(c) == trump:
                s = strength[trump][c] - 100
                if s > best:
                    best = s
        return best

    def legal_moves(self, seat: int | None = None) -> int:
        seat = self.to_play if seat is None else seat
        return legal_moves(
            self.hands[seat],
            self.trick_trump,
            self.led_suit,
            self.best_trump_strength(),
            strict_undertrump=self.cfg.strict_undertrump,
            puur_exempt=self.cfg.puur_exempt_trump_lead,
        )

    # -- mutation -----------------------------------------------------------

    def play(self, card: int) -> None:
        """Play one card for the seat on turn. Raises :class:`IllegalMove` — never trust a
        caller, whether it is a bot or the browser."""
        if not 0 <= card < NUM_CARDS:
            raise IllegalMove(f"card index {card} out of range")
        seat = self.to_play
        if self.block_pending:
            raise IllegalMove("the next 3×3 block has not been named")
        if not self.legal_moves(seat) & bit(card):
            raise IllegalMove(f"card {card} is not legal for seat {seat}")

        if self.tutti and not self.trick:
            self._name_by_lead(card)
        self.hands[seat] ^= bit(card)
        self.trick.append(card)
        if len(self.trick) == NUM_SEATS:
            self._resolve_trick()

    def _name_by_lead(self, card: int) -> None:
        """Tutti: the suit led is this trick's trump; the first trick's is the round's count."""
        led = Contract(card_suit(card))
        self.schedule[len(self.tricks_played)] = led
        if not self.tricks_played:
            self.contract = led
            self._values = CARD_VALUES[led]
            self.trump = led.trump_suit

    def _resolve_trick(self) -> None:
        strength = STRENGTH[self.trick_contract][card_suit(self.trick[0])]
        winner = trick_winner(self.trick, self.leader, strength)
        team = team_of(winner)
        points = sum(self._values[c] for c in self.trick)
        self.trick_points[team] += points
        self.tricks_won[team] += 1
        self.trick_results.append((winner, points))
        self.tricks_played.append((self.leader, tuple(self.trick)))
        self.last_trick_winner = winner
        self.leader = winner
        self.trick = []

    # -- result -------------------------------------------------------------

    def score(
        self,
        weis: tuple[int, int] | None = None,
        stoeck: tuple[int, int] | None = None,
    ) -> RoundScore:
        """Final score. Weis and Stöck are derived from the dealt hands unless overridden."""
        if not self.done:
            raise RuntimeError("round is not finished")
        if weis is None:
            weis, _ = score_weis(self.initial_hands, self.trump, self.cfg, self.forehand)
        if stoeck is None:
            stoeck = score_stoeck(self.initial_hands, self.trump, self.cfg)
        return score_round(
            trick_points=tuple(self.trick_points),
            tricks_won=tuple(self.tricks_won),
            last_trick_winner=self.last_trick_winner,
            contract=self.contract,
            cfg=self.cfg,
            weis=weis,
            stoeck=stoeck,
        )
