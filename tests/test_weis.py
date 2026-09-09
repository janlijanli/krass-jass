"""Weis is the largest source of rule bugs in the project, so it gets the reference
treatment: brute-force agreement plus the specific cases the sources argue about."""

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from krass_jass.cards import parse_hand as H
from krass_jass.rules import EVAL, HOUSE, RulesConfig
from krass_jass.weis import (
    STOECK_POINTS,
    WeisKind,
    find_weis,
    score_stoeck,
    score_weis,
)
from tests import reference
from tests.helpers import to_codes

LARGE = HOUSE.variant(weis_large=True)


def total(hand: str, cfg: RulesConfig = HOUSE) -> int:
    return sum(m.points for m in find_weis(H(hand), cfg))


# --- the values -------------------------------------------------------------


def test_sequence_points():
    assert total("DA DK DQ S6 S7 H8 H9 CA CK") == 20      # three
    assert total("DA DK DQ DJ S7 H8 H9 CA CK") == 50      # four
    assert total("DA DK DQ DJ DT S7 H8 CA CK") == 100     # five
    assert total("DA DK DQ DJ DT D9 S7 CA CK") == 100     # small Weis caps 5+ at 100


def test_large_weis_scores_long_sequences_separately():
    assert total("DA DK DQ DJ DT D9 S7 CA CK", LARGE) == 150
    assert total("DA DK DQ DJ DT D9 D8 D7 D6", LARGE) == 300


def test_four_of_a_kind_points():
    assert total("DJ HJ SJ CJ DA S7 H8 C9 D6") == 200
    assert total("D9 H9 S9 C9 DA S7 H8 CK D6") == 150
    assert total("DA HA SA CA D7 S7 H8 CK D6") == 100


def test_four_nines_is_a_flag():
    hand = "D9 H9 S9 C9 DA S7 H8 CK D6"
    assert total(hand, HOUSE.variant(weis_four_nines=False)) == 0


def test_eights_sevens_and_sixes_are_not_a_weis():
    assert total("D8 H8 S8 C8 DA S7 H9 CK D6") == 0


def test_sequence_order_ignores_the_trump_order():
    """J-10-9 of trumps is a sequence; J-9-A is not. Sequence order is always A K Q J 10 9
    8 7 6 whatever the contract."""
    assert total("HJ HT H9 DA S7 C8 CK D6 D7") == 20
    assert total("HJ H9 HA DK S7 C8 CQ D6 D7") == 0


# --- the interesting case ---------------------------------------------------


def test_small_weis_may_announce_a_shorter_sequence_to_free_a_card():
    """A-K-Q-J of diamonds plus four jacks. Under small Weis the DJ can only count once,
    and 4 jacks + A-K-Q (220) beats 4 jacks alone (200) and the sequence alone (50)."""
    hand = "DJ HJ SJ CJ DA DK DQ S7 S6"
    melds = find_weis(H(hand), HOUSE)
    assert sum(m.points for m in melds) == 220
    assert sorted(m.kind.value for m in melds) == ["four", "sequence"]


def test_large_weis_lets_the_jack_count_twice():
    assert total("DJ HJ SJ CJ DA DK DQ S7 S6", LARGE) == 250


def test_equal_scoring_ties_pick_the_stronger_meld():
    """A run of nine and a run of five both score 100 under small Weis — but only the run
    of nine beats an opponent's run of six, so it is the one to announce."""
    melds = find_weis(H("DA DK DQ DJ DT D9 D8 D7 D6"), HOUSE)
    assert len(melds) == 1
    assert melds[0].points == 100 and melds[0].length == 9


# --- who scores -------------------------------------------------------------


def test_best_weis_takes_all_and_the_other_team_scores_nothing():
    seat0 = "DJ HJ SJ CJ DA DK DQ S7 S6"   # four jacks + A-K-Q of diamonds
    seat1 = "HA HK CA CK ST S9 D8 DT H7"   # nothing
    seat2 = "SA SK SQ CT C9 C7 H8 D9 D7"   # A-K-Q of spades — partner of seat 0
    seat3 = "HQ HJ HT H9 H6 CQ CJ C8 C6"
    hands = [H(seat0), H(seat1), H(seat2), H(seat3)]
    assert sum(bin(h).count("1") for h in hands) == 36, "hands must be a real deal"

    points, winner = score_weis(hands, trump=1, cfg=HOUSE)
    assert winner == 0, "four jacks is the best Weis at the table"
    assert points[1] == 0, "the losing team scores none of its Weis"
    # the winning team scores everything its *both* seats hold
    expected = reference.best_weis_total(
        seat0.split(), large=False, four_nines=True
    ) + reference.best_weis_total(seat2.split(), large=False, four_nines=True)
    assert points[0] == expected


def test_ties_go_to_the_earlier_player():
    hand = "DA DK DQ S6 S7 H8 H9 CA C7"
    other = "HA HK HQ S8 S9 D6 D7 CK C8"
    points, winner = score_weis([H(hand), H(other), 0, 0], trump=2, cfg=HOUSE, forehand=1)
    assert winner == 1, "seat 1 leads, so its equal Weis wins the tie"
    points, winner = score_weis([H(hand), H(other), 0, 0], trump=2, cfg=HOUSE, forehand=0)
    assert winner == 0


def test_weis_disabled_scores_nothing():
    hands = [H("DJ HJ SJ CJ DA DK DQ S7 S6"), 0, 0, 0]
    assert score_weis(hands, trump=1, cfg=EVAL) == ((0, 0), -1)


# --- stoeck -----------------------------------------------------------------


def test_stoeck_is_king_and_queen_of_trumps():
    hands = [H("HK HQ DA DK DQ DJ DT D9 D8"), 0, 0, 0]
    assert score_stoeck(hands, trump=1, cfg=HOUSE) == (STOECK_POINTS, 0)
    assert score_stoeck(hands, trump=2, cfg=HOUSE) == (0, 0), "holds no spade K+Q"


def test_there_is_no_stoeck_in_a_no_trump_contract():
    hands = [H("HK HQ DA DK DQ DJ DT D9 D8"), 0, 0, 0]
    assert score_stoeck(hands, trump=-1, cfg=HOUSE) == (0, 0)


def test_stoeck_disabled():
    hands = [H("HK HQ DA DK DQ DJ DT D9 D8"), 0, 0, 0]
    assert score_stoeck(hands, trump=1, cfg=EVAL) == (0, 0)


# --- properties -------------------------------------------------------------


def random_hand(rng):
    deck = list(range(36))
    rng.shuffle(deck)
    return sum(1 << c for c in deck[:9])


@settings(max_examples=300, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**32 - 1), large=st.booleans())
def test_matches_brute_force_reference(seed, large):
    cfg = HOUSE.variant(weis_large=large)
    hand = random_hand(random.Random(seed))
    got = sum(m.points for m in find_weis(hand, cfg))
    want = reference.best_weis_total(to_codes(hand), large=large, four_nines=cfg.weis_four_nines)
    assert got == want


@settings(max_examples=300, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_small_weis_melds_are_disjoint_and_held(seed):
    hand = random_hand(random.Random(seed))
    union = 0
    for m in find_weis(hand, HOUSE):
        assert m.cards & hand == m.cards, "announced a card not in the hand"
        assert union & m.cards == 0, "the same card counted twice under small Weis"
        union |= m.cards


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_large_weis_never_scores_less_than_small(seed):
    hand = random_hand(random.Random(seed))
    assert sum(m.points for m in find_weis(hand, LARGE)) >= sum(
        m.points for m in find_weis(hand, HOUSE)
    )
