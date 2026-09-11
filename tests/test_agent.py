"""Agents and the arena. Mostly guarding invariants the arena would otherwise hide."""

import random

import pytest

from arena.arena import double_round, match, paired_test, play_round
from krass_jass.agent import DmctsAgent, GreedyAgent, RandomAgent
from krass_jass.cards import card_list
from krass_jass.observation import build_observation
from krass_jass.rules import EVAL, Contract
from krass_jass.state import RoundState
from krass_jass.tables import CARD_VALUES

pytest.importorskip("krass_jass_core", reason="Rust core not built")


def deal(rng):
    deck = list(range(36))
    rng.shuffle(deck)
    return [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]


def agents():
    return [
        RandomAgent(),
        GreedyAgent(),
        DmctsAgent(determinizations=8, iterations=16, cfg=EVAL),
    ]


@pytest.mark.parametrize("agent", agents(), ids=lambda a: a.name)
def test_agents_only_return_legal_moves(agent):
    rng = random.Random(4)
    for _ in range(6):
        state = RoundState(contract=Contract(rng.randrange(6)), hands=deal(rng), cfg=EVAL)
        while not state.done:
            obs = build_observation(state, decision_seed=rng.getrandbits(64))
            card = agent.decide(obs)
            assert obs.legal_moves & (1 << card), f"{agent.name} returned an illegal move"
            state.play(card)


def test_greedy_takes_the_highest_value_legal_card():
    rng = random.Random(8)
    state = RoundState(contract=Contract.HEARTS, hands=deal(rng), cfg=EVAL)
    obs = build_observation(state)
    values = CARD_VALUES[Contract.HEARTS]
    chosen = GreedyAgent().decide(obs)
    assert values[chosen] == max(values[c] for c in card_list(obs.legal_moves))


def test_dmcts_skips_the_search_when_there_is_no_choice():
    """One legal move means no decision. Burning a full search budget on it would waste
    most of a round's think time in the late tricks, where hands are usually forced."""
    from krass_jass.cards import parse_hand as H

    state = RoundState(
        contract=Contract.HEARTS,
        hands=[H("S7"), H("SA"), H("SK"), H("SQ")],
        cfg=EVAL,
        leader=1,
    )
    state.play(card_list(state.legal_moves())[0])
    obs = build_observation(state, 2)
    assert obs.legal_moves.bit_count() == 1
    huge = DmctsAgent(determinizations=10**6, iterations=10**6, cfg=EVAL)
    assert huge.decide(obs) == card_list(obs.legal_moves)[0]


def test_round_points_are_conserved():
    rng = random.Random(12)
    a, b = RandomAgent(), GreedyAgent()
    total = play_round(
        deal(rng), Contract.SPADES, 0, {0: a, 1: b, 2: a, 3: b}, EVAL, game_seed=5
    )
    assert sum(total) == 157


def test_double_round_shares_sum_to_one():
    rng = random.Random(13)
    a_share, b_share = double_round(
        deal(rng), Contract.CLUBS, 0, RandomAgent(), GreedyAgent(), EVAL, game_seed=9
    )
    assert abs(a_share + b_share - 1.0) < 1e-9


def test_double_round_swaps_the_agents():
    """The point of a double round is that the same deal is played from both sides. An
    agent playing itself must therefore score exactly half, every time, with no variance —
    which is the sharpest possible check that the swap really happens."""
    rng = random.Random(21)
    for _ in range(5):
        a_share, _ = double_round(
            deal(rng), Contract.HEARTS, rng.randrange(4),
            RandomAgent(), RandomAgent(), EVAL, game_seed=rng.getrandbits(32),
        )
        assert a_share == pytest.approx(0.5), "self-play must be exactly even under a swap"


def test_matches_are_reproducible():
    a = DmctsAgent(determinizations=4, iterations=8, cfg=EVAL)
    b = GreedyAgent()
    first = match(a, b, deals=3, seed=77)
    second = match(a, b, deals=3, seed=77)
    assert first.a_share == second.a_share


def test_paired_test_detects_a_real_shift_and_ignores_noise():
    assert paired_test([0.0] * 50)[1] == 1.0
    _, p = paired_test([0.1] * 50)
    assert p < 0.001
    rng = random.Random(1)
    _, p_noise = paired_test([rng.gauss(0, 0.1) for _ in range(200)])
    assert p_noise > 0.05


def test_dmcts_beats_random_convincingly():
    """The end-to-end claim. Small budget, few deals — but if this ever stops holding,
    something upstream is badly wrong."""
    result = match(
        DmctsAgent(determinizations=24, iterations=48, cfg=EVAL),
        RandomAgent(),
        deals=12,
        seed=3,
    )
    assert result.a_share > 0.55, f"dmcts only took {result.a_share:.1%} against random"


def test_parallel_matches_are_identical_to_serial():
    """Parallelism must not change the answer. Every deal's setup and seeds come from
    (seed, index), so process count only affects how long it takes."""
    a = DmctsAgent(determinizations=4, iterations=8, cfg=EVAL)
    b = GreedyAgent()
    serial = match(a, b, deals=8, seed=5, workers=1)
    parallel = match(a, b, deals=8, seed=5, workers=4)
    assert serial.a_share == parallel.a_share
    assert serial.std == parallel.std


def test_the_endgame_solve_is_reached_whichever_search_is_selected():
    """ISMCTS does not own an endgame branch — positions below the threshold are routed to
    the exact double-dummy solve that `dmcts` already has.

    The solve is exact, so both searches must return *identical* candidates there. If this
    ever diverges, ISMCTS has grown its own endgame by accident.
    """
    from krass_jass.agent import DmctsAgent
    from krass_jass.game import Game, Phase
    from krass_jass.rules import EVAL

    ism = DmctsAgent(determinizations=20, iterations=20, cfg=EVAL, endgame_cards=5, ismcts=True)
    dmc = DmctsAgent(determinizations=20, iterations=20, cfg=EVAL, endgame_cards=5, ismcts=False)

    game = Game(cfg=EVAL.variant(target_score=None), seed=11)
    guard = 0
    while game.phase is Phase.BIDDING and guard < 6:
        seat = game.to_act
        game.bid(seat, ism.select_trump(game.hand_of(seat), seat == game.forehand))
        guard += 1
    assert game.phase is Phase.PLAYING

    checked = 0
    while game.round is not None and not game.round.done:
        seat = game.to_act
        obs = game.observation(seat)
        if bin(obs.hand).count("1") <= 5:
            assert ism.trace(obs) == dmc.trace(obs), "the endgame solve must not depend on it"
            checked += 1
        game.play(seat, ism.decide(obs))
    assert checked > 0, "the round never reached the endgame threshold"
