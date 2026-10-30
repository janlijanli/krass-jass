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


@pytest.mark.parametrize("seed", range(300))
def test_rust_bids_exactly_as_python_does(seed):
    """The browser build bids with `rust/src/sidi_bidding.rs`; a human playing offline must meet
    the same partner as one playing against the server."""
    from krass_jass import native
    from krass_jass.deal import deal

    core = native._core
    if not hasattr(core, "rs_sidi_choose_call"):
        pytest.skip("Rust core predates the Sidi bidder")
    hands = deal(seed, 0)
    auction = Auction(opener=seed % 4, cfg=SIDI)
    rng = random.Random(seed)
    while not auction.done:
        seat = auction.to_act
        public = tuple((s, str(c)) for s, c in auction.calls)
        for double in (None, True, False):
            py = sb.choose_call(hands[seat], public, seat, SIDI, double=double)
            rs = core.rs_sidi_choose_call(hands[seat], list(public), seat, double)
            assert py == rs, (seed, public, seat, double)
        # Walk on sometimes by a random legal call, so the comparison sees auctions the
        # bidder itself would never produce.
        legal = [str(c) for c in auction.legal_calls(seat)]
        choice = sb.choose_call(hands[seat], public, seat, SIDI) if rng.random() < 0.6 else rng.choice(legal[:20])
        auction.call(seat, choice)


def test_a_bot_never_takes_the_opponents_suit_off_them():
    """Owner, 2026-09-19: bidding the opponents' own suit higher only buys them out of a
    contract they would likely have lost — with their trumps, wait for the knock."""
    strong_hearts = hand("HJ", "H9", "HA", "HK", "H8", "SA", "C6", "D6", "S6")
    call = sb.choose_call(strong_hearts, ((1, "HEARTS 60"),), 2, SIDI, double=False)
    assert not call.startswith("HEARTS")
    assert sb.choose_call(strong_hearts, ((1, "HEARTS 60"),), 2, SIDI, double=True) == "DOUBLE"
    # Its partner's hearts it still supports.
    assert sb.choose_call(strong_hearts, ((0, "HEARTS 60"),), 2, SIDI).startswith("HEARTS")


def test_a_bot_knocks_on_a_hopeless_bid_out_of_turn_and_not_on_its_partner():
    """Knocking out of turn is off by default — it lost 7.61 points a hand (measurements §5v).
    With it on, a seat knocks only on an opponent's bid it cannot beat with one of its own."""
    from krass_jass.agent import DmctsAgent

    shipped = DmctsAgent(determinizations=4, iterations=30, cfg=SIDI)
    agent = DmctsAgent(determinizations=4, iterations=30, cfg=SIDI, sidi_knock_anytime=True)
    strong = hand("HJ", "H9", "HA", "HK", "DA", "SA", "CA", "D6", "S6")
    assert shipped.sidi_knock(strong, ((1, "HEARTS 120"),), 2) is False  # the shipped default
    assert agent.sidi_knock(strong, ((1, "HEARTS 120"),), 2) is True
    assert agent.sidi_knock(strong, ((0, "HEARTS 120"),), 2) is False    # its partner's bid
    assert agent.sidi_knock(strong, (), 2) is False                      # nothing bid yet
    # Holding the opponents' own suit: their bid is hopeless, but this hand can outbid it at 110,
    # which is the cheaper answer — a double would end the auction and give that bid away.
    spades = hand("SJ", "S9", "SA", "SK", "S8", "HA", "DA", "C6", "D6")
    assert agent.sidi_knock(spades, ((1, "SPADES 70"),), 2) is False
    loud = DmctsAgent(determinizations=4, iterations=30, cfg=SIDI, sidi_knock_anytime=True,
                      sidi_knock_holds_bid=False)
    assert loud.sidi_knock(spades, ((1, "SPADES 70"),), 2) is True
