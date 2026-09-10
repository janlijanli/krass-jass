"""The ported rules must agree with the Python they replace, on randomised input.

This is the same safety argument that made the search port defensible. The Python side is
itself checked against `tests/reference.py`, which was written from the rules text and
imports neither implementation — so agreement here is agreement with an independent reading,
not two copies of the same mistake.

Weis gets the most attention because it is the largest and the one with a real optimiser in
it. Two of the three bugs found while writing the Python version were in Weis.
"""

import random

import pytest

from krass_jass.cards import SUIT_MASK, card_list, parse_hand
from krass_jass.rules import DEFAULT_MULTIPLIERS, HOUSE, SHOVE, Contract
from krass_jass.scoring import score_round
from krass_jass.trump import score_all, select_trump
from krass_jass.voids import infer_forbidden
from krass_jass.weis import find_weis, score_stoeck, score_weis

core = pytest.importorskip("krass_jass_core", reason="Rust core not built")

MULTS = [DEFAULT_MULTIPLIERS[Contract(i)] for i in range(6)]


def random_hand(rng, n=9):
    deck = list(range(36))
    rng.shuffle(deck)
    return sum(1 << c for c in deck[:n])


def deal(rng):
    deck = list(range(36))
    rng.shuffle(deck)
    return [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]


# --- Weis -------------------------------------------------------------------


@pytest.mark.parametrize("large", [False, True])
def test_find_weis_agrees(large):
    """Both the total and the *chosen melds* must match — a different set scoring the same
    still loses the comparison against another team, so 'same points' is not enough."""
    cfg = HOUSE.variant(weis_large=large)
    rng = random.Random(7 if large else 3)
    for _ in range(600):
        hand = random_hand(rng)
        py = sorted(
            (m.points, m.cards, m.length, m.top_rank, m.kind.value)
            for m in find_weis(hand, cfg, trump=1)
        )
        rs = sorted(
            (points, cards, length, top, kind)
            for kind, points, cards, length, top, _suit in core.rs_find_weis(
                hand, 1, large, True, True
            )
        )
        assert py == rs, f"hand={card_list(hand)} large={large}"


def test_find_weis_agrees_on_the_awkward_hands():
    """The cases that caught bugs in the Python implementation."""
    cases = [
        "DJ HJ SJ CJ DA DK DQ S7 S6",   # four jacks vs a sequence sharing the DJ
        "DA DK DQ DJ DT D9 D8 D7 D6",   # a run of nine — must not split
        "DA DK DQ HA HK HQ S6 S7 C9",
        "D9 H9 S9 C9 DA S7 H8 CK D6",
        "HJ HT H9 DA S7 C8 CK D6 D7",   # sequence order ignores the trump order
    ]
    for large in (False, True):
        cfg = HOUSE.variant(weis_large=large)
        for text in cases:
            hand = parse_hand(text)
            py = sum(m.points for m in find_weis(hand, cfg, trump=1))
            rs = sum(m[1] for m in core.rs_find_weis(hand, 1, large, True, True))
            assert py == rs, f"{text} large={large}: python {py}, rust {rs}"


@pytest.mark.parametrize("four_nines", [True, False])
def test_score_weis_agrees(four_nines):
    cfg = HOUSE.variant(weis_four_nines=four_nines)
    rng = random.Random(11)
    for _ in range(400):
        hands = deal(rng)
        trump = rng.randrange(-1, 4)
        forehand = rng.randrange(4)
        py_points, py_winner = score_weis(hands, trump, cfg, forehand)
        rs_points, rs_winner = core.rs_score_weis(hands, trump, forehand, False, four_nines, True)
        assert tuple(py_points) == rs_points
        assert py_winner == rs_winner


def test_score_stoeck_agrees():
    rng = random.Random(5)
    for _ in range(300):
        hands = deal(rng)
        trump = rng.randrange(-1, 4)
        assert tuple(score_stoeck(hands, trump, HOUSE)) == core.rs_score_stoeck(hands, trump, True)
        assert core.rs_score_stoeck(hands, trump, False) == (0, 0)


# --- scoring ----------------------------------------------------------------


@pytest.mark.parametrize("contract", list(Contract))
def test_score_round_agrees(contract):
    rng = random.Random(int(contract) + 40)
    for _ in range(200):
        a = rng.randrange(0, 153)
        tricks_a = rng.randrange(0, 10)
        weis = (rng.choice([0, 20, 50, 100, 200]), rng.choice([0, 20, 100]))
        stoeck = (rng.choice([0, 20]), rng.choice([0, 20]))
        last = rng.randrange(4)

        py = score_round(
            (a, 152 - a), (tricks_a, 9 - tricks_a), last, contract, HOUSE, weis, stoeck
        )
        rs = core.rs_score_round(
            (a, 152 - a), (tricks_a, 9 - tricks_a), last, int(contract), weis, stoeck, MULTS
        )
        assert tuple(py.trick_points) == rs[0]
        assert tuple(py.last_trick) == rs[1]
        assert tuple(py.match) == rs[2]
        assert tuple(py.weis) == rs[3]
        assert tuple(py.stoeck) == rs[4]
        assert py.multiplier == rs[5]
        assert tuple(py.total) == rs[6]


def test_claim_sequence_agrees():
    """The ordering decides who wins a simultaneous finish, so a divergence here would show
    up as the wrong team winning rather than as wrong totals."""
    from krass_jass.game import Game

    rng = random.Random(23)
    for _ in range(150):
        contract = Contract(rng.randrange(6))
        trick_results = [(rng.randrange(4), rng.randrange(0, 40)) for _ in range(9)]
        weis = (rng.choice([0, 20, 100]), rng.choice([0, 50]))
        stoeck = (rng.choice([0, 20]), rng.choice([0, 20]))
        a = rng.randrange(0, 153)
        tricks_a = rng.randrange(0, 10)

        score = score_round(
            (a, 152 - a), (tricks_a, 9 - tricks_a), 0, contract, HOUSE, weis, stoeck
        )
        game = Game.__new__(Game)
        game.cfg = HOUSE
        game.contract = contract

        class Round:
            pass

        Round.trick_results = trick_results
        game.round = Round()
        py = game._claim_sequence(score)
        rs = core.rs_claim_sequence(
            (a, 152 - a), (tricks_a, 9 - tricks_a), 0, int(contract), trick_results,
            weis, stoeck, MULTS,
        )
        assert py == [tuple(x) for x in rs]


# --- voids ------------------------------------------------------------------


@pytest.mark.parametrize("contract", list(Contract))
def test_void_inference_agrees_over_whole_rounds(contract):
    from krass_jass.rules import EVAL
    from krass_jass.state import RoundState

    rng = random.Random(int(contract) * 7 + 1)
    for _ in range(25):
        state = RoundState(contract=contract, hands=deal(rng), cfg=EVAL, leader=rng.randrange(4))
        while not state.done:
            py = infer_forbidden(
                state.tricks_played, state.trick, state.leader, contract, EVAL
            )
            rs = core.rs_infer_forbidden(
                [(leader, list(cards)) for leader, cards in state.tricks_played],
                list(state.trick),
                state.leader,
                contract.trump_suit,
                True,
            )
            assert py == rs
            legal = card_list(state.legal_moves())
            state.play(legal[rng.randrange(len(legal))])


def test_void_inference_agrees_without_the_puur_exemption():
    from krass_jass.rules import EVAL
    from krass_jass.state import RoundState

    cfg = EVAL.variant(puur_exempt_trump_lead=False)
    rng = random.Random(99)
    for _ in range(25):
        state = RoundState(contract=Contract.HEARTS, hands=deal(rng), cfg=cfg, leader=0)
        while not state.done:
            py = infer_forbidden(
                state.tricks_played, state.trick, state.leader, Contract.HEARTS, cfg
            )
            rs = core.rs_infer_forbidden(
                [(leader, list(cards)) for leader, cards in state.tricks_played],
                list(state.trick), state.leader, 1, False,
            )
            assert py == rs
            legal = card_list(state.legal_moves())
            state.play(legal[rng.randrange(len(legal))])


# --- trump selection --------------------------------------------------------


def test_trump_scores_agree():
    """Weights are compiled into Rust from the same JSON Python reads, so a drift between
    them means someone edited one and not the other."""
    rng = random.Random(31)
    for _ in range(500):
        hand = random_hand(rng)
        py = score_all(hand, HOUSE)
        rs = core.rs_trump_scores(hand, MULTS)
        for contract in Contract:
            assert py[contract] == pytest.approx(rs[int(contract)], abs=1e-9), (
                f"{contract.name}: python {py[contract]}, rust {rs[int(contract)]}"
            )


@pytest.mark.parametrize("is_forehand", [True, False])
def test_trump_selection_agrees(is_forehand):
    rng = random.Random(17)
    shoves = 0
    for _ in range(500):
        hand = random_hand(rng)
        py = select_trump(hand, is_forehand, HOUSE)
        rs = core.rs_select_trump(hand, is_forehand, MULTS)
        if py == SHOVE:
            shoves += 1
            assert rs == -1
        else:
            assert int(py) == rs, f"python {py.name}, rust index {rs}"
    if is_forehand:
        assert shoves > 0, "the shove path was never exercised"
    else:
        assert shoves == 0


# --- round state ------------------------------------------------------------


@pytest.mark.parametrize("contract", list(Contract))
def test_round_state_agrees_ply_by_ply(contract):
    """Replay the same round through both and compare at every ply, not just at the end —
    a divergence that happens to land in the same place would otherwise go unseen."""
    from krass_jass.rules import EVAL
    from krass_jass.state import RoundState

    rng = random.Random(int(contract) * 13 + 5)
    for _ in range(30):
        hands = deal(rng)
        leader = rng.randrange(4)
        state = RoundState(contract=contract, hands=list(hands), cfg=EVAL, leader=leader)

        played = []
        py_legal = []
        while not state.done:
            py_legal.append(state.legal_moves())
            legal = card_list(state.legal_moves())
            card = legal[rng.randrange(len(legal))]
            played.append(card)
            state.play(card)

        rs_hands, rs_points, rs_won, rs_last, rs_results, rs_legal = core.rs_replay_round(
            int(contract), hands, leader, played
        )
        assert rs_legal == py_legal, "legal moves diverged mid-round"
        assert rs_hands == state.hands
        assert rs_points == tuple(state.trick_points)
        assert rs_won == tuple(state.tricks_won)
        assert rs_last == state.last_trick_winner
        assert [tuple(r) for r in rs_results] == state.trick_results
        assert sum(rs_points) == 152


def test_the_rust_round_refuses_an_illegal_card():
    """The engine is authoritative on both sides. A port that accepted an illegal move would
    be a hole rather than a difference."""
    from krass_jass.rules import EVAL
    from krass_jass.state import RoundState

    rng = random.Random(4)
    hands = deal(rng)
    state = RoundState(contract=Contract.HEARTS, hands=list(hands), cfg=EVAL, leader=0)
    seat = state.to_play
    illegal = card_list(state.hands[seat] ^ state.legal_moves(seat))
    if not illegal:
        pytest.skip("this deal has no illegal card in hand to try")
    with pytest.raises(ValueError):
        core.rs_replay_round(int(Contract.HEARTS), hands, 0, [illegal[0]])
