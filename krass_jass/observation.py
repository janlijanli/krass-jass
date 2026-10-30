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
    #: `(seat, points)` for **all four seats**, the value each called in the first trick —
    #: zero for a seat that called nothing. Empty while the calls are still coming in, or
    #: when Weis is off: silence is only a claim once the seat has had its turn to speak.
    #:
    #: A value is not a card and cannot become a void mask, which is why `known_cards` left
    #: it: "a four-card sequence somewhere" forbids no particular card. It is a predicate
    #: over whole hands and is tested where whole hands are made — see `rust/src/announce.rs`.
    weis_announced: tuple = ()
    #: `(seat, card)` pairs that the table has been *shown*. The winning Weis is turned face
    #: up to prove it, so those cards are public knowledge about a specific hand — and the
    #: search was dealing them to random seats in every imagined world. Only cards still
    #: unplayed appear here; once played they are public through `played` like any other.
    #:
    #: Stöck has no equivalent and deliberately contributes nothing: it is announced when the
    #: *second* of King and Queen is played, by which point both are already face up.
    known_cards: tuple = ()
    #: What a bot may spend on a move. 6 s: the shipped search costs ~1.3 s natively (median; p90
    #: 1.8 s) since the tree policy went on, and a CPU-capped container is slower again. The web
    #: client waits this plus a margin before playing a random card for a bot that has not answered.
    time_budget_ms: int = 6000
    decision_seed: int = 0
    round_index: int = 0
    #: Sidi Barrani only (empty / 0 / False in the Schieber). The auction is public: every call
    #: was said aloud, `(seat, "HEARTS 100" | "PASS" | "DOUBLE")` in order.
    auction: tuple = ()
    #: The standing bid the declarers must reach, and whether it was doubled.
    bid_value: int = 0
    doubled: bool = False

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
    def played_by(self) -> tuple[int, ...]:
        """Per seat, a mask of the cards it has already played this round.

        A Weis value is a statement about the nine cards a seat was *dealt*, so a world
        imagined in trick five has to be put back together before it can be tested against
        one. Derived from the public history like `played`, and never from a hand.
        """
        out = [0, 0, 0, 0]
        for leader, cards in self.tricks_played:
            for i, c in enumerate(cards):
                out[(leader + i) % 4] |= 1 << c
        for i, c in enumerate(self.trick):
            out[(self.trick_leader + i) % 4] |= 1 << c
        return tuple(out)

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
    weis_announced: tuple = (),
    known_cards: tuple = (),
    time_budget_ms: int = 6000,
    decision_seed: int = 0,
    round_index: int = 0,
    auction: tuple = (),
    bid_value: int = 0,
    doubled: bool = False,
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
        weis_announced=weis_announced,
        known_cards=known_cards,
        time_budget_ms=time_budget_ms,
        decision_seed=decision_seed,
        round_index=round_index,
        auction=auction,
        bid_value=bid_value,
        doubled=doubled,
    )
