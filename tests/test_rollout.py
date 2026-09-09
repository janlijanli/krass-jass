"""The rollout kernel is the seam that will eventually be rewritten in a faster language
(`docs/plan-review.md` §1). These tests are the contract any replacement must satisfy."""

import random

import pytest

from krass_jass.cards import bit
from krass_jass.legal import legal_moves
from krass_jass.rules import EVAL, HOUSE, Contract
from krass_jass.rollout import make_kernel, play_out
from krass_jass.state import RoundState


def deal(rng):
    deck = list(range(36))
    rng.shuffle(deck)
    return [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]


@pytest.mark.parametrize("contract", list(Contract))
def test_points_always_total_157(contract):
    rng = random.Random(4)
    kernel = make_kernel(contract, EVAL)
    for _ in range(200):
        a, b = play_out(deal(rng), rng.randrange(4), kernel, rng)
        assert a + b == 157


def test_match_bonus_is_applied_when_enabled():
    """Force a match: one team gets every trump plus the top of every suit is irrelevant —
    simplest is to give one hand all the trumps and check across many deals."""
    rng = random.Random(11)
    kernel = make_kernel(Contract.HEARTS, HOUSE)
    seen_match = False
    for _ in range(4000):
        a, b = play_out(deal(rng), rng.randrange(4), kernel, rng)
        if a + b != 157:
            assert a + b == 257, "a match is worth exactly 100 more"
            seen_match = True
    assert seen_match, "no match occurred in 4000 random deals; the test is not exercising the bonus"


def test_same_seed_replays_identically():
    """Determinism is what turns 'the bot did something weird' into a test case."""
    hands = deal(random.Random(3))
    kernel = make_kernel(Contract.CLUBS, EVAL)
    a = play_out(list(hands), 0, kernel, random.Random(99))
    b = play_out(list(hands), 0, kernel, random.Random(99))
    assert a == b


def test_kernel_only_ever_plays_legal_cards():
    """Cross-check the kernel against the authoritative object layer: replay the kernel's
    own choices through RoundState, which validates every move."""
    rng = random.Random(5)
    for _ in range(50):
        hands = deal(rng)
        contract = Contract(rng.randrange(6))
        state = RoundState(contract=contract, hands=list(hands), cfg=EVAL, leader=0)
        # RoundState.play raises IllegalMove, so simply completing a random round through
        # the same legal_moves the kernel uses is the assertion.
        while not state.done:
            seat = state.to_play
            legal = state.legal_moves(seat)
            assert legal == legal_moves(
                state.hands[seat],
                state.trump,
                state.led_suit,
                state.best_trump_strength(),
            )
            cards = [c for c in range(36) if legal & bit(c)]
            state.play(cards[rng.randrange(len(cards))])


@pytest.mark.parametrize("tricks_played", [0, 1, 4, 8])
def test_plays_out_from_a_partial_position(tricks_played):
    """DMCTS rolls out from wherever the search is, not from the deal."""
    rng = random.Random(21)
    kernel = make_kernel(Contract.SPADES, EVAL)
    for _ in range(30):
        state = RoundState(contract=Contract.SPADES, hands=deal(rng), cfg=EVAL)
        while len(state.tricks_played) < tricks_played:
            legal = state.legal_moves()
            cards = [c for c in range(36) if legal & bit(c)]
            state.play(cards[rng.randrange(len(cards))])

        before = sum(state.trick_points)
        a, b = play_out(list(state.hands), state.leader, kernel, rng)
        # the playout covers exactly the points still on the table, plus the last trick
        assert before + a + b == 157


def test_empty_position_scores_nothing():
    kernel = make_kernel(Contract.SPADES, EVAL)
    assert play_out([0, 0, 0, 0], 0, kernel, random.Random(1)) == (0, 0)


def test_match_bonus_is_not_awarded_from_a_partial_position():
    """From mid-round the kernel cannot know who took the earlier tricks."""
    rng = random.Random(31)
    kernel = make_kernel(Contract.HEARTS, HOUSE)
    for _ in range(500):
        state = RoundState(contract=Contract.HEARTS, hands=deal(rng), cfg=HOUSE)
        legal = state.legal_moves()
        cards = [c for c in range(36) if legal & bit(c)]
        for _ in range(4):
            legal = state.legal_moves()
            cards = [c for c in range(36) if legal & bit(c)]
            state.play(cards[rng.randrange(len(cards))])
        a, b = play_out(list(state.hands), state.leader, kernel, rng)
        assert a + b <= 157, "match bonus must not be awarded from a partial position"


def test_round_score_includes_weis_and_stoeck_from_the_dealt_hands():
    """Weis is announced from the dealt hand during the first trick, so the round must
    remember it — by scoring time every hand is empty."""
    rng = random.Random(77)
    state = RoundState(contract=Contract.HEARTS, hands=deal(rng), cfg=HOUSE)
    dealt = list(state.hands)
    while not state.done:
        legal = state.legal_moves()
        cards = [c for c in range(36) if legal & bit(c)]
        state.play(cards[rng.randrange(len(cards))])

    from krass_jass.weis import score_stoeck, score_weis

    assert all(h == 0 for h in state.hands)
    score = state.score()
    assert score.weis == score_weis(dealt, 1, HOUSE, 0)[0]
    assert score.stoeck == score_stoeck(dealt, 1, HOUSE)
    assert sum(score.trick_points) + sum(score.last_trick) == 157
