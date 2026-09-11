"""The table read shown to the player.

Two obligations pull against each other, and both are tested here. It must be **sound** —
never claim a void that the cards do not prove, because a player acts on it. And it must be
**public** — never sharpen on information a player at the table does not have, because the
display would then be a cheat rather than a help.

`test_observation.py` guards what a *bot* sees. This guards what the *screen* says.
"""

import pytest

from krass_jass.agent import GreedyAgent
from krass_jass.awareness import NONE, PUUR, trick_points, trick_taker, trump_read
from krass_jass.cards import SUIT_MASK, parse_card, parse_hand
from krass_jass.game import Game
from krass_jass.rules import HOUSE, Contract
from krass_jass.state import RoundState
from krass_jass.tables import PUUR_MASK

HEARTS = Contract.HEARTS


def puur_table():
    """Hearts are trump. Seat 2 holds no heart at all; seat 0 holds the Puur and nothing else
    in trump. Leader is seat 1, so the order of play is 1, 2, 3, 0."""
    hands = [
        parse_hand("HJ D6 D7 D8 D9 DT DJ DQ DK"),
        parse_hand("HA HK DA S6 S7 S8 S9 ST SJ"),
        parse_hand("SQ SK SA C6 C7 C8 C9 CT CJ"),
        parse_hand("HQ HT H9 H8 H7 H6 CQ CK CA"),
    ]
    return RoundState(contract=HEARTS, hands=hands, cfg=HOUSE, leader=1)


def read_for(state, seat):
    return trump_read(
        state.tricks_played, state.trick, state.leader, seat, state.hands[seat], HEARTS, HOUSE
    )


def test_claims_nothing_before_a_card_is_played():
    """Seat 2 genuinely holds no trump. Nothing has proved it, so nothing may say so."""
    state = puur_table()
    assert state.hands[2] & SUIT_MASK[HEARTS.trump_suit] == 0, "the fixture means what it says"
    assert read_for(state, 0)["voids"] == [None, None, None, None]


def test_a_discard_on_a_trump_lead_reads_as_far_as_the_puur():
    """The Jass-specific edge. Seat 2 discards on a trump lead, which proves their trump
    holding is a subset of the Puur — not that they are empty, because the Puur may be held
    back. Two seats therefore read the same discard differently, and both are right."""
    state = puur_table()
    state.play(parse_card("HA"))   # seat 1 leads trump
    state.play(parse_card("C6"))   # seat 2 cannot follow

    # Seat 0 holds the Puur, so for them there is no trump left that seat 2 could have.
    assert read_for(state, 0)["voids"][2] == NONE
    # Seat 3 cannot see the Puur, so for them seat 2 might still hold exactly that one card.
    assert read_for(state, 3)["voids"][2] == PUUR


def test_the_read_hardens_once_the_puur_is_played():
    """The user's case: a player who did not trump when they should have, and the Bauer has
    since gone, has no trump at all."""
    state = puur_table()
    state.play(parse_card("HA"))
    state.play(parse_card("C6"))
    state.play(parse_card("H6"))
    assert read_for(state, 3)["voids"][2] == PUUR, "still only the Puur in question"

    state.play(parse_card("HJ"))   # seat 0 plays the Puur
    assert read_for(state, 3)["voids"][2] == NONE, "the one card in question is now face up"


def test_trumps_out_counts_only_what_is_unaccounted_for():
    state = puur_table()
    assert read_for(state, 0)["out"] == 8, "nine trumps, one of them mine"
    state.play(parse_card("HA"))
    assert read_for(state, 0)["out"] == 7


def test_no_trump_contract_reads_nothing():
    hands = [parse_hand(h) for h in (
        "HJ D6 D7 D8 D9 DT DJ DQ DK",
        "HA HK DA S6 S7 S8 S9 ST SJ",
        "SQ SK SA C6 C7 C8 C9 CT CJ",
        "HQ HT H9 H8 H7 H6 CQ CK CA",
    )]
    state = RoundState(contract=Contract.OBENABE, hands=hands, cfg=HOUSE, leader=1)
    read = trump_read(
        state.tricks_played, state.trick, state.leader, 0, state.hands[0],
        Contract.OBENABE, HOUSE,
    )
    assert read == {"out": None, "voids": [None, None, None, None]}


@pytest.mark.parametrize("seed", [1, 7, 31, 404])
def test_the_read_is_never_wrong_about_a_real_hand(seed):
    """Soundness against ground truth, over whole games. A player acts on this, so a claim
    that does not hold is worse than no claim at all."""
    game = Game(cfg=HOUSE.variant(target_score=None), seed=seed)
    agent = GreedyAgent()
    game.bid(game.to_act, agent.select_trump(game.hand_of(game.to_act), True))

    while game.round is not None and not game.round.done:
        state = game.round
        trump_mask = SUIT_MASK[game.contract.trump_suit] if game.contract.is_trump else 0

        for seat in range(4):
            read = read_of(game, seat)
            if trump_mask:
                held = sum(
                    bin(h & trump_mask).count("1")
                    for s, h in enumerate(state.hands)
                    if s != seat
                )
                assert read["out"] == held, "the count must be the true one, not an estimate"

            for other, claim in enumerate(read["voids"]):
                theirs = state.hands[other] & trump_mask
                if claim == NONE:
                    assert theirs == 0, f"seat {other} was called empty holding {theirs:b}"
                elif claim == PUUR:
                    assert theirs & ~PUUR_MASK[game.contract.trump_suit] == 0, (
                        f"seat {other} was called Puur-only while holding more"
                    )

        seat = game.to_act
        game.play(seat, agent.decide(game.observation(seat)))


def read_of(game, seat):
    state = game.round
    return trump_read(
        state.tricks_played, state.trick, state.leader, seat, state.hands[seat],
        game.contract, game.cfg,
    )


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
