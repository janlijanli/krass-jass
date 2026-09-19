"""The first Sidi bidder speaks the owner's bidding language (`docs/sidi-plan.md`)."""

import random

import pytest

from krass_jass import sidi_bidding as sb
from krass_jass.auction import Auction
from krass_jass.cards import parse_card
from krass_jass.rules import SIDI, Contract


def hand(*codes):
    return sum(1 << parse_card(c) for c in codes)


# Hearts is suit 1. J = Bauer, 9 = Nell.
@pytest.mark.parametrize(
    "cards, value",
    [
        (("HJ", "H7"), 50),                     # Bauer + one
        (("HJ", "H9", "H6"), 70),               # Bauer and Nell: odd, the Bauer is announced
        (("HJ", "HA", "HK", "H8"), 90),         # Bauer + three
        (("H9", "HA"), 40),                     # Nell + one
        (("H9", "HA", "HK", "H8"), 80),         # Nell + three
        (("HA", "HK", "HQ"), None),             # neither: nothing
        (("HA", "HK", "HQ", "HT", "H8"), 100),  # neither, but long
    ],
)
def test_trump_values_say_what_is_held(cards, value):
    assert sb.trump_value(hand(*cards, "SA", "C6"), 1) == value


def test_obenabe_counts_aces():
    h = hand("HA", "SA", "CA", "D7", "S8", "C9", "H6", "D8", "S7")
    assert sb.opening(h) == (Contract.OBENABE, 60)


@pytest.mark.parametrize(
    "cards, partner_bid, expect",
    [
        (("H9", "H7"), 50, True),        # Nell + one on a Bauer bid
        (("H9",), 50, False),            # a bare Nell is not enough
        (("HA", "H8", "H7"), 50, True),  # three without the Nell
        (("HA", "H8"), 50, False),
        (("HJ", "H7"), 60, True),        # a Nell bid is supported only with the Bauer
        (("HA", "HK", "H8"), 60, False),
    ],
)
def test_support_rules(cards, partner_bid, expect):
    assert (sb.support(hand(*cards), Contract.HEARTS, partner_bid) is not None) == expect


def test_supporting_obenabe_adds_ten_per_ace():
    assert sb.support(hand("SA", "CA", "D7"), Contract.OBENABE, 40) == 60


@pytest.mark.parametrize("seed", range(200))
def test_every_call_is_legal(seed):
    from krass_jass.deal import deal

    hands = deal(seed, 0)
    auction = Auction(opener=seed % 4, cfg=SIDI)
    while not auction.done:
        seat = auction.to_act
        public = tuple((s, str(c)) for s, c in auction.calls)
        call = sb.choose_call(hands[seat], public, seat, SIDI)
        assert call in {str(c) for c in auction.legal_calls(seat)}, call
        auction.call(seat, call)


def test_partners_do_not_bid_each_other_up():
    """A Nell bid, the Bauer supports it: the Nell holder has said its piece and passes."""
    nell = hand("S9", "SA", "SK", "S8", "H7", "H8", "D7", "D8", "C7")
    call = sb.choose_call(nell, ((1, "SPADES 80"), (2, "PASS"), (3, "SPADES 130"), (0, "PASS")), 1, SIDI)
    assert call == "PASS"


def test_auctions_between_bots_end_without_escalating():
    from krass_jass.deal import deal

    for seed in range(300):
        hands = deal(seed, 0)
        auction = Auction(opener=seed % 4, cfg=SIDI)
        while not auction.done:
            seat = auction.to_act
            public = tuple((s, str(c)) for s, c in auction.calls)
            auction.call(seat, sb.choose_call(hands[seat], public, seat, SIDI))
        # every bid after a seat's first names a different contract or answers the other side
        for seat in range(4):
            mine = [c.contract for s, c in auction.calls if s == seat and c.kind == "bid"]
            assert len(mine) == len(set(mine)) or len(mine) <= 2, (seed, auction.calls)


@pytest.mark.parametrize(
    "cards, partner_bid, floor, expect",
    [
        (("H9", "H7"), 50, 50, 60),             # the Nell on a Bauer bid: even
        (("H9", "H7", "H8", "HA"), 50, 50, 80), # Nell + three: what it would have opened with
        (("HJ", "H7"), 60, 60, 70),             # the Bauer on a Nell bid: odd
        (("HJ", "H7"), 60, 80, 90),             # over a higher standing bid, still odd
    ],
)
def test_a_support_names_the_supporters_own_card(cards, partner_bid, floor, expect):
    assert sb.support(hand(*cards), Contract.HEARTS, partner_bid, floor) == expect
