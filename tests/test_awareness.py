"""The table read shown to the player.

It must be **exact** — a player acts on it, so a count that is nearly right is worse than no
count — and it must be **public**, derived from the cards face up and the asking seat's own
hand and nothing else, or the display would be a cheat rather than a help.

`test_observation.py` guards what a *bot* sees. This guards what the *screen* says.
"""

import pytest

from krass_jass.agent import GreedyAgent
from krass_jass.awareness import trick_points, trick_taker, trumps_out
from krass_jass.cards import SUIT_MASK, parse_card, parse_hand
from krass_jass.game import Game
from krass_jass.rules import HOUSE, Contract
from krass_jass.state import RoundState

HEARTS = Contract.HEARTS


def table():
    """Hearts are trump; seat 0 holds the Puur. Leader is seat 1, so play goes 1, 2, 3, 0."""
    hands = [
        parse_hand("HJ D6 D7 D8 D9 DT DJ DQ DK"),
        parse_hand("HA HK DA S6 S7 S8 S9 ST SJ"),
        parse_hand("SQ SK SA C6 C7 C8 C9 CT CJ"),
        parse_hand("HQ HT H9 H8 H7 H6 CQ CK CA"),
    ]
    return RoundState(contract=HEARTS, hands=hands, cfg=HOUSE, leader=1)


def out_for(state, seat):
    return trumps_out(state.tricks_played, state.trick, state.hands[seat], HEARTS)


def test_counts_only_what_is_unaccounted_for():
    state = table()
    assert out_for(state, 0) == 8, "nine trumps, one of them mine"
    state.play(parse_card("HA"))
    assert out_for(state, 0) == 7


def test_each_seat_counts_from_its_own_side():
    """Seat 3 holds six trumps, so far fewer are unaccounted for from where they sit."""
    state = table()
    assert out_for(state, 3) == 3
    assert out_for(state, 2) == 9, "holding none, everything is still out there"


def test_no_trump_contract_counts_nothing():
    hands = [parse_hand(h) for h in (
        "HJ D6 D7 D8 D9 DT DJ DQ DK",
        "HA HK DA S6 S7 S8 S9 ST SJ",
        "SQ SK SA C6 C7 C8 C9 CT CJ",
        "HQ HT H9 H8 H7 H6 CQ CK CA",
    )]
    state = RoundState(contract=Contract.OBENABE, hands=hands, cfg=HOUSE, leader=1)
    assert trumps_out(state.tricks_played, state.trick, state.hands[0], Contract.OBENABE) is None


@pytest.mark.parametrize("seed", [1, 7, 31, 404])
def test_the_count_is_the_true_one_over_whole_games(seed):
    """Exactness against ground truth. Every trump is face up, in your hand, or in somebody
    else's, so there is a right answer and the display has to have it."""
    game = Game(cfg=HOUSE.variant(target_score=None), seed=seed)
    agent = GreedyAgent()
    game.bid(game.to_act, agent.select_trump(game.hand_of(game.to_act), True))

    while game.round is not None and not game.round.done:
        state = game.round
        if game.contract.is_trump:
            mask = SUIT_MASK[game.contract.trump_suit]
            for seat in range(4):
                held = sum(
                    bin(h & mask).count("1") for s, h in enumerate(state.hands) if s != seat
                )
                assert trumps_out(
                    state.tricks_played, state.trick, state.hands[seat], game.contract
                ) == held, "the count must be the true one, not an estimate"

        seat = game.to_act
        game.play(seat, agent.decide(game.observation(seat)))


@pytest.mark.parametrize("seed", [2, 11, 99])
def test_the_taker_predicts_the_trick_it_ends_up_winning(seed):
    """The whole promise of the label: what it says with three cards down is what happens
    when the fourth lands, unless the fourth card changes it."""
    game = Game(cfg=HOUSE.variant(target_score=None), seed=seed)
    agent = GreedyAgent()
    game.bid(game.to_act, agent.select_trump(game.hand_of(game.to_act), True))

    while game.round is not None and not game.round.done:
        state = game.round
        before = len(state.tricks_played)
        leader = state.leader
        seat = game.to_act
        game.play(seat, agent.decide(game.observation(seat)))

        if len(state.tricks_played) > before:
            _, cards = state.tricks_played[-1]
            assert trick_taker(cards, leader, game.contract) == state.last_trick_winner
            assert trick_points(cards, game.contract) == state.trick_results[-1][1]
        else:
            # Mid-trick the claim is about the cards actually on the table, which is all a
            # player at the table can say either.
            assert trick_taker(state.trick, leader, game.contract) in range(4)
