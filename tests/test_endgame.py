"""The endgame solver claims to be exact, so it is checked against brute force.

The reference solver below is plain minimax with no pruning, written on top of
`tests/reference.py` — so it shares no code with the Rust alpha-beta. If they agree on
every position, the pruning is sound.
"""

import random
from functools import lru_cache

import pytest

from krass_jass.cards import card_list, format_card
from krass_jass.rules import Contract
from krass_jass.tables import CARD_VALUES
from tests import reference
from tests.helpers import CONTRACT_CODES, to_codes

core = pytest.importorskip("krass_jass_core", reason="Rust core not built")

LAST_TRICK = 5


def brute_force(hands, trick, leader, contract):
    """Exact team-0 points under perfect information. Minimax, no pruning, no cleverness."""

    @lru_cache(maxsize=None)
    def go(hands_key, trick_key, leader):
        hands = [list(h) for h in hands_key]
        trick = list(trick_key)
        if not trick and not any(hands):
            return 0
        to_play = (leader + len(trick)) % 4
        legal = sorted(reference.legal(hands[to_play], contract, trick))
        maximizing = to_play % 2 == 0
        best = None
        for card in legal:
            nh = [list(h) for h in hands]
            nh[to_play].remove(card)
            nt = trick + [card]
            if len(nt) == 4:
                winner = (leader + reference.winner_index(nt, contract)) % 4
                pts = sum(reference.card_value(c, contract) for c in nt)
                done = not any(nh)
                if done:
                    pts += LAST_TRICK
                gained = pts if winner % 2 == 0 else 0
                sub = 0 if done else go(tuple(tuple(sorted(h)) for h in nh), (), winner)
                value = gained + sub
            else:
                value = go(tuple(tuple(sorted(h)) for h in nh), tuple(nt), leader)
            if best is None or (value > best if maximizing else value < best):
                best = value
        return best

    return go(tuple(tuple(sorted(h)) for h in hands), tuple(trick), leader)


def random_endgame(rng, cards_each):
    """A legal position with `cards_each` cards in every hand."""
    deck = list(range(36))
    rng.shuffle(deck)
    return [
        sum(1 << c for c in deck[i * cards_each : (i + 1) * cards_each]) for i in range(4)
    ]


@pytest.mark.parametrize("contract", list(Contract))
@pytest.mark.parametrize("cards_each", [1, 2, 3])
def test_matches_brute_force(contract, cards_each):
    rng = random.Random(1000 + int(contract) * 10 + cards_each)
    code = CONTRACT_CODES[contract]
    for _ in range(12):
        hands = random_endgame(rng, cards_each)
        leader = rng.randrange(4)
        got, _ = core.solve_endgame(hands, [], leader, int(contract))
        want = brute_force([to_codes(h) for h in hands], [], leader, code)
        assert got == want, f"{[to_codes(h) for h in hands]} leader={leader} {code}"


@pytest.mark.parametrize("contract", [Contract.HEARTS, Contract.OBENABE, Contract.UNDENUFE])
def test_matches_brute_force_mid_trick(contract):
    """The solver has to handle being called with a trick already in progress."""
    rng = random.Random(55 + int(contract))
    code = CONTRACT_CODES[contract]
    for _ in range(12):
        hands = random_endgame(rng, 2)
        leader = rng.randrange(4)
        # play one legal card into the trick
        seat = leader
        legal = card_list(
            core.legal_moves(hands[seat], contract.trump_suit, -1, -1)
        )
        card = legal[rng.randrange(len(legal))]
        hands[seat] ^= 1 << card

        got, _ = core.solve_endgame(hands, [card], leader, int(contract))
        want = brute_force(
            [to_codes(h) for h in hands], [format_card(card)], leader, code
        )
        assert got == want


@pytest.mark.parametrize("contract", list(Contract))
def test_points_are_conserved(contract):
    """Team 0's exact take plus team 1's must equal everything on the table."""
    rng = random.Random(int(contract) + 400)
    values = CARD_VALUES[contract]
    for _ in range(20):
        hands = random_endgame(rng, 4)
        total = sum(values[c] for h in hands for c in card_list(h)) + LAST_TRICK
        team0, _ = core.solve_endgame(hands, [], 0, int(contract))
        assert 0 <= team0 <= total


def test_cost_is_affordable_once_per_determinization():
    """Cost governs *where* the solver is used, so it is pinned here.

    Roughly 15x per extra card: 4 cards ~0.2ms, 5 cards ~3ms. Far too slow per MCTS leaf
    (800k leaves would be forty minutes), which is why `dmcts` replaces the whole search
    with one solve per determinization once the round is small enough.
    """
    rng = random.Random(3)
    nodes = sorted(
        core.solve_endgame(random_endgame(rng, 5), [], 0, int(Contract.HEARTS))[1]
        for _ in range(40)
    )
    median = nodes[len(nodes) // 2]
    assert median < 250_000, f"median {median} nodes per 5-card solve"


def test_dmcts_uses_the_exact_solver_in_the_endgame():
    """Every candidate gets exactly one certain evaluation per determinization, rather than
    a pile of sampled visits — the signature that the search was replaced, not decorated."""
    rng = random.Random(17)
    hands = random_endgame(rng, 3)
    dets = 50
    out = core.dmcts(
        seat=0,
        hand=hands[0],
        unseen=hands[1] | hands[2] | hands[3],
        trick=[],
        trick_leader=0,
        contract=int(Contract.HEARTS),
        determinizations=dets,
        iterations=999_999,  # would be ruinous if MCTS actually ran
        endgame_cards=5,
        seed=4,
    )
    assert all(visits == dets for _, visits, _, _ in out)
    assert sum(sel for _, _, _, sel in out) == dets


def test_dmcts_endgame_finds_the_dominant_move():
    """Seat 0 holds the trump Puur and a worthless card, and a fat trick is on the table.
    Trumping is correct in every possible world, so the search must find it whatever the
    unseen cards turn out to be."""
    from krass_jass.cards import parse_card, parse_hand as H
    from krass_jass.rules import EVAL
    from krass_jass.state import RoundState

    # Built through the engine so the trick, the turn order and the unseen set are
    # consistent — assembling them by hand is how you end up searching from a seat that is
    # not even on turn.
    state = RoundState(
        contract=Contract.HEARTS,
        hands=[H("HJ D6"), H("CA C7"), H("SA S8"), H("DA S7")],
        cfg=EVAL,
        leader=3,
    )
    state.play(parse_card("DA"))
    assert state.to_play == 0

    out = core.dmcts(
        seat=0,
        hand=state.hands[0],
        unseen=state.hands[1] | state.hands[2] | state.hands[3],
        trick=list(state.trick),
        trick_leader=state.leader,
        contract=int(Contract.HEARTS),
        determinizations=100,
        iterations=200,
        endgame_cards=5,
        seed=8,
    )
    assert out[0][0] == parse_card("HJ"), "should trump the led ace with the Puur"
