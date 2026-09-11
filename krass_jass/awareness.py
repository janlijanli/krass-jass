"""What a player at the table can work out from the cards face up.

Everything here is *public*: the arguments are the played cards plus the asking seat's own
hand, and nothing else is reachable from them. That is the point — this feeds the display,
and a display that knew more than a player at the table would be a cheat rather than a help.

Two things a human does automatically and a screen otherwise hides:

1. **Who is currently taking the trick.** Three cards are down, one of them is an ace worth
   eleven, and whether that is a gift or a loss depends on a comparison the player has to
   redo every time a card lands.
2. **How much trump is left.** Every trump is either face up, in your own hand, or in
   somebody else's, so the count is exact arithmetic rather than a read.

Deliberately *not* here: which seat is out of trump. The play proves it — that is what
`voids.py` infers, and the bots search with it — but working out who can still trump you is
the read that makes the game, and a screen that hands it over is playing the game for you.
The bots know; they do not say.
"""

from __future__ import annotations

from .cards import SUIT_MASK
from .rules import Contract
from .tables import CARD_VALUES, STRENGTH
from .trick import NUM_SEATS


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


def trumps_out(tricks_played, current_trick, hand: int, contract: Contract) -> int | None:
    """Trumps in the other three hands.

    Every trump is either face up, in `hand`, or in somebody else's, so subtracting the first
    two is exact — not an estimate, and not a read on anybody's cards.
    """
    # `is_trump`, not truthiness: Contract.DIAMONDS is 0 and therefore falsy.
    if not contract.is_trump:
        return None

    seen = hand
    for _, cards in tricks_played:
        for card in cards:
            seen |= 1 << card
    for card in current_trick:
        seen |= 1 << card

    return bin(SUIT_MASK[contract.trump_suit] & ~seen).count("1")
