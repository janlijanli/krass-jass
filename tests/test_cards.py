from hypothesis import given
from hypothesis import strategies as st

from krass_jass.cards import (
    FULL_DECK,
    NUM_CARDS,
    SUIT_MASK,
    card,
    card_list,
    card_rank,
    card_suit,
    count,
    format_card,
    format_hand,
    nth_card,
    parse_card,
    parse_hand,
)


def test_encoding_round_trip():
    for c in range(NUM_CARDS):
        assert card(card_suit(c), card_rank(c)) == c
        assert parse_card(format_card(c)) == c


def test_parse_accepts_ten_both_ways_and_any_case():
    assert parse_card("D10") == parse_card("DT") == parse_card("dt")
    assert format_card(parse_card("D10")) == "DT"


def test_suits_are_contiguous_and_partition_the_deck():
    total = 0
    for m in SUIT_MASK:
        assert count(m) == 9
        assert total & m == 0
        total |= m
    assert total == FULL_DECK


def test_rejects_nonsense():
    for bad in ("", "X", "DX", "ZA", "DTT"):
        try:
            parse_card(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} should not parse")


def test_duplicate_card_in_hand_is_rejected():
    try:
        parse_hand("DA DA")
    except ValueError:
        return
    raise AssertionError("duplicate not rejected")


@given(st.integers(min_value=0, max_value=FULL_DECK))
def test_hand_text_round_trip(hand):
    assert parse_hand(format_hand(hand)) == hand
    assert count(hand) == len(card_list(hand))


@given(st.integers(min_value=1, max_value=FULL_DECK))
def test_nth_card_matches_card_list(hand):
    cards = card_list(hand)
    for i, c in enumerate(cards):
        assert nth_card(hand, i) == c
