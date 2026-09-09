"""Bitboard card primitives.

A hand is a 36-bit integer. Card index is ``suit * 9 + rank``, so each suit is a
contiguous 9-bit field and ``SUIT_MASK[s]`` selects it.

Ranks are numbered *descending in plain (non-trump) order* — A=0 … 6=8 — so plain-order
comparison is ``rank_a < rank_b`` with no table. Trump and Undenufe orders are lookup
tables over these same indices (see :mod:`krass_jass.tables`), not separate encodings.

See ``docs/rules-config.md`` for the encoding contract this file implements.
"""

from __future__ import annotations

from typing import Iterator

# --- suits -----------------------------------------------------------------

DIAMONDS, HEARTS, SPADES, CLUBS = 0, 1, 2, 3
SUIT_CHARS = "DHSC"
SUIT_NAMES = ("DIAMONDS", "HEARTS", "SPADES", "CLUBS")
NUM_SUITS = 4

# --- ranks -----------------------------------------------------------------

RANK_A, RANK_K, RANK_Q, RANK_J, RANK_T, RANK_9, RANK_8, RANK_7, RANK_6 = range(9)
RANK_CHARS = "AKQJT9876"
NUM_RANKS = 9

NUM_CARDS = NUM_SUITS * NUM_RANKS  # 36
FULL_DECK = (1 << NUM_CARDS) - 1

SUIT_MASK: tuple[int, ...] = tuple(((1 << NUM_RANKS) - 1) << (NUM_RANKS * s) for s in range(NUM_SUITS))


def card(suit: int, rank: int) -> int:
    """Card *index* (0..35), not a mask."""
    return suit * NUM_RANKS + rank


def card_suit(c: int) -> int:
    return c // NUM_RANKS


def card_rank(c: int) -> int:
    return c % NUM_RANKS


def bit(c: int) -> int:
    """Single-card mask for card index ``c``."""
    return 1 << c


# --- text form -------------------------------------------------------------


def parse_card(text: str) -> int:
    """``"DJ"`` -> card index. Accepts ``"D10"`` and any case; ten is emitted as ``T``."""
    t = text.strip().upper()
    if len(t) == 3 and t[1:] == "10":
        t = t[0] + "T"
    if len(t) != 2:
        raise ValueError(f"bad card {text!r}")
    suit = SUIT_CHARS.find(t[0])
    rank = RANK_CHARS.find(t[1])
    if suit < 0 or rank < 0:
        raise ValueError(f"bad card {text!r}")
    return card(suit, rank)


def format_card(c: int) -> str:
    return SUIT_CHARS[card_suit(c)] + RANK_CHARS[card_rank(c)]


def parse_hand(cards: str | list[str]) -> int:
    """Space-separated string or list of codes -> 36-bit hand mask."""
    items = cards.split() if isinstance(cards, str) else cards
    hand = 0
    for item in items:
        b = bit(parse_card(item))
        if hand & b:
            raise ValueError(f"duplicate card {item!r}")
        hand |= b
    return hand


def format_hand(hand: int) -> str:
    return " ".join(format_card(c) for c in iter_cards(hand))


# --- mask helpers ----------------------------------------------------------


def iter_cards(hand: int) -> Iterator[int]:
    """Card indices in a mask, ascending."""
    while hand:
        low = hand & -hand
        yield low.bit_length() - 1
        hand ^= low


def card_list(hand: int) -> list[int]:
    return list(iter_cards(hand))


def count(hand: int) -> int:
    return hand.bit_count()


def nth_card(hand: int, n: int) -> int:
    """Index of the ``n``-th set bit (0-based, ascending). Used by the rollout kernel."""
    while n:
        hand &= hand - 1
        n -= 1
    return (hand & -hand).bit_length() - 1
