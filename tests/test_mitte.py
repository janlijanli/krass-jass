"""The Mitte row (Coiffeur, owner 2026-11-06), against `tests/reference.py`.

The ten is highest, then outwards in equal pairs — 9 and Under, 8 and Ober, 7 and King, 6 and Ace —
and of an equal pair the card played first takes the trick. No trump. The round is counted as
Obenabe or Undenufe by the first card of trick 1 that is not a ten: above the ten Obenabe, below
it Undenufe.
"""

from __future__ import annotations

import random

import pytest

from krass_jass.cards import card_list, format_card, parse_card
from krass_jass.coiffeur import ROW_NAMES
from krass_jass.game import Game, Phase
from krass_jass.rules import COIFFEUR, Contract, Order
from krass_jass.schedule import mitte, mitte_count, parse
from krass_jass.state import RoundState
from krass_jass.tables import CARD_VALUES

from tests import reference

core = pytest.importorskip("krass_jass_core")


def deal(rng: random.Random) -> list[int]:
    deck = list(range(36))
    rng.shuffle(deck)
    return [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]


def codes(mask: int) -> set[str]:
    return {format_card(c) for c in card_list(mask)}


@pytest.mark.parametrize("seed", range(200))
def test_legal_moves_winners_and_the_count_agree_with_the_reference(seed):
    rng = random.Random(seed)
    st = RoundState(contract=Contract.OBENABE, hands=deal(rng), cfg=COIFFEUR, leader=rng.randrange(4),
                    schedule=mitte().tricks)
    ref_hands = [codes(h) for h in st.hands]
    first: list[str] = []
    while not st.done:
        trick: list[str] = []
        for _ in range(4):
            seat = st.to_play
            assert st.trick_contract is Order.MITTE
            got = codes(st.legal_moves(seat))
            assert got == reference.legal(sorted(ref_hands[seat]), "MITTE", trick)
            card = sorted(got)[rng.randrange(len(got))]
            ref_hands[seat].remove(card)
            trick.append(card)
            st.play(parse_card(card))
        if not first:
            first = trick
        leader, _ = st.tricks_played[-1]
        assert st.last_trick_winner == (leader + reference.winner_index(trick, "MITTE")) % 4
    counted = Contract[reference.mitte_counted_as(first)]
    assert st.contract is counted
    values = CARD_VALUES[counted]
    assert sum(st.trick_points) == sum(values[c] for _, cards in st.tricks_played for c in cards) == 152


def test_equal_pairs_go_to_the_card_played_first():
    for trick, winner in (
        (["D9", "DJ", "D6", "D7"], 0),     # 9 and Under equal: the 9 was first
        (["DJ", "D9", "D6", "D7"], 0),     # and the other way round
        (["DA", "D6", "DK", "D7"], 2),     # the King beats 6 and Ace; the 7 came after it
        (["D8", "DQ", "DT", "D9"], 2),     # the ten is highest
        (["DA", "HT", "S9", "CJ"], 0),     # nothing followed: the lead keeps it
    ):
        assert reference.winner_index(trick, "MITTE") == winner
        st = RoundState(contract=Contract.OBENABE, hands=[0] * 4, cfg=COIFFEUR, schedule=mitte().tricks)
        st.hands = [1 << parse_card(c) for c in trick]
        for c in trick:
            st.play(parse_card(c))
        assert st.last_trick_winner == winner, trick


def test_the_count_is_decided_by_the_first_card_that_is_not_a_ten():
    p = lambda cards: [parse_card(c) for c in cards]  # noqa: E731
    assert mitte_count(p(["DK"])) is Contract.OBENABE
    assert mitte_count(p(["D9"])) is Contract.UNDENUFE
    assert mitte_count(p(["DT"])) is None
    assert mitte_count(p(["DT", "D6"])) is Contract.UNDENUFE
    assert mitte_count(p(["DT", "HT", "CA"])) is Contract.OBENABE
    assert mitte_count(p(["DT", "HT", "ST", "CT"])) is Contract.OBENABE
    for first in (["DT", "D6"], ["DT", "HJ"], ["DA"], ["D7"]):
        assert reference.mitte_counted_as(first) == mitte_count(p(first)).name


def test_a_mitte_in_the_game_is_its_own_row_and_counted_as_its_first_card_says():
    game = Game(cfg=COIFFEUR, seed=21)
    seat = game.to_act
    assert "MITTE" in [str(c) for c in game.legal_choices()] and parse("MITTE") == mitte()
    game.bid(seat, "MITTE")
    assert game.round.trick_contract is Order.MITTE
    obs = game.observation(seat)
    assert obs.schedule == (6,) * 9 and obs.trick_contract is Order.MITTE
    rng = random.Random(3)
    while game.phase is not Phase.ROUND_OVER:
        s = game.to_act
        game.play(s, rng.choice(card_list(game.round.legal_moves(s))))
    first = [format_card(c) for c in game.round.tricks_played[0][1]]
    assert game.contract is Contract[reference.mitte_counted_as(first)]
    team = seat % 2
    taken = game.last_score["round_total"][team]
    assert game.sheet.written[team][ROW_NAMES.index("MITTE")] == (taken + 5) // 10


@pytest.mark.parametrize("seed", range(6))
def test_the_search_plays_a_mitte_and_reads_the_count_mid_trick(seed):
    """The search is handed a Mitte at every point of the round — counted or not yet — and only
    ever answers with a legal card."""
    from krass_jass.agent import DmctsAgent

    agent = DmctsAgent(determinizations=8, iterations=16)
    game = Game(cfg=COIFFEUR, seed=seed)
    game.bid(game.to_act, "MITTE")
    while game.phase is not Phase.ROUND_OVER:
        s = game.to_act
        card = agent.decide(game.observation(s))
        assert game.round.legal_moves(s) >> card & 1
        game.play(s, card)
