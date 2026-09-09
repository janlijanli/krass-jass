"""Legal-move generation — the highest-risk function in the codebase.

Three things here are unlike Bridge/Skat/Hearts and are the usual source of bugs. They are
not mistakes; do not "fix" them:

1. **You may always trump, even when you can follow suit.**
2. **Strict undertrumping.** Once someone has trumped a non-trump lead, a lower trump is
   illegal — unless your hand is nothing but trumps.
3. **The Puur is exempt from a trump lead.** If your only trump is the trump Jack you need
   not play it.

Everything is masks in, mask out. No objects, no allocation — the rollout kernel calls this
several hundred thousand times per move.
"""

from __future__ import annotations

from .cards import NUM_RANKS, SUIT_MASK
from .tables import PUUR_MASK, TRUMP_HIGHER


def legal_moves(
    hand: int,
    trump: int,
    led: int,
    best_trump_strength: int,
    *,
    strict_undertrump: bool = True,
    puur_exempt: bool = True,
) -> int:
    """Mask of legal cards.

    :param hand: the player's remaining cards.
    :param trump: trump suit index, or ``-1`` for Obenabe/Undenufe.
    :param led: led suit index, or ``-1`` when leading the trick.
    :param best_trump_strength: strength of the highest trump already played *in this
        trick*, or ``-1`` if none. Only consulted for the undertrump rule.

    Never returns 0 for a non-empty hand.
    """
    if led < 0:  # leading — anything goes
        return hand

    if trump < 0:  # Obenabe / Undenufe: ordinary follow-suit, no trumping
        follow = hand & SUIT_MASK[led]
        return follow or hand

    trumps = hand & SUIT_MASK[trump]

    if led == trump:
        # Trump led: follow with a trump if you have one. The Puur exemption applies only
        # when it is your *sole* trump.
        if not trumps:
            return hand
        if puur_exempt and trumps == PUUR_MASK[trump]:
            return hand
        return trumps

    # Non-trump led. Following is optional — trumping is always allowed — but the trumps
    # you may choose from are constrained once someone has already trumped.
    if strict_undertrump and best_trump_strength >= 0 and trumps != hand:
        allowed_trumps = trumps & (TRUMP_HIGHER[best_trump_strength] << (trump * NUM_RANKS))
    else:
        # No one has trumped yet, the rule is off, or the hand is nothing but trumps —
        # in all three cases every trump held is playable.
        allowed_trumps = trumps

    follow = hand & SUIT_MASK[led]
    if follow:
        return follow | allowed_trumps
    return (hand & ~SUIT_MASK[trump]) | allowed_trumps
