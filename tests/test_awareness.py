"""The one thing the table read still says: which way the cards on the table are going.

What it says has to be right — a player acts on it — and it has to be derivable from the
cards face up, or the display would be a cheat rather than a help. Everything else the module
used to offer (the trump count, the points on the table, who is out of trump) was taken back
out: counting is what a player is at the table to do.

`test_observation.py` guards what a *bot* sees. This guards what the *screen* says.
"""

import pytest

from krass_jass.agent import GreedyAgent
from krass_jass.awareness import trick_taker
from krass_jass.game import Game
from krass_jass.rules import HOUSE


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
        else:
            # Mid-trick the claim is about the cards actually on the table, which is all a
            # player at the table can say either.
            assert trick_taker(state.trick, leader, game.contract) in range(4)


def test_an_empty_table_names_nobody():
    from krass_jass.rules import Contract

    assert trick_taker([], 0, Contract.HEARTS) is None
