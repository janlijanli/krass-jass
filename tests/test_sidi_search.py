"""Sidi Barrani in the search: the hand is played for the bid, and the auction is read.

`rust/src/objective.rs` and `rust/src/sidi_read.rs`; the reasoning is in their doc comments.
"""

from __future__ import annotations

import itertools
import random

import pytest

from krass_jass import native
from krass_jass.agent import DmctsAgent
from krass_jass.cards import parse_card
from krass_jass.game import Game, Phase
from krass_jass.objective import sidi_reward
from krass_jass.rules import SIDI_EVAL

pytestmark = pytest.mark.skipif(not native.AVAILABLE, reason="Rust core not built")
core = native._core
needs_sidi = pytest.mark.skipif(
    not hasattr(core, "rs_sidi_auction_loglik"), reason="Rust core predates the Sidi search"
)


@needs_sidi
@pytest.mark.parametrize(
    "ours, bid, team, declarers, doubled",
    list(itertools.product((0, 40, 99, 100, 101, 152, 157), (40, 100, 150, 157, 257), (0, 1), (0, 1), (False, True))),
)
def test_both_implementations_agree(ours, bid, team, declarers, doubled):
    theirs = 157 - ours
    mine = sidi_reward(ours, theirs, team, bid, declarers, doubled)
    rust = core.rs_reward(ours, theirs, team, (0, 0), (0, 0), 0, 1, bid, declarers, doubled)
    assert mine == pytest.approx(rust, abs=1e-12)


def test_the_threshold_is_a_cliff_both_ways():
    short, made = sidi_reward(99, 58, 0, 100, 0, False), sidi_reward(100, 57, 0, 100, 0, False)
    assert made - short > 0.25
    # The defenders' view of the same hands is the mirror image.
    assert sidi_reward(58, 99, 1, 100, 0, False) == pytest.approx(1 - short)


def hand(*codes):
    return sum(1 << parse_card(c) for c in codes)


@needs_sidi
def test_an_opening_is_read_as_the_bauer_and_its_count():
    # Seat 1 opened hearts 70: the Bauer and two more.
    auction = [(1, 1, 70)]
    worlds = {
        "truth": hand("HJ", "HA", "H6"),
        "one short": hand("HJ", "HA"),
        "no Bauer": hand("H9", "HA", "H6"),
    }
    ll = {k: core.rs_sidi_auction_loglik([0, h, 0, 0], auction, 0) for k, h in worlds.items()}
    assert ll["truth"] == 0.0
    assert ll["no Bauer"] < ll["one short"] < ll["truth"]


@needs_sidi
@pytest.mark.parametrize("settings", [{}, {"sidi_alpha": 0.0}, {"sidi_objective": False}])
def test_the_agent_plays_legal_cards_in_a_sidi_hand(settings):
    agent = DmctsAgent(determinizations=4, iterations=30, cfg=SIDI_EVAL, belief_pool=64, **settings)
    game = Game(cfg=SIDI_EVAL, seed=7)
    while game.phase is not Phase.ROUND_OVER:
        seat = game.to_act
        if game.phase is Phase.BIDDING:
            game.bid(seat, agent.sidi_call(game.hand_of(seat), game.public_auction(), seat))
        elif game.phase is Phase.DOUBLING:
            game.double(seat, agent.sidi_double(game.observation(seat)))
        else:
            obs = game.observation(seat)
            card = agent.decide(obs)
            assert obs.legal_moves >> card & 1
            game.play(seat, card)


# --- doubling on an estimate ---------------------------------------------------

needs_estimate = pytest.mark.skipif(
    not hasattr(core, "rs_sidi_make_probability"), reason="Rust core predates the estimate"
)


@needs_estimate
def test_the_estimate_reads_the_hand_and_the_auction():
    from krass_jass.rules import Contract

    strong = hand("HJ", "H9", "HA", "HK", "DA", "SA", "CA", "D6", "S6")
    weak = hand("D6", "D7", "D8", "S6", "S7", "S8", "C6", "C7", "C8")
    auction = [(1, int(Contract.HEARTS), 120)]
    p_strong, _ = native.sidi_make_probability(0, strong, [], 1, Contract.HEARTS, 1, 120, auction, 300)
    p_weak, _ = native.sidi_make_probability(0, weak, [], 1, Contract.HEARTS, 1, 120, auction, 300)
    assert p_strong < 0.2 < p_weak


@needs_estimate
def test_the_agent_doubles_a_bid_its_hand_makes_hopeless():
    agent = DmctsAgent(determinizations=4, iterations=30, cfg=SIDI_EVAL)
    strong = hand("HJ", "H9", "HA", "HK", "DA", "SA", "CA", "D6", "S6")
    weak = hand("D6", "D7", "D8", "S6", "S7", "S8", "C6", "C7", "C8")
    auction = ((1, "HEARTS 120"),)
    assert agent.sidi_call(strong, auction, 2) == "DOUBLE"
    assert agent.sidi_call(weak, auction, 2) != "DOUBLE"
    # Never the partner's bid.
    assert agent.sidi_call(strong, ((0, "HEARTS 120"),), 2) != "DOUBLE"
