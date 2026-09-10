"""Stöck-Weis-Stich.

The rule only bites when both teams would cross the target in the same round: whoever gets
there first *in claim order* wins, whatever the final totals say. Adding the round up in one
go produces the right totals and can name the wrong winner, which is the failure this
guards.
"""

import pytest

from krass_jass.agent import GreedyAgent
from krass_jass.game import Game, Phase
from krass_jass.rules import HOUSE, Contract


def play_out(game, agent=None):
    agent = agent or GreedyAgent()
    for _ in range(20000):
        if game.phase in (Phase.GAME_OVER, Phase.ROUND_OVER):
            return
        seat = game.to_act
        if game.phase is Phase.BIDDING:
            game.bid(seat, agent.select_trump(game.hand_of(seat), seat == game.forehand))
        elif game.phase is Phase.WEIS:
            game.choose_weis(seat, True)
        else:
            game.play(seat, agent.decide(game.observation(seat)))
    raise AssertionError("round did not finish")


@pytest.mark.parametrize("contract", list(Contract))
def test_the_claim_sequence_always_reproduces_the_round_total(contract):
    """The engine asserts this internally on every round; this pins it across contracts,
    because a dropped claim would silently change who wins a close game."""
    game = Game(cfg=HOUSE.variant(target_score=None), seed=13)
    game.bid(game.to_act, contract.name)
    if game.phase is Phase.WEIS:
        for seat in list(game.weis_offers):
            game.choose_weis(seat, True)
    play_out(game)
    assert game.last_score is not None
    assert sum(game.last_score["round_total"]) == sum(game.scores)


def test_stoeck_is_claimed_before_weis():
    """The whole point of the ordering. Team 1 takes the game on its Stöck even though
    team 0's Weis would otherwise have got there first."""
    from krass_jass.scoring import score_round

    cfg = HOUSE.variant(target_score=1000)
    game = Game(cfg=cfg, seed=1)
    game.contract = Contract.DIAMONDS

    class Round:
        trick_results = [(1, 30), (0, 40), (1, 25), (0, 20), (1, 17), (0, 10), (1, 5), (0, 3), (1, 2)]

    game.round = Round()
    score = score_round(
        (73, 79), (4, 5), 1, Contract.DIAMONDS, cfg, weis=(20, 0), stoeck=(0, 20)
    )
    sequence = game._claim_sequence(score)

    assert sequence[0] == (1, 20), "Stöck is claimed first"
    assert sequence[1] == (0, 20), "then Weis"
    assert all(team in (0, 1) for team, _ in sequence)

    running = [980, 990]
    winner = None
    for team, points in sequence:
        running[team] += points
        if winner is None and max(running) >= 1000:
            winner = team
    assert winner == 1


def test_claim_order_is_configurable():
    """Houses differ. Reversing the order must actually reverse who is paid first."""
    from krass_jass.scoring import score_round

    cfg = HOUSE.variant(target_score=1000, claim_order=("weis", "stoeck", "stich"))
    game = Game(cfg=cfg, seed=1)
    game.contract = Contract.DIAMONDS

    class Round:
        trick_results = [(0, 152)] + [(0, 0)] * 8

    game.round = Round()
    score = score_round((152, 0), (9, 0), 0, Contract.DIAMONDS, cfg, weis=(20, 0), stoeck=(0, 20))
    sequence = game._claim_sequence(score)
    assert sequence[0] == (0, 20), "Weis first under this house rule"
    assert sequence[1] == (1, 20), "Stöck second"


def test_tricks_are_claimed_one_at_a_time_in_order():
    from krass_jass.scoring import score_round

    cfg = HOUSE.variant(target_score=1000)
    game = Game(cfg=cfg, seed=1)
    game.contract = Contract.SPADES

    class Round:
        trick_results = [(0, 11), (1, 20), (0, 4), (1, 3), (0, 24), (1, 10), (0, 30), (1, 30), (0, 20)]

    game.round = Round()
    score = score_round((89, 63), (5, 4), 0, Contract.SPADES, cfg)
    stich = game._claim_sequence(score)
    # nine tricks, the last carrying the five-point bonus
    assert len(stich) == 9
    assert stich[-1] == (0, 25), "the last trick carries the last-trick bonus"
    assert [team for team, _ in stich] == [0, 1, 0, 1, 0, 1, 0, 1, 0]


def test_a_normal_finish_still_names_the_leader():
    game = Game(cfg=HOUSE.variant(target_score=1000), seed=21)
    for _ in range(40):
        if game.phase is Phase.GAME_OVER:
            break
        if game.phase is Phase.ROUND_OVER:
            game.next_round()
            continue
        play_out(game)
    assert game.phase is Phase.GAME_OVER
    from krass_jass.events import EventType

    over = [e for e in game.log.all() if e.type is EventType.GAME_OVER][0]
    winner = over.payload["winner"]
    assert game.scores[winner] >= 1000
