"""Translation between the engine's bitboards and the reference's strings."""

from __future__ import annotations

from krass_jass.cards import card_list, format_card, parse_card
from krass_jass.rules import Contract

CONTRACT_CODES = {
    Contract.DIAMONDS: "D",
    Contract.HEARTS: "H",
    Contract.SPADES: "S",
    Contract.CLUBS: "C",
    Contract.OBENABE: "OBENABE",
    Contract.UNDENUFE: "UNDENUFE",
}


def to_codes(mask: int) -> list[str]:
    return [format_card(c) for c in card_list(mask)]


def to_mask(codes) -> int:
    m = 0
    for c in codes:
        m |= 1 << parse_card(c)
    return m
