"""Trick resolution."""

from __future__ import annotations

NUM_SEATS = 4


def trick_winner(cards: list[int], leader: int, strength: tuple[int, ...]) -> int:
    """Seat that wins the trick.

    :param cards: the four card indices, in play order starting from ``leader``.
    :param strength: ``STRENGTH[contract][led_suit]`` from :mod:`krass_jass.tables`.
    """
    best_i, best_s = 0, strength[cards[0]]
    for i in range(1, len(cards)):
        s = strength[cards[i]]
        if s > best_s:
            best_i, best_s = i, s
    return (leader + best_i) % NUM_SEATS


def trick_points(cards: list[int], values: tuple[int, ...]) -> int:
    return sum(values[c] for c in cards)
