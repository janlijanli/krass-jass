"""Reading the table, and what the reading is allowed to do to the search.

Two properties, and the second is the one that matters. A signal may make a world *likelier*;
it must never make one impossible. `voids.py` removes worlds because it has proof; this has a
convention and a guess, and a human who ignores the convention must cost the search sampling
efficiency and nothing else.
"""

import pytest

from krass_jass.cards import SUIT_MASK, card_list, parse_card, parse_hand
from krass_jass.reading import LIMIT, infer_affinity, sister
from krass_jass.rules import Contract

core = pytest.importorskip("krass_jass_core", reason="Rust core not built")

HEARTS, CLUBS = Contract.HEARTS, Contract.CLUBS
H, D, S, C = 1, 0, 2, 3   # suit indices


def trick(leader, *cards):
    return (leader, tuple(parse_card(c) for c in cards))


def test_the_sister_of_a_discard_is_what_it_asks_for():
    assert sister(H) == D and sister(D) == H
    assert sister(S) == C and sister(C) == S


def test_a_lead_says_nothing():
    """Leading a suit is a choice about this trick, not a message about your hand."""
    affinity = infer_affinity([trick(0, "SA", "S6", "S7", "S8")], [], 0, CLUBS)
    assert affinity == [[0] * 4 for _ in range(4)]


def test_a_discard_asks_for_the_sister_suit():
    # Clubs are trump; spades led; seat 1 throws a diamond, which is neither.
    affinity = infer_affinity([trick(0, "SA", "D6", "S7", "S8")], [], 0, CLUBS)
    assert affinity[1][D] == -1, "short in what it threw"
    assert affinity[1][H] == +1, "asking for the sister"
    assert affinity[0] == [0, 0, 0, 0], "the leader said nothing"
    assert affinity[2] == [0, 0, 0, 0] and affinity[3] == [0, 0, 0, 0]


def test_following_and_trumping_are_not_discards():
    """Trumping is legal whether or not you could follow, so it proves and suggests nothing —
    the same trap `voids.py` documents."""
    affinity = infer_affinity([trick(0, "SA", "S6", "CA", "S8")], [], 0, CLUBS)
    assert affinity == [[0] * 4 for _ in range(4)], "a trump is not a message"


def test_the_reading_is_bounded():
    """Repeating a discard is evidence; repeating it five times is having run out of cards."""
    tricks = [trick(0, "SA", "D6", "S7", "S8"),
              trick(0, "SK", "D7", "S9", "ST"),
              trick(0, "SQ", "D8", "SJ", "H6"),
              trick(0, "H7", "D9", "H8", "H9")]
    affinity = infer_affinity(tricks, [], 0, CLUBS)
    assert affinity[1][D] == -LIMIT
    assert affinity[1][H] == +LIMIT


def test_python_and_rust_read_the_same_table():
    tricks = [trick(0, "SA", "D6", "S7", "S8"), trick(2, "H6", "CA", "H8", "D9")]
    mine = infer_affinity(tricks, [parse_card("SK")], 1, CLUBS)
    theirs = core.rs_infer_affinity(
        [(leader, list(cards)) for leader, cards in tricks],
        [parse_card("SK")], 1, CLUBS.trump_suit,
    )
    assert mine == [list(row) for row in theirs]


# --- what it does to the sampler -------------------------------------------

def sample(affinity, seed=7, samples=400):
    """Deal one fixed set of unseen cards many times, with and without a prior."""
    unseen = parse_hand(
        "DA DK DQ DJ DT D9 D8 D7 D6 HA HK HQ HJ HT H9 H8 H7 H6 "
        "SA SK SQ SJ ST S9 S8 S7 S6"
    )
    counts = [0, 9, 9, 9]
    return core.rs_determinize(unseen, counts, [0, 0, 0, 0], affinity, seed, samples)


def mean_in_suit(worlds, seat, suit):
    mask = SUIT_MASK[suit]
    return sum(len(card_list(w[seat] & mask)) for w in worlds) / len(worlds)


def test_the_prior_tilts_the_sampling():
    """Seat 1 asked for hearts and threw Ecken, so it should be dealt more hearts and fewer
    diamonds than an even split would give it."""
    flat = sample([[0] * 4 for _ in range(4)])
    tilted = sample([[0, 0, 0, 0], [-LIMIT, +LIMIT, 0, 0], [0] * 4, [0] * 4])

    assert mean_in_suit(tilted, 1, H) > mean_in_suit(flat, 1, H) + 0.5
    assert mean_in_suit(tilted, 1, D) < mean_in_suit(flat, 1, D) - 0.5


def test_the_prior_never_makes_a_world_impossible():
    """The property that separates this from a void. A seat that asked for hearts can still
    turn up holding a fistful of Ecken — a human who ignores the convention, or one who had
    nothing else to throw, must stay inside the search's reach."""
    worlds = sample([[0, 0, 0, 0], [-LIMIT, +LIMIT, 0, 0], [0] * 4, [0] * 4], samples=600)
    assert worlds, "the sampler produced nothing at all"
    assert any(w[1] & SUIT_MASK[D] for w in worlds), "never dealt the down-weighted suit"
    assert max(len(card_list(w[1] & SUIT_MASK[D])) for w in worlds) >= 3, (
        "the down-weighted suit is reachable but not in any quantity"
    )


def test_every_card_still_finds_a_home():
    """The prior changes which seat is likelier to get a card, never whether it is dealt."""
    unseen = parse_hand(
        "DA DK DQ DJ DT D9 D8 D7 D6 HA HK HQ HJ HT H9 H8 H7 H6 "
        "SA SK SQ SJ ST S9 S8 S7 S6"
    )
    worlds = sample([[0, 0, 0, 0], [-LIMIT, +LIMIT, 0, 0], [0] * 4, [0] * 4], samples=200)
    for w in worlds:
        assert w[0] == 0
        assert w[1] | w[2] | w[3] == unseen, "cards went missing"
        assert w[1] & w[2] == 0 and w[1] & w[3] == 0 and w[2] & w[3] == 0, "card dealt twice"
        assert all(len(card_list(w[s])) == 9 for s in (1, 2, 3))


def test_the_prior_respects_a_proven_void():
    """Proof outranks suggestion: asking for hearts cannot conjure one you are known not to
    hold."""
    unseen = parse_hand(
        "DA DK DQ DJ DT D9 D8 D7 D6 HA HK HQ HJ HT H9 H8 H7 H6 "
        "SA SK SQ SJ ST S9 S8 S7 S6"
    )
    worlds = core.rs_determinize(
        unseen, [0, 9, 9, 9], [0, SUIT_MASK[H], 0, 0],
        [[0, 0, 0, 0], [-LIMIT, +LIMIT, 0, 0], [0] * 4, [0] * 4], 11, 200,
    )
    assert worlds
    assert all(w[1] & SUIT_MASK[H] == 0 for w in worlds), "dealt a card it cannot hold"
