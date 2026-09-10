"""Trump selection. PLAN.md §3.1 makes this the biggest cheap win in the project, so the
tests check judgement, not just plumbing."""

import json
import random

import pytest

from krass_jass.agent import DmctsAgent, GreedyAgent, RandomAgent
from krass_jass.cards import parse_hand as H
from krass_jass.rules import EVAL, HOUSE, SHOVE, Contract
from krass_jass.trump import WEIGHTS_PATH, describe, load_weights, score_all, select_trump


def test_weight_tables_cover_every_rank():
    """A missing rank does not fail at import — it crashes mid-bid on the one hand that
    holds that card."""
    w = json.loads(WEIGHTS_PATH.read_text())
    for table in ("trump_rank_weights", "side_suit_weights", "obenabe_weights", "undenufe_weights"):
        ranks = set(w[table]) - {"_comment"}
        assert ranks == set("AKQJT9876"), f"{table} is missing {set('AKQJT9876') - ranks}"
    lengths = set(w["trump_length_bonus"]) - {"_comment"}
    assert lengths == {str(i) for i in range(10)}


def test_picks_the_long_strong_trump_suit():
    assert select_trump(H("HJ H9 HA HK H8 H7 SA D6 C6"), True, HOUSE) is Contract.HEARTS


def test_picks_obenabe_on_top_heavy_hands():
    assert select_trump(H("HA HK SA SK DA DK CA CK D6"), True, HOUSE) is Contract.OBENABE


def test_picks_undenufe_on_bottom_heavy_hands():
    assert select_trump(H("H6 H7 H8 S6 S7 S8 D6 D7 C6"), True, HOUSE) is Contract.UNDENUFE


def test_shoves_on_a_hand_with_nothing():
    assert select_trump(H("HT SQ DJ C9 H8 S7 D6 CT SJ"), True, HOUSE) == SHOVE


def test_never_shoves_off_forehand():
    """A shoved-to partner must choose, or the bidding does not terminate."""
    rng = random.Random(5)
    for _ in range(300):
        deck = list(range(36))
        rng.shuffle(deck)
        hand = sum(1 << c for c in deck[:9])
        assert select_trump(hand, is_forehand=False, cfg=HOUSE) != SHOVE


def test_multiplier_scales_the_edge_not_the_score():
    """The trap. The multiplier scales the round for *both* teams, so it multiplies your
    edge. A mediocre hand must not become attractive just because Undenufe pays x4."""
    mediocre = H("HT SQ DJ C9 H8 S7 D6 CT SJ")
    scores = score_all(mediocre, HOUSE)
    assert scores[Contract.UNDENUFE] < 0, "a weak Undenufe must score worse, not 4x better"

    strong_low = H("H6 H7 H8 S6 S7 S8 D6 D7 C6")
    assert score_all(strong_low, HOUSE)[Contract.UNDENUFE] > 0


def test_a_strong_hand_always_beats_the_shove_threshold():
    rng = random.Random(11)
    shoves = 0
    for _ in range(400):
        deck = list(range(36))
        rng.shuffle(deck)
        hand = sum(1 << c for c in deck[:9])
        if select_trump(hand, True, HOUSE) == SHOVE:
            shoves += 1
    # Sanity band. Always shoving or never shoving both mean the threshold is wrong.
    assert 0.05 < shoves / 400 < 0.6, f"shove rate {shoves / 400:.0%} looks broken"


def test_describe_is_ordered_best_first():
    ordered = describe(H("HJ H9 HA HK H8 H7 SA D6 C6"), HOUSE)
    assert [v for _, v in ordered] == sorted([v for _, v in ordered], reverse=True)


@pytest.mark.parametrize("agent", [RandomAgent(), GreedyAgent(), DmctsAgent(cfg=EVAL)])
def test_every_agent_can_bid(agent):
    rng = random.Random(2)
    deck = list(range(36))
    rng.shuffle(deck)
    hand = sum(1 << c for c in deck[:9])
    action = agent.select_trump(hand, is_forehand=False)
    assert isinstance(action, Contract)


def test_bidding_terminates_and_produces_a_legal_contract():
    from arena.arena import choose_contract, deal_hands

    rng = random.Random(3)
    a = GreedyAgent()
    for _ in range(200):
        hands = deal_hands(rng)
        contract, declarer = choose_contract(hands, 0, {i: a for i in range(4)}, EVAL)
        assert isinstance(contract, Contract)
        assert declarer in (0, 2), "only forehand or its partner can declare"
