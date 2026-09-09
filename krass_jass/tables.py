"""Precomputed lookup tables.

The engine does no rule *reasoning* in its hot paths — it indexes into these. Everything
here is derived once at import from :mod:`krass_jass.cards` and the value/order tables in
``docs/rules-config.md``, and everything is a plain tuple of ints so the rollout kernel can
stay free of Python objects (see ``docs/plan-review.md`` §1 on why that matters).
"""

from __future__ import annotations

from .cards import (
    NUM_CARDS,
    NUM_RANKS,
    NUM_SUITS,
    RANK_6,
    RANK_7,
    RANK_8,
    RANK_9,
    RANK_A,
    RANK_J,
    RANK_K,
    RANK_Q,
    RANK_T,
    card_rank,
    card_suit,
)
from .rules import Contract

# --- card values, per rank -------------------------------------------------

_VAL_PLAIN = (11, 4, 3, 2, 10, 0, 0, 0, 0)          # A K Q J 10 9 8 7 6
_VAL_TRUMP = (11, 4, 3, 20, 10, 14, 0, 0, 0)        # Puur 20, Näll 14
_VAL_OBENABE = (11, 4, 3, 2, 10, 0, 8, 0, 0)        # 8s pay 8
_VAL_UNDENUFE = (0, 4, 3, 2, 10, 0, 8, 0, 11)       # values invert with the order: 6=11, A=0

# --- strength, per rank (higher wins) --------------------------------------

_STR_PLAIN = tuple(NUM_RANKS - 1 - r for r in range(NUM_RANKS))        # A high
_STR_UNDENUFE = tuple(range(NUM_RANKS))                                # 6 high
#: J > 9 > A > K > Q > 10 > 8 > 7 > 6
_STR_TRUMP = tuple(
    {RANK_J: 8, RANK_9: 7, RANK_A: 6, RANK_K: 5, RANK_Q: 4, RANK_T: 3, RANK_8: 2, RANK_7: 1, RANK_6: 0}[r]
    for r in range(NUM_RANKS)
)

#: ``TRUMP_HIGHER[s]`` — 9-bit mask of trump *ranks* strictly stronger than trump strength
#: ``s``. Shift by ``trump * 9`` to get a card mask. This is what makes the undertrump rule
#: a lookup rather than a comparison loop.
TRUMP_HIGHER: tuple[int, ...] = tuple(
    sum(1 << r for r in range(NUM_RANKS) if _STR_TRUMP[r] > s) for s in range(NUM_RANKS)
)

#: Mask of the Puur, per trump suit.
PUUR_MASK: tuple[int, ...] = tuple(1 << (s * NUM_RANKS + RANK_J) for s in range(NUM_SUITS))

#: Mask of King+Queen of trumps (Stöck), per trump suit.
STOECK_MASK: tuple[int, ...] = tuple(
    (1 << (s * NUM_RANKS + RANK_K)) | (1 << (s * NUM_RANKS + RANK_Q)) for s in range(NUM_SUITS)
)


def _values_for(contract: Contract) -> tuple[int, ...]:
    """Point value of every card index, for one contract."""
    if contract is Contract.OBENABE:
        per_rank = [_VAL_OBENABE] * NUM_SUITS
    elif contract is Contract.UNDENUFE:
        per_rank = [_VAL_UNDENUFE] * NUM_SUITS
    else:
        trump = contract.trump_suit
        per_rank = [_VAL_TRUMP if s == trump else _VAL_PLAIN for s in range(NUM_SUITS)]
    return tuple(per_rank[card_suit(c)][card_rank(c)] for c in range(NUM_CARDS))


def _strength_for(contract: Contract, led: int) -> tuple[int, ...]:
    """Trick strength of every card index, given the led suit.

    Banded so a single ``max`` decides the trick: trump 100+, led suit 10+, anything else
    0. A card that is neither trump nor of the led suit can never win, and the leader's own
    card is always in a scoring band, so the max is never ambiguous.
    """
    trump = contract.trump_suit
    base = _STR_UNDENUFE if contract is Contract.UNDENUFE else _STR_PLAIN
    out = []
    for c in range(NUM_CARDS):
        s, r = card_suit(c), card_rank(c)
        if s == trump:
            out.append(100 + _STR_TRUMP[r])
        elif s == led:
            out.append(10 + base[r])
        else:
            out.append(0)
    return tuple(out)


#: ``CARD_VALUES[contract]`` -> 36 point values.
CARD_VALUES: dict[Contract, tuple[int, ...]] = {c: _values_for(c) for c in Contract}

#: ``STRENGTH[contract][led_suit]`` -> 36 strengths.
STRENGTH: dict[Contract, tuple[tuple[int, ...], ...]] = {
    c: tuple(_strength_for(c, led) for led in range(NUM_SUITS)) for c in Contract
}

#: Points in the whole deck, per contract. Every contract totals 152 — which is exactly why
#: a "sums to 157" test cannot catch a mis-implemented Undenufe.
DECK_POINTS: dict[Contract, int] = {c: sum(v) for c, v in CARD_VALUES.items()}
