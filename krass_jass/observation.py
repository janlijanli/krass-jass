"""The information boundary.

**This is the security-critical function in the project.** A single `build_observation`
decides what any agent ever sees; if it is wrong, no amount of process isolation helps,
because each bot container simply receives the leaked data over HTTP instead of through a
function call (`PLAN.md` §1.1).

An observation contains the seat's own hand, engine-computed legal moves, and public
history. It does **not** contain another player's hand, the deck order, the game seed, or
the full state object. `tests/test_observation.py` fuzzes this and asserts that no card
identifier outside the seat's own hand and the public history appears anywhere in the
payload — if you change the shape of an observation, that test moves with it.

`decision_seed` is the one deliberate exception to "no seed", and it is what makes
bit-for-bit replay possible at all. It is derived per decision and reveals nothing hidden;
the raw game seed must never cross this boundary, because it determines the deal.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field

from .cards import card_list
from .rules import Contract
from .scoring import team_of


def derive_decision_seed(game_seed: int, game_id: str, seat: int, rnd: int, trick: int) -> int:
    """`HMAC(game_seed, game_id ‖ seat ‖ round ‖ trick)`, truncated to 64 bits.

    Not invertible, independent of any hidden card, and stable across replays.
    """
    msg = f"{game_id}|{seat}|{rnd}|{trick}".encode()
    key = game_seed.to_bytes(32, "big", signed=False)
    digest = hmac.new(key, msg, hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big")


@dataclass(frozen=True)
class Observation:
    """Everything one seat is allowed to know. Deliberately not a view onto the state."""

    seat: int
    hand: int                       #: own remaining cards, as a mask
    legal_moves: int                #: engine-computed and authoritative
    contract: Contract
    declarer_seat: int
    trick: tuple[int, ...]          #: cards played in the current trick, in order
    trick_leader: int
    tricks_played: tuple[tuple[int, tuple[int, ...]], ...] = ()
    scores: tuple[int, int] = (0, 0)
    #: Weis awarded this round, per team. Public: the table finished calling in the first
    #: trick and the result was announced. Stöck has no counterpart here — it stays private
    #: until the second honour is played, so it is not in an observation and not in the
    #: search's projection either.
    weis_points: tuple[int, int] = (0, 0)
    weis_announced: tuple = ()
    time_budget_ms: int = 1500
    decision_seed: int = 0
    round_index: int = 0

    @property
    def team(self) -> int:
        return team_of(self.seat)

    @property
    def forehand(self) -> int:
        """Seat that led the round — the one that had first call in the bidding.

        Derived rather than carried: it is the leader of the first trick, and before a card
        is played it is simply the current leader. A property, so the frozen-shape test in
        `test_observation.py` still guards the fields that cross the boundary.
        """
        if self.tricks_played:
            return self.tricks_played[0][0]
        return self.trick_leader

    @property
    def played(self) -> int:
        """Mask of every card visible on the table, this trick and previous ones."""
        seen = 0
        for _, cards in self.tricks_played:
            for c in cards:
                seen |= 1 << c
        for c in self.trick:
            seen |= 1 << c
        return seen

    @property
    def unseen(self) -> int:
        """Cards this seat cannot see: the other three hands, combined."""
        from .cards import FULL_DECK

        return FULL_DECK & ~self.hand & ~self.played

    def cards(self) -> list[int]:
        return card_list(self.hand)


def build_observation(
    state,
    seat: int | None = None,
    *,
    declarer_seat: int = 0,
    scores: tuple[int, int] = (0, 0),
    weis_points: tuple[int, int] = (0, 0),
    time_budget_ms: int = 1500,
    decision_seed: int = 0,
    round_index: int = 0,
) -> Observation:
    """The only way an agent learns anything. Add fields here and nowhere else.

    Everything below comes from the seat's own hand or from cards already face-up on the
    table. Nothing reads `state.hands[other]`, and nothing may be added that does.
    """
    seat = state.to_play if seat is None else seat
    return Observation(
        seat=seat,
        hand=state.hands[seat],
        legal_moves=state.legal_moves(seat),
        contract=state.contract,
        declarer_seat=declarer_seat,
        trick=tuple(state.trick),
        trick_leader=state.leader,
        tricks_played=tuple(state.tricks_played),
        scores=scores,
        weis_points=weis_points,
        time_budget_ms=time_budget_ms,
        decision_seed=decision_seed,
        round_index=round_index,
    )
