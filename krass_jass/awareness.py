"""What a player at the table can work out from the cards face up.

Everything here is *public*: the arguments are the played cards plus the asking seat's own
hand, and nothing else is reachable from them. That is the point — this feeds the display,
and a display that knew more than a player at the table would be a cheat rather than a help.

Two things a human does automatically and a screen otherwise hides:

1. **Who is currently taking the trick.** Three cards are down, one of them is an ace worth
   eleven, and whether that is a gift or a loss depends on a comparison the player has to
   redo every time a card lands.
2. **Where the trump is.** A player counts trump and remembers who could not follow one.
   The inference has a Jass-specific sharp edge: a discard on a trump lead proves only that
   their trump holding is a subset of the Puur, because the Puur may always be held back —
   so it is a *hard* void only once the Puur itself is accounted for. That is `voids.py`'s
   rule, read from the asking seat's side of the table.
"""

from __future__ import annotations

from .cards import SUIT_MASK
from .rules import Contract, RulesConfig
from .tables import CARD_VALUES, PUUR_MASK, STRENGTH
from .trick import NUM_SEATS
from .voids import infer_forbidden

#: A seat's trump holding, as far as the cards face up prove it.
NONE = "none"     #: provably holds no trump at all
PUUR = "puur"     #: provably holds no trump except possibly the Puur


def trick_taker(cards, leader: int, contract: Contract) -> int | None:
    """Seat the cards on the table currently go to, with the trick still in progress.

    The same comparison `RoundState` makes when the fourth card lands; strengths are banded
    (trump above led suit above the rest) so one maximum decides it at any length.
    """
    if not cards:
        return None
    strength = STRENGTH[contract][cards[0] // 9]
    best = 0
    for i in range(1, len(cards)):
        if strength[cards[i]] > strength[cards[best]]:
            best = i
    return (leader + best) % NUM_SEATS


def trick_points(cards, contract: Contract) -> int:
    """Card points lying on the table."""
    values = CARD_VALUES[contract]
    return sum(values[c] for c in cards)


def trump_read(
    tricks_played,
    current_trick,
    current_leader: int,
    seat: int,
    hand: int,
    contract: Contract,
    cfg: RulesConfig,
) -> dict:
    """How much trump is still out, and who is proven not to hold any.

    `out` counts the trumps in the other three hands: every trump is either face up, in
    `hand`, or in somebody else's — so subtracting the first two is exact, not an estimate.
    """
    # `is_trump`, not truthiness: Contract.DIAMONDS is 0 and therefore falsy.
    if not contract.is_trump:
        return {"out": None, "voids": [None] * NUM_SEATS}

    trump = contract.trump_suit
    seen = hand
    for _, cards in tricks_played:
        for card in cards:
            seen |= 1 << card
    for card in current_trick:
        seen |= 1 << card

    mask = SUIT_MASK[trump]
    unseen = mask & ~seen
    forbidden = infer_forbidden(tricks_played, current_trick, current_leader, contract, cfg)

    voids: list[str | None] = []
    for other in range(NUM_SEATS):
        if other == seat:
            voids.append(None)
            continue
        # What is left after removing every trump that is face up, in my own hand, or ruled
        # out for them by the play. Nothing about *their* hand is read here.
        possible = unseen & ~forbidden[other]
        if possible == 0:
            voids.append(NONE)
        elif possible & ~PUUR_MASK[trump] == 0:
            # The Puur is the one trump a player may hold back on a trump lead, so it is the
            # one card the discard did not rule out. Once it has been played this branch
            # cannot be reached: the card is in `seen`, and the read hardens to NONE.
            voids.append(PUUR)
        else:
            voids.append(None)

    return {"out": bin(unseen).count("1"), "voids": voids}
