"""The highest-risk function in the codebase gets the most tests.

Hand-written cases pin the three rules that are unlike other trick-taking games; the
Hypothesis tests then check the engine against `tests/reference.py` over whole random
rounds, which is where the interactions between those rules actually show up.
"""

import random

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from krass_jass.cards import format_hand, parse_hand
from krass_jass.legal import legal_moves
from krass_jass.rules import EVAL, Contract
from krass_jass.state import IllegalMove, RoundState
from tests import reference
from tests.helpers import CONTRACT_CODES, to_codes

H = parse_hand
HEARTS = 1
SPADES = 2


def legal_str(hand, trump, led, best_trump=-1, **kw):
    return format_hand(legal_moves(H(hand), trump, led, best_trump, **kw))


# --- the three rules that are unlike Bridge/Skat/Hearts ---------------------


def test_leading_allows_anything():
    assert legal_str("SA S7 HJ DA", HEARTS, -1) == "DA HJ SA S7"


def test_may_trump_even_when_able_to_follow():
    """The rule that gives Jass its branching factor. Spades led, hand holds spades, and
    the hearts are still legal."""
    assert legal_str("SA S7 HJ H6 DA", HEARTS, SPADES) == "HJ H6 SA S7"


def test_strict_undertrump_excludes_lower_trumps():
    """H9 (trump 9) has already trumped; only the Puur beats it, so H6 drops out."""
    h9_strength = 7
    assert legal_str("SA S7 HJ H6 DA", HEARTS, SPADES, h9_strength) == "HJ SA S7"


def test_undertrump_rule_can_be_switched_off():
    h9_strength = 7
    assert legal_str(
        "SA S7 HJ H6 DA", HEARTS, SPADES, h9_strength, strict_undertrump=False
    ) == "HJ H6 SA S7"


def test_all_trump_hand_may_undertrump():
    """The exception: with nothing but trumps, any trump is allowed."""
    assert legal_str("HJ H8 H6", HEARTS, SPADES, 7) == "HJ H8 H6"


def test_cannot_follow_may_discard_or_trump():
    assert legal_str("DA D7 HJ", HEARTS, SPADES) == "DA D7 HJ"


def test_puur_is_exempt_from_a_trump_lead():
    assert legal_str("SA S7 HJ DA", HEARTS, HEARTS) == "DA HJ SA S7"


def test_puur_is_not_exempt_when_other_trumps_are_held():
    assert legal_str("SA HJ H6 DA", HEARTS, HEARTS) == "HJ H6"


def test_puur_exemption_can_be_switched_off():
    assert legal_str("SA S7 HJ DA", HEARTS, HEARTS, puur_exempt=False) == "HJ"


def test_no_trump_at_all_on_a_trump_lead():
    assert legal_str("SA S7 DA", HEARTS, HEARTS) == "DA SA S7"


@pytest.mark.parametrize("contract", [Contract.OBENABE, Contract.UNDENUFE])
def test_no_trump_contracts_are_plain_follow_suit(contract):
    assert legal_str("SA S7 HJ DA", -1, SPADES) == "SA S7"
    assert legal_str("HJ DA", -1, SPADES) == "DA HJ"


# --- the property tests -----------------------------------------------------


def deal(rng):
    deck = list(range(36))
    rng.shuffle(deck)
    return [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]


@settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    seed=st.integers(min_value=0, max_value=2**32 - 1),
    contract=st.sampled_from(list(Contract)),
)
def test_engine_agrees_with_reference_over_a_whole_round(seed, contract):
    """Play a full random round, checking legal moves and the trick winner at every ply
    against the independently written reference."""
    rng = random.Random(seed)
    state = RoundState(contract=contract, hands=deal(rng), cfg=EVAL, leader=rng.randrange(4))
    code = CONTRACT_CODES[contract]

    ref_hands = [to_codes(h) for h in state.hands]

    while not state.done:
        trick_codes = to_codes_ordered(state.trick)
        for _ in range(4):
            seat = state.to_play
            got = set(to_codes(state.legal_moves(seat)))
            want = reference.legal(ref_hands[seat], code, trick_codes)
            assert got == want, (
                f"contract={code} seat={seat} trick={trick_codes} "
                f"hand={sorted(ref_hands[seat])} engine={sorted(got)} ref={sorted(want)}"
            )

            choice = sorted(got)[rng.randrange(len(got))]
            ref_hands[seat].remove(choice)
            trick_codes.append(choice)
            state.play(to_card(choice))

        # the trick just resolved — check who the engine says took it
        leader, cards = state.tricks_played[-1]
        assert state.last_trick_winner == (leader + reference.winner_index(trick_codes, code)) % 4


@settings(max_examples=200, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=2**32 - 1),
    contract=st.sampled_from(list(Contract)),
)
def test_legal_moves_is_never_empty_and_is_a_subset_of_the_hand(seed, contract):
    rng = random.Random(seed)
    state = RoundState(contract=contract, hands=deal(rng), cfg=EVAL, leader=rng.randrange(4))
    while not state.done:
        seat = state.to_play
        legal = state.legal_moves(seat)
        assert legal, "a non-empty hand always has a legal move"
        assert legal & ~state.hands[seat] == 0, "returned a card not in the hand"
        cards = to_codes(legal)
        state.play(to_card(cards[rng.randrange(len(cards))]))


@settings(max_examples=100, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_illegal_moves_are_rejected(seed):
    """The engine is authoritative: anything outside `legal_moves` raises, always."""
    rng = random.Random(seed)
    state = RoundState(contract=Contract.HEARTS, hands=deal(rng), cfg=EVAL)
    seat = state.to_play
    illegal = state.hands[seat] ^ state.legal_moves(seat)  # held but not legal
    other_seat_card = state.hands[(seat + 1) % 4] & ~state.hands[seat]
    for mask in (illegal, other_seat_card):
        for code in to_codes(mask)[:3]:
            with pytest.raises(IllegalMove):
                state.play(to_card(code))


def to_card(code):
    from krass_jass.cards import parse_card

    return parse_card(code)


def to_codes_ordered(cards):
    from krass_jass.cards import format_card

    return [format_card(c) for c in cards]
