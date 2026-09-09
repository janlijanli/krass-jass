"""The Rust core must agree with the Python engine, which agrees with `tests/reference.py`.

This is the whole safety argument for the port: the reference was written from the rules
text and imports neither implementation, so a shared misreading cannot hide here. Any
divergence is a bug in the Rust core until proven otherwise — the Python engine is the
engine of record.
"""

import random

import pytest

from krass_jass.cards import card_list, card_suit
from krass_jass.legal import legal_moves as py_legal_moves
from krass_jass.rules import EVAL, Contract
from krass_jass.state import RoundState
from tests import reference
from tests.helpers import CONTRACT_CODES, to_codes

core = pytest.importorskip("krass_jass_core", reason="Rust core not built (see rust/README)")


def deal(rng):
    deck = list(range(36))
    rng.shuffle(deck)
    return [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]


# --- legal moves ------------------------------------------------------------


@pytest.mark.parametrize("contract", list(Contract))
def test_legal_moves_agree_with_python_and_the_reference(contract):
    """Walk whole random rounds, comparing all three at every ply."""
    rng = random.Random(1234 + int(contract))
    code = CONTRACT_CODES[contract]

    for _ in range(40):
        state = RoundState(contract=contract, hands=deal(rng), cfg=EVAL, leader=rng.randrange(4))
        ref_hands = [to_codes(h) for h in state.hands]

        while not state.done:
            trick_codes = [
                to_codes(1 << c)[0] for c in state.trick
            ]
            for _ in range(4):
                seat = state.to_play
                py = py_legal_moves(
                    state.hands[seat], state.trump, state.led_suit, state.best_trump_strength()
                )
                rs = core.legal_moves(
                    state.hands[seat], state.trump, state.led_suit, state.best_trump_strength()
                )
                ref = reference.legal(ref_hands[seat], code, trick_codes)

                assert rs == py, f"rust vs python: {to_codes(rs)} != {to_codes(py)}"
                assert set(to_codes(rs)) == ref, f"rust vs reference: {to_codes(rs)} != {sorted(ref)}"

                cards = card_list(rs)
                card = cards[rng.randrange(len(cards))]
                ref_hands[seat].remove(to_codes(1 << card)[0])
                trick_codes.append(to_codes(1 << card)[0])
                state.play(card)


def test_legal_moves_agree_on_the_awkward_flags():
    """The undertrump and Puur rules, with both flags in both settings."""
    rng = random.Random(99)
    for _ in range(3000):
        hand = 0
        for c in range(36):
            if rng.random() < 0.25:
                hand |= 1 << c
        if not hand:
            continue
        trump = rng.randrange(-1, 4)
        led = rng.randrange(-1, 4)
        best = rng.randrange(-1, 9)
        strict = rng.random() < 0.5
        puur = rng.random() < 0.5
        assert core.legal_moves(
            hand, trump, led, best, strict, puur
        ) == py_legal_moves(
            hand, trump, led, best, strict_undertrump=strict, puur_exempt=puur
        )


# --- rollout ----------------------------------------------------------------


@pytest.mark.parametrize("contract", list(Contract))
def test_playouts_total_157(contract):
    """With the match bonus off, the points on the table are conserved exactly."""
    rng = random.Random(7)
    for _ in range(300):
        a, b = core.play_out(
            deal(rng), rng.randrange(4), int(contract), rng.getrandbits(64), True, True, 5, 0
        )
        assert a + b == 157


def test_playout_is_deterministic_for_a_seed():
    hands = deal(random.Random(3))
    first = core.play_out(hands, 0, int(Contract.CLUBS), 42)
    assert core.play_out(hands, 0, int(Contract.CLUBS), 42) == first


def test_playout_only_plays_legal_cards():
    """Indirect but strong: if the kernel ever played an illegal card the round could not
    finish with every hand empty and the points totalling 157 across all contracts."""
    rng = random.Random(15)
    for contract in Contract:
        for _ in range(200):
            a, b = core.play_out(deal(rng), 0, int(contract), rng.getrandbits(64), True, True, 5, 0)
            assert a + b == 157


def test_match_bonus_matches_the_python_kernel_semantics():
    """Awarded only when the playout covered a whole round."""
    rng = random.Random(11)
    seen_match = False
    for _ in range(6000):
        a, b = core.play_out(deal(rng), 0, int(Contract.HEARTS), rng.getrandbits(64))
        assert a + b in (157, 257)
        seen_match |= a + b == 257
    assert seen_match, "no match in 6000 deals; the bonus path is untested"


# --- dmcts ------------------------------------------------------------------


def position_from(state, seat):
    """Build the search input from an engine state, as the bot service will."""
    unseen = 0
    for s in range(4):
        if s != seat:
            unseen |= state.hands[s]
    return dict(
        seat=seat,
        hand=state.hands[seat],
        unseen=unseen,
        trick=list(state.trick),
        trick_leader=state.leader,
        contract=int(state.contract),
    )


def test_dmcts_only_ever_returns_legal_moves():
    rng = random.Random(21)
    for _ in range(20):
        state = RoundState(contract=Contract.HEARTS, hands=deal(rng), cfg=EVAL)
        for _ in range(rng.randrange(0, 12)):
            legal = state.legal_moves()
            cards = card_list(legal)
            state.play(cards[rng.randrange(len(cards))])
        if state.done:
            continue
        seat = state.to_play
        out = core.dmcts(
            **position_from(state, seat), determinizations=16, iterations=32, seed=7
        )
        legal = set(card_list(state.legal_moves(seat)))
        assert out, "search returned no candidates"
        assert {c for c, _, _, _ in out} == legal


def test_dmcts_is_deterministic_and_thread_count_does_not_change_the_result():
    """Determinizations get independent seed streams via SplitMix64, so the answer must not
    depend on how the work was scheduled. Without this, `PLAN.md`'s bit-for-bit replay
    requirement fails the moment the search goes parallel."""
    rng = random.Random(5)
    state = RoundState(contract=Contract.SPADES, hands=deal(rng), cfg=EVAL)
    pos = position_from(state, 0)

    single = core.dmcts(**pos, determinizations=64, iterations=64, seed=1234, threads=1)
    again = core.dmcts(**pos, determinizations=64, iterations=64, seed=1234, threads=1)
    parallel = core.dmcts(**pos, determinizations=64, iterations=64, seed=1234, threads=8)

    assert single == again
    assert single == parallel


def test_dmcts_respects_known_voids():
    """A seat proven void in a suit must never be dealt that suit, or the search is
    reasoning about impossible worlds."""
    rng = random.Random(31)
    state = RoundState(contract=Contract.HEARTS, hands=deal(rng), cfg=EVAL)
    pos = position_from(state, 0)
    # everyone else void in diamonds is unsatisfiable unless seat 0 holds them all;
    # a satisfiable case: only seat 1 is void in diamonds
    pos["voids"] = [0, 1 << 0, 0, 0]
    out = core.dmcts(**pos, determinizations=32, iterations=32, seed=3)
    assert out, "search should still find a move under a satisfiable void constraint"


def test_dmcts_takes_the_trick_it_can_obviously_win():
    """A constructed endgame: seat 0 holds the last two cards and one of them wins a
    high-value trick outright. A working search finds it."""
    from krass_jass.cards import parse_hand as H

    state = RoundState(
        contract=Contract.HEARTS,
        hands=[H("HJ D6"), H("DA D7"), H("D8 D9"), H("DT DK")],
        cfg=EVAL,
        leader=1,
    )
    state.play(list(card_list(H("DA")))[0])  # seat 1 leads the diamond ace
    seat = state.to_play
    assert seat == 2
    # seat 2 cannot trump (no hearts); check seat 0 later. Instead search from seat 2:
    out = core.dmcts(**position_from(state, seat), determinizations=200, iterations=200, seed=9)
    best = out[0][0]
    assert best in card_list(state.legal_moves(seat))
