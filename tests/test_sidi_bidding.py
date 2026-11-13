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


# -- the second style: «Gspürsch mi, füehlsch mi» ------------------------------------------------

FEEL_TABLES = [
    ("count", "count", "count", "count"),
    ("feel", "feel", "feel", "feel"),
    ("feel", "count", "feel", "count"),
    ("count", "feel", "count", "feel"),
]


def _auction(hands, opener, styles):
    auction = Auction(opener=opener, cfg=SIDI)
    while not auction.done:
        seat = auction.to_act
        public = tuple((s, str(c)) for s, c in auction.calls)
        call = sb.choose_call(hands[seat], public, seat, SIDI, style=styles[seat])
        assert call in {str(c) for c in auction.legal_calls(seat)}, (call, public)
        auction.call(seat, call)
    return auction


def test_feeling_the_way_opens_low_and_is_raised_a_step_at_a_time():
    """The owner's brief (2026-11-12): not a count by height, but several rounds to find each
    other — open gently, low bids, never straight to the maximum."""
    opener = hand("HJ", "H9", "H7", "D8", "S8", "C8", "D7", "S7", "C7")
    assert sb.choose_call(opener, (), 0, SIDI, style="feel") == "HEARTS 40"
    assert sb.choose_call(opener, (), 0, SIDI, style="count") == "HEARTS 70"
    # The partner holds three hearts to the ace and a side ace: "it fits", one step up.
    partner = hand("HA", "HK", "HQ", "SA", "D6", "C6", "D9", "C9", "S6")
    said = ((0, "HEARTS 40"), (1, "PASS"))
    assert sb.choose_call(partner, said, 2, SIDI, style="feel") == "HEARTS 50"
    # Back at the opener: strength 3 was all it had, and that is said. It passes.
    said += ((2, "HEARTS 50"), (3, "PASS"))
    assert sb.choose_call(opener, said, 0, SIDI, style="feel") == "PASS"


def test_a_new_contract_says_not_yours_but_here():
    # No heart to speak of, but the spade Bauer and Nell fourth.
    mine = hand("SJ", "S9", "SK", "S8", "H6", "D8", "C8", "D7", "C7")
    assert sb.choose_call(mine, ((0, "HEARTS 40"), (1, "PASS")), 2, SIDI, style="feel") == "SPADES 50"


def test_a_jump_of_twenty_says_much_stronger():
    # Bauer, Nell, ace and a fourth trump with a side ace: strength 6, two over an opening.
    strong = hand("SJ", "S9", "SA", "S7", "DA", "H8", "C8", "H7", "C7")
    assert sb.choose_call(strong, (), 0, SIDI, style="feel") == "SPADES 50"
    calls = [(0, sb.Call.parse("SPADES 50"))]
    w = sb.feel_weights()
    assert sb.feel_shown(calls, 0) == {Contract.SPADES: w["open"] + w["jump"]}
    # Over a standing 50 the two jumps are 70 and 80: the Bauer takes the odd one.
    assert sb.choose_call(strong, ((3, "HEARTS 50"),), 0, SIDI, double=False, style="feel") == "SPADES 70"
    no_bauer = hand("S9", "SA", "SK", "S8", "S7", "DA", "HA", "C8", "C7")
    assert sb.choose_call(no_bauer, ((3, "HEARTS 50"),), 0, SIDI, double=False, style="feel") == "SPADES 70"
    assert sb.choose_call(no_bauer, ((3, "HEARTS 60"),), 0, SIDI, double=False, style="feel") == "SPADES 80"
    assert sb.choose_call(strong, ((3, "HEARTS 60"),), 0, SIDI, double=False, style="feel") == "SPADES 90"


@pytest.mark.parametrize("styles", FEEL_TABLES)
def test_every_call_is_legal_in_every_table_of_styles(styles):
    from krass_jass.deal import deal

    for seed in range(150):
        _auction(deal(seed, 0), seed % 4, styles)


def test_feeling_the_way_takes_more_rounds_and_ends_lower():
    from statistics import fmean

    from krass_jass.deal import deal

    rounds, heights = {}, {}
    for style in ("count", "feel"):
        spoken, high = [], []
        for seed in range(400):
            auction = _auction(deal(seed, 0), seed % 4, (style,) * 4)
            if auction.high is None:
                continue
            side = auction.high[0] % 2
            spoken.append(sum(1 for s, c in auction.calls if c.kind == "bid" and s % 2 == side))
            high.append(auction.high[2])
        rounds[style], heights[style] = fmean(spoken), fmean(high)
    assert rounds["feel"] > rounds["count"] and heights["feel"] < heights["count"], (rounds, heights)


def test_a_seat_never_bids_past_what_it_has_shown_it_holds():
    """What stops two partners bidding each other up: every bid spends a point of strength."""
    from krass_jass.deal import deal

    for seed in range(300):
        hands = deal(seed, 0)
        auction = _auction(hands, seed % 4, ("feel",) * 4)
        calls = list(auction.calls)
        for seat in range(4):
            for contract, said in sb.feel_shown(calls, seat).items():
                assert said <= sb.feel_strength(hands[seat], contract), (seed, seat, calls)


@pytest.mark.parametrize("seed", range(200))
def test_rust_feels_its_way_exactly_as_python_does(seed):
    """Both styles, and tables where the two teams speak different ones: the offline build must
    seat the same partner and the same opponents as the server."""
    from krass_jass import native
    from krass_jass.deal import deal

    core = native._core
    hands = deal(seed, 0)
    styles = FEEL_TABLES[1 + seed % 3]
    auction = Auction(opener=seed % 4, cfg=SIDI)
    rng = random.Random(seed)
    while not auction.done:
        seat = auction.to_act
        public = tuple((s, str(c)) for s, c in auction.calls)
        for style in sb.STYLES:
            for double in (None, True, False):
                py = sb.choose_call(hands[seat], public, seat, SIDI, double=double, style=style)
                rs = core.rs_sidi_choose_call(
                    hands[seat], list(public), seat, double, sb.STYLES.index(style)
                )
                assert py == rs, (seed, public, seat, double, style)
        legal = [str(c) for c in auction.legal_calls(seat)]
        own = sb.choose_call(hands[seat], public, seat, SIDI, style=styles[seat])
        auction.call(seat, own if rng.random() < 0.6 else rng.choice(legal[:20]))


def test_a_bid_is_read_in_its_bidders_style():
    """`rust/src/sidi_read.rs`: the same forty is two different claims."""
    from krass_jass import native

    core = native._core
    bauer_nell = hand("HJ", "H9", "H7")          # felt: enough. Counted: 40 denies the Bauer.
    nell_one = hand("H9", "H7")                  # counted: exactly this. Felt: too little.
    auction = [(1, int(Contract.HEARTS), 40)]

    def ll(h, styles):
        return core.rs_sidi_auction_loglik([0, h, 0, 0], auction, 0, styles)

    feel, count = [0, 1, 0, 1], None
    assert ll(bauer_nell, feel) == 0 and ll(bauer_nell, count) < 0
    assert ll(nell_one, count) == 0 and ll(nell_one, feel) < 0
    # The other team's style does not touch this seat's bid.
    assert ll(bauer_nell, [1, 0, 1, 0]) == ll(bauer_nell, count)


def test_the_styles_are_public_and_reach_every_seat():
    from krass_jass.game import Game, Phase

    styles = ("feel", "count", "feel", "count")
    game = Game(cfg=SIDI.variant(sidi_bid_styles=styles), seed=11, game_id="styles")
    assert game.bid_styles == styles
    assert game.log.all()[0].payload["bid_styles"] == list(styles)
    while game.phase is Phase.BIDDING:
        seat = game.to_act
        game.bid(seat, sb.choose_call(
            game.hand_of(seat), game.public_auction(), seat, game.cfg, double=False,
            style=styles[seat],
        ))
    if game.round is not None and game.phase is not Phase.ROUND_OVER:
        assert game.observation(game.to_act).bid_styles == styles
    # The default says nothing in the log: every seat counts.
    assert "bid_styles" not in Game(cfg=SIDI, seed=11, game_id="plain").log.all()[0].payload
