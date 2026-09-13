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


def test_the_round_arena_is_unchanged_when_weis_is_off():
    """Weis came to the round-level arena late, and every figure in `docs/measurements.md`
    predates it. `EVAL` switches Weis off, so the whole existing instrument has to be provably
    inert under the new code — not merely similar.
    """
    import random

    from arena.arena import resolve_weis
    from krass_jass.cards import card_list
    from krass_jass.rules import EVAL, Contract
    from krass_jass.state import RoundState

    rng = random.Random(3)
    for _ in range(80):
        deck = list(range(36))
        rng.shuffle(deck)
        hands = [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]
        contract = Contract(rng.randrange(6))
        leader = rng.randrange(4)

        assert resolve_weis(hands, contract, leader, EVAL) == ((0, 0), (0, 0), (), ())

        a = RoundState(contract=contract, hands=list(hands), cfg=EVAL, leader=leader)
        b = RoundState(contract=contract, hands=list(hands), cfg=EVAL, leader=leader)
        while not a.done:
            card = card_list(a.legal_moves())[0]
            a.play(card)
            b.play(card)
        assert a.score().total == b.score(weis=(0, 0), stoeck=(0, 0)).total


def test_a_shown_weis_is_really_in_the_hand_that_showed_it():
    """`known_cards` pins cards to a seat, so a wrong one would have the search reasoning
    about worlds that cannot exist — the exact failure `voids.py` is careful to avoid."""
    import random

    from arena.arena import resolve_weis
    from krass_jass.rules import HOUSE, Contract

    rng = random.Random(11)
    checked = 0
    for _ in range(120):
        deck = list(range(36))
        rng.shuffle(deck)
        hands = [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]
        contract = Contract(rng.randrange(6))
        _weis, _stoeck, shown, _called = resolve_weis(hands, contract, rng.randrange(4), HOUSE)
        for seat, card in shown:
            assert hands[seat] & (1 << card), "shown a card that seat does not hold"
            checked += 1
    assert checked > 0, "no Weis was ever shown; the fixture proves nothing"


def test_a_call_is_published_only_once_the_table_has_heard_it():
    """Silence is a claim — but only after the seat has had its turn to make it.

    Before the calls are in, a seat that has said nothing has not said "nothing", and
    handing the search a zero would be a constraint the table never heard. A seat that
    *declines* is the other half: the table heard "nothing" and so does the search, which
    is the whole point of declining.
    """
    from krass_jass.cards import card_list, parse_hand as H
    from krass_jass.game import Game, Phase
    from krass_jass.rules import HOUSE

    game = Game(cfg=HOUSE.variant(weis_manual=True), seed=2)
    game._dealt = [
        H("DK DQ DA D9 D8 S6 S7 H6 H7"),   # 20
        H("SA SK SQ SJ ST S9 S8 H8 H9"),   # 100
        H("CA CK CQ CJ CT C9 C8 C7 C6"),   # 100, the best — and it will decline
        H("DJ DT D7 D6 HA HK HQ HJ HT"),   # 100
    ]
    game.forehand = 0
    game.declarer = 0
    game.bid(0, "DIAMONDS")

    assert game.phase is Phase.WEIS
    assert game._announced() == (), "a call was published before anybody made it"

    for _ in range(4):
        seat = game.to_act
        if game.phase is Phase.WEIS:
            game.choose_weis(seat, seat != 2)
        game.play(seat, card_list(game.round.legal_moves(seat))[0])

    called = game._announced()
    assert [seat for seat, _ in called] == [0, 1, 2, 3], "every seat has to be accounted for"
    assert dict(called)[2] == 0, "a declined Weis is a call of nothing, not a hidden one"
    assert dict(called)[0] == 20


def test_what_a_seat_called_is_true_of_the_hand_it_was_dealt():
    """The call is the predicate the search filters worlds with, so a call the dealt hand
    would not have made would have it rejecting the *real* world.

    The reconstruction matters as much as the value: a call is about the nine cards dealt,
    and a world imagined in trick five is missing some of them.
    """
    import random

    from arena.arena import resolve_weis
    from krass_jass.rules import HOUSE, Contract
    from krass_jass.weis import find_weis

    rng = random.Random(29)
    positive = 0
    for _ in range(150):
        deck = list(range(36))
        rng.shuffle(deck)
        hands = [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]
        contract = Contract(rng.randrange(6))
        trump = contract.trump_suit if contract.is_trump else -1
        *_rest, called = resolve_weis(hands, contract, rng.randrange(4), HOUSE)
        for seat, points in called:
            assert points == sum(m.points for m in find_weis(hands[seat], HOUSE, trump))
            positive += points > 0
    assert positive > 0, "nobody ever called; the fixture proves nothing"


def test_a_seat_is_never_asked_to_explain_a_card_it_has_played():
    """`played_by` is what puts a mid-round world back together before it is tested against
    a call. It must be exactly the public history, split by who played what."""
    import random

    from krass_jass.observation import build_observation
    from krass_jass.rules import EVAL, Contract
    from krass_jass.state import RoundState
    from krass_jass.cards import card_list

    rng = random.Random(5)
    for _ in range(30):
        deck = list(range(36))
        rng.shuffle(deck)
        hands = [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]
        state = RoundState(
            contract=Contract(rng.randrange(6)), hands=list(hands), cfg=EVAL, leader=rng.randrange(4)
        )
        dealt = list(hands)
        while not state.done:
            obs = build_observation(state, state.to_play)
            by_seat = obs.played_by
            assert sum(bin(m).count("1") for m in by_seat) == bin(obs.played).count("1")
            for seat in range(4):
                assert by_seat[seat] | state.hands[seat] == dealt[seat]
                assert by_seat[seat] & state.hands[seat] == 0
            state.play(card_list(state.legal_moves())[0])


def test_the_search_sees_no_calls_when_weis_is_off():
    """Every figure in `docs/measurements.md` before §5m was taken under `EVAL`, where Weis
    does not exist. The new belief has to be provably absent there, not merely quiet."""
    import random

    from arena.arena import resolve_weis
    from krass_jass.agent import DmctsAgent
    from krass_jass.observation import build_observation
    from krass_jass.rules import EVAL, Contract
    from krass_jass.state import RoundState

    rng = random.Random(17)
    for _ in range(20):
        deck = list(range(36))
        rng.shuffle(deck)
        hands = [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]
        contract = Contract(rng.randrange(6))
        assert resolve_weis(hands, contract, 0, EVAL)[3] == ()
        state = RoundState(contract=contract, hands=list(hands), cfg=EVAL, leader=0)
        obs = build_observation(state, state.to_play)
        assert obs.weis_announced == ()
        agent = DmctsAgent(determinizations=2, iterations=8, cfg=EVAL)
        assert agent._beliefs(obs)[1] == {}, "a belief arrived where there is no Weis"
