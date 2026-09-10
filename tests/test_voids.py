"""Void inference must be *sound*: never claim a constraint that is not proven.

An unsound constraint makes the search reason about worlds that cannot exist, and it will
not show up as a crash — it shows up as a bot that is subtly, unaccountably worse. So the
main test replays whole random rounds and checks every inferred constraint against the
hands that were actually dealt.
"""

import random

import pytest

from krass_jass.cards import SUIT_MASK, card_list, parse_card, parse_hand as H
from krass_jass.rules import EVAL, HOUSE, Contract
from krass_jass.state import RoundState
from krass_jass.voids import infer_forbidden, infer_from_state


def deal(rng):
    deck = list(range(36))
    rng.shuffle(deck)
    return [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]


@pytest.mark.parametrize("contract", list(Contract))
def test_inferences_are_sound_over_whole_rounds(contract):
    """Every card ruled out must genuinely not be in that seat's hand — checked against the
    real deal at every ply, which the inference never sees."""
    rng = random.Random(500 + int(contract))
    for _ in range(40):
        hands = deal(rng)
        state = RoundState(contract=contract, hands=list(hands), cfg=EVAL, leader=rng.randrange(4))
        while not state.done:
            forbidden = infer_from_state(state)
            for seat in range(4):
                overlap = forbidden[seat] & state.hands[seat]
                assert overlap == 0, (
                    f"{contract.name}: claimed seat {seat} cannot hold "
                    f"{card_list(overlap)}, but it does"
                )
            legal = card_list(state.legal_moves())
            state.play(legal[rng.randrange(len(legal))])


def test_failing_to_follow_proves_a_void():
    state = RoundState(
        contract=Contract.HEARTS,
        hands=[H("SA S7 D6"), H("CA CK CQ"), H("SK S8 D7"), H("S9 S6 D8")],
        cfg=EVAL,
        leader=0,
    )
    state.play(parse_card("SA"))
    state.play(parse_card("CA"))  # seat 1 discards a club on a spade lead
    forbidden = infer_from_state(state)
    assert forbidden[1] & SUIT_MASK[2] == SUIT_MASK[2], "seat 1 is void in spades"
    assert forbidden[0] == 0 and forbidden[2] == 0


def test_trumping_proves_nothing():
    """The trap. You may always trump in Jass, so a trump on a side-suit lead says nothing
    about whether the player could have followed."""
    state = RoundState(
        contract=Contract.HEARTS,
        hands=[H("SA S7 D6"), H("HA SK D7"), H("SQ S8 D8"), H("S9 S6 D9")],
        cfg=EVAL,
        leader=0,
    )
    state.play(parse_card("SA"))
    state.play(parse_card("HA"))  # seat 1 trumps — and still holds SK
    assert infer_from_state(state)[1] == 0


def test_discard_on_a_trump_lead_leaves_the_puur_possible():
    """Under the Puur exemption the proof is 'trumps are a subset of {Puur}', not 'no
    trumps'. Claiming the stronger version would rule out a hand that is perfectly legal."""
    state = RoundState(
        contract=Contract.HEARTS,
        hands=[H("HA H7 D6"), H("HJ SK D7"), H("SQ S8 D8"), H("S9 S6 D9")],
        cfg=EVAL,
        leader=0,
    )
    state.play(parse_card("HA"))
    state.play(parse_card("SK"))  # legal: seat 1's only trump is the Puur

    forbidden = infer_from_state(state)
    assert forbidden[1] & (1 << parse_card("HJ")) == 0, "the Puur must stay possible"
    assert forbidden[1] & (1 << parse_card("H9")) != 0, "every other heart is ruled out"


def test_without_the_puur_exemption_a_discard_rules_out_every_trump():
    cfg = HOUSE.variant(puur_exempt_trump_lead=False)
    state = RoundState(
        contract=Contract.HEARTS,
        hands=[H("HA H7 D6"), H("SK SQ D7"), H("S9 S8 D8"), H("S6 C6 D9")],
        cfg=cfg,
        leader=0,
    )
    state.play(parse_card("HA"))
    state.play(parse_card("SK"))
    assert infer_from_state(state)[1] & SUIT_MASK[1] == SUIT_MASK[1]


def test_constraints_persist_across_tricks():
    """Proven once, true forever — a player cannot acquire a suit they did not have."""
    rng = random.Random(9)
    state = RoundState(contract=Contract.CLUBS, hands=deal(rng), cfg=EVAL)
    seen = [0] * 4
    while not state.done:
        forbidden = infer_from_state(state)
        for s in range(4):
            assert forbidden[s] & seen[s] == seen[s], "a constraint was forgotten"
            seen[s] = forbidden[s]
        legal = card_list(state.legal_moves())
        state.play(legal[rng.randrange(len(legal))])
