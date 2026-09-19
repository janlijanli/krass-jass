"""Sidi Barrani: the auction, the double after the lead, the stake, the dealer, the end.

Rules in `docs/rules-config.md`, "Sidi Barrani". `reference_auction` below is written from that
text alone and imports nothing from `krass_jass.auction`, so the two cannot agree on the same
mistake.
"""

from __future__ import annotations

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from krass_jass.agent import GreedyAgent
from krass_jass.auction import Auction, Call
from krass_jass.cards import card_list
from krass_jass.game import Game, Phase
from krass_jass.rules import HOUSE, SIDI, SIDI_EVAL, Contract
from krass_jass.state import IllegalMove

LADDER = (40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 157, 257)


def reference_auction(opener, calls):
    """From the rules text. Returns (done, high, doubled) or raises ValueError on an illegal call."""
    seat, high, doubled, passes_in_a_row = opener, None, False, 0
    for call in calls:
        words = call.split()
        if words == ["PASS"]:
            passes_in_a_row += 1
        elif words == ["DOUBLE"]:
            if high is None or (seat % 2) == (high[0] % 2) or doubled:
                raise ValueError("double")
            doubled = True
        else:
            value = int(words[1])
            if value not in LADDER or (high is not None and value <= high[2]):
                raise ValueError("bid")
            high, passes_in_a_row = (seat, words[0], value), 0
        seat = (seat + 1) % 4
        over = (
            doubled
            or (high is None and passes_in_a_row == 4)
            or (high is not None and (passes_in_a_row == 3 or high[2] == 257))
        )
        if over:
            return True, high, doubled
    return False, high, doubled


CALLS = st.sampled_from(
    ["PASS"] * 6 + ["DOUBLE"] + [f"{c.name} {v}" for c in Contract for v in LADDER]
)


@settings(max_examples=400, deadline=None)
@given(opener=st.integers(0, 3), calls=st.lists(CALLS, max_size=14))
def test_the_auction_agrees_with_the_rules_text(opener, calls):
    auction = Auction(opener=opener, cfg=SIDI)
    for i, call in enumerate(calls):
        prefix = calls[: i + 1]
        try:
            expected = reference_auction(opener, prefix)
        except ValueError:
            with pytest.raises(IllegalMove):
                auction.call(auction.to_act, call)
            return
        auction.call(auction.to_act, call)
        done, high, doubled = expected
        assert auction.done == done
        assert auction.doubled == doubled
        got = None if auction.high is None else (auction.high[0], auction.high[1].name, auction.high[2])
        assert got == high
        if done:
            with pytest.raises(IllegalMove):
                auction.call(0, "PASS")
            return


@settings(max_examples=200, deadline=None)
@given(opener=st.integers(0, 3), calls=st.lists(CALLS, max_size=10))
def test_legal_calls_are_exactly_the_calls_that_are_accepted(opener, calls):
    auction = Auction(opener=opener, cfg=SIDI)
    for call in calls:
        if auction.done:
            break
        seat = auction.to_act
        legal = {str(c) for c in auction.legal_calls(seat)}
        parsed = str(Call.parse(call))
        if parsed in legal:
            auction.call(seat, call)
        else:
            with pytest.raises(IllegalMove):
                auction.call(seat, call)


def test_a_passed_seat_may_come_back_and_partners_may_overbid():
    a = Auction(opener=1, cfg=SIDI)
    a.call(1, "HEARTS 60")
    a.call(2, "PASS")
    a.call(3, "SPADES 70")     # overbids across the table, a different contract
    a.call(0, "PASS")
    a.call(1, "HEARTS 80")     # seat 1's partner is seat 3: overbidding a partner is allowed
    a.call(2, "OBENABE 90")    # seat 2 passed before and is back
    assert not a.done and a.high == (2, Contract.OBENABE, 90)
    for seat in (3, 0, 1):
        a.call(seat, "PASS")
    assert a.done and not a.thrown_in


def test_no_order_among_contracts_only_the_number_counts():
    a = Auction(opener=0, cfg=SIDI)
    a.call(0, "SPADES 100")
    with pytest.raises(IllegalMove):
        a.call(1, "HEARTS 100")
    a.call(1, "HEARTS 110")


def test_only_the_opponents_double_and_a_double_ends_the_auction():
    a = Auction(opener=0, cfg=SIDI)
    a.call(0, "CLUBS 70")
    a.call(1, "PASS")
    with pytest.raises(IllegalMove):
        a.call(2, "DOUBLE")    # partner of the bidder
    a.call(2, "PASS")
    a.call(3, "DOUBLE")
    assert a.done and a.doubled and a.high == (0, Contract.CLUBS, 70)


def test_match_ends_the_auction():
    a = Auction(opener=2, cfg=SIDI)
    a.call(2, "OBENABE 257")
    assert a.done


# --- the game ---------------------------------------------------------------


def play_out(game, rng, caller=None, doubler=None):
    """Drive a game to the end of the current round. `caller(game, seat)` names a call."""
    agent = GreedyAgent()
    while game.phase not in (Phase.ROUND_OVER, Phase.GAME_OVER):
        seat = game.to_act
        if game.phase is Phase.BIDDING:
            call = caller(game, seat) if caller else random_call(game, seat, rng)
            game.bid(seat, call)
        elif game.phase is Phase.DOUBLING:
            game.double(seat, doubler(game, seat) if doubler else rng.random() < 0.2)
        else:
            obs = game.observation(seat)
            game.play(seat, agent.decide(obs))


def random_call(game, seat, rng):
    legal = game.auction.legal_calls(seat)
    if rng.random() < 0.55:
        return "PASS"
    return str(rng.choice(legal[:12]))


def test_the_declarer_leads_and_opponents_are_asked_after_the_lead():
    game = Game(cfg=SIDI, seed=3)
    opener = game.to_act
    game.bid(opener, "HEARTS 80")
    for _ in range(3):
        game.bid(game.to_act, "PASS")
    assert game.phase is Phase.PLAYING and game.declarer == opener
    assert game.round.leader == opener and game.to_act == opener
    lead = card_list(game.round.legal_moves(opener))[0]
    game.play(opener, lead)
    assert game.phase is Phase.DOUBLING
    assert game.to_act == (opener + 1) % 4
    with pytest.raises(IllegalMove):
        game.play(game.to_act, card_list(game.round.legal_moves(game.to_act))[0])
    game.double((opener + 1) % 4, False)
    assert game.to_act == (opener + 3) % 4
    game.double((opener + 3) % 4, True)
    assert game.doubled and game.phase is Phase.PLAYING and game.to_act == (opener + 1) % 4


def test_no_question_after_the_lead_once_doubled_in_the_auction():
    game = Game(cfg=SIDI, seed=4)
    opener = game.to_act
    game.bid(opener, "SPADES 60")
    game.bid(game.to_act, "DOUBLE")
    game.play(opener, card_list(game.round.legal_moves(opener))[0])
    assert game.phase is Phase.PLAYING


def test_all_passing_throws_the_hand_in_and_the_next_seat_deals():
    game = Game(cfg=SIDI, seed=5)
    dealer, hands = game.dealer, list(game._dealt)
    for _ in range(4):
        game.bid(game.to_act, "PASS")
    assert game.phase is Phase.BIDDING
    assert game.dealer == (dealer + 1) % 4
    assert game.to_act == (dealer + 2) % 4
    assert list(game._dealt) != hands


def reference_round(declarer_points, bid, doubled):
    """(declarers, opponents) written for one round, from the rules text."""
    card_total = 257 if declarer_points in (0, 257) else 157
    opponents = card_total - declarer_points
    stake = bid * (2 if doubled else 1)
    if declarer_points >= bid:
        return declarer_points + stake, opponents
    return declarer_points, opponents + stake


@pytest.mark.parametrize("seed", range(40))
def test_rounds_are_written_as_the_rules_say(seed):
    rng = random.Random(seed)
    game = Game(cfg=SIDI_EVAL, seed=seed)
    play_out(game, rng)
    d = game.declarer & 1
    s = game.last_score
    points = s["trick_points"][d] + s["last_trick"][d] + s["match"][d]
    ours, theirs = reference_round(points, game.bid_value, game.doubled)
    assert s["round_total"][d] == ours and s["round_total"][1 - d] == theirs
    assert s["made"] == (points >= game.bid_value)


def test_the_examples_in_the_rules():
    assert reference_round(113, 100, False) == (213, 44)
    assert reference_round(113, 120, True) == (113, 284)
    assert reference_round(257, 257, False) == (514, 0)
    assert reference_round(119, 257, True) == (119, 38 + 514)


@pytest.mark.parametrize("seed", range(6))
def test_whole_games_end_at_the_target_with_the_higher_score(seed):
    rng = random.Random(seed)
    game = Game(cfg=SIDI, seed=seed)
    rounds = 0
    while game.phase is not Phase.GAME_OVER:
        dealer_before = None
        play_out(game, rng)
        if game.phase is Phase.ROUND_OVER:
            declarer = game.declarer
            game.next_round()
            assert game.dealer == (declarer + 1) % 4
        rounds += 1
        assert rounds < 200
    assert max(game.scores) >= 2000 and game.scores[0] != game.scores[1]
    winner = game.log.all()[-1].payload["winner"]
    assert game.scores[winner] > game.scores[1 - winner]


def test_the_schieber_is_untouched():
    game = Game(cfg=HOUSE, seed=1)
    assert game.auction is None
    game.bid(game.to_act, "HEARTS")
    assert game.phase in (Phase.PLAYING, Phase.WEIS)
    assert game.round.leader == game.forehand


def test_the_auction_reaches_the_observation():
    game = Game(cfg=SIDI, seed=8)
    opener = game.to_act
    game.bid(opener, "UNDENUFE 50")
    for _ in range(3):
        game.bid(game.to_act, "PASS")
    obs = game.observation(opener)
    assert obs.auction[0] == (opener, "UNDENUFE 50") and len(obs.auction) == 4
    assert obs.bid_value == 50 and not obs.doubled


@pytest.mark.parametrize("seed", range(30))
def test_there_is_no_stoeck_in_the_sidi(seed):
    """Stöck does not count in the Sidi, so it must not be announced either — the points were
    always zero, but the second honour used to be called and shown at the table."""
    rng = random.Random(seed)
    game = Game(cfg=SIDI_EVAL, seed=seed)
    play_out(game, rng)
    assert not [e for e in game.log.all() if e.type.value == "stoeck"]
    assert game.stoeck_seats == []


def test_an_opponent_may_knock_out_of_turn():
    """Owner, 2026-09-19: a double may come at any time until the second card — at a table you
    knock the moment you hear the bid, without waiting for your partner to speak first."""
    a = Auction(opener=1, cfg=SIDI)
    a.call(1, "HEARTS 90")
    assert a.to_act == 2
    with pytest.raises(IllegalMove):
        a.call(0, "PASS")          # nothing else is out of turn
    with pytest.raises(IllegalMove):
        a.call(3, "DOUBLE")        # and never the bidder's own partner
    a.call(0, "DOUBLE")
    assert a.done and a.doubled and a.high == (1, Contract.HEARTS, 90)


def test_a_turn_is_not_lost_to_a_knock_that_does_not_end_the_auction():
    a = Auction(opener=1, cfg=SIDI.variant(sidi_double_ends_auction=False))
    a.call(1, "HEARTS 90")
    a.call(0, "DOUBLE")            # out of turn
    assert a.to_act == 2 and not a.done
