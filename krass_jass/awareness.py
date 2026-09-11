"""What a player at the table can work out from the cards face up.

Everything here is *public*: the arguments are the played cards plus the asking seat's own
hand, and nothing else is reachable from them. That is the point — this feeds the display,
and a display that knew more than a player at the table would be a cheat rather than a help.

One thing a human does automatically and a screen otherwise hides: **who is currently taking
the trick**. Four cards land at angles, the strength order depends on the contract, and
whether the ace just played is a gift or a loss is a comparison the player would otherwise
redo every time a card lands.

That is the whole list, and what is left off it is the point of the module. Not who is out of
trump: the play proves it and the bots search with it (`voids.py`), but working out who can
still trump you is the read that makes the game. Not how much trump is left, not the points
on the table, not the points taken so far. Counting is what a player is at the table to do,
and a screen that counts for them is playing it for them.
"""

from __future__ import annotations

from .rules import Contract
from .tables import STRENGTH
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
