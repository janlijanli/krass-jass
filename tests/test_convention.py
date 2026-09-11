"""Table conventions — the ordering applied to moves the search rated the same.

The obligation that matters is the negative one: a convention must never take a move the
search preferred. Everything else here is about being readable to a partner, which is a
judgement, but "does not cost tricks" is checkable and is checked.
"""

import pytest

from krass_jass import convention
from krass_jass.cards import format_card, parse_card, parse_hand
from krass_jass.observation import Observation
from krass_jass.rules import Contract

DIAMONDS, HEARTS, SPADES, CLUBS = (Contract.DIAMONDS, Contract.HEARTS,
                                   Contract.SPADES, Contract.CLUBS)


def obs_for(hand, contract, trick=(), leader=0, seat=1, tricks_played=()):
    return Observation(
        seat=seat,
        hand=parse_hand(hand),
        legal_moves=parse_hand(hand),
        contract=contract,
        declarer_seat=0,
        trick=tuple(parse_card(c) for c in trick),
        trick_leader=leader,
        tricks_played=tricks_played,
    )


def candidates(*cards, dets=10, mean=0.5):
    """A search result that rates every move identically — so the convention decides."""
    return [(parse_card(c), 100, mean, dets) for c in cards]


def test_the_sister_suits_are_the_colour_pairs():
    assert convention.sister(DIAMONDS.trump_suit) == HEARTS.trump_suit
    assert convention.sister(HEARTS.trump_suit) == DIAMONDS.trump_suit
    assert convention.sister(SPADES.trump_suit) == CLUBS.trump_suit
    assert convention.sister(CLUBS.trump_suit) == SPADES.trump_suit


def test_a_single_candidate_is_returned_untouched():
    obs = obs_for("HA HK D6 S6 C6 C7 C8 C9 CT", CLUBS)
    assert convention.choose(candidates("HA"), obs, [0, 0, 0, 0]) == parse_card("HA")


def test_the_search_keeps_its_pick_when_it_expressed_one():
    """One move rated clearly ahead of the rest: the convention has no business here."""
    obs = obs_for("HA H7 D6 D7 S6 C6 C7 C8 C9", CLUBS, trick=("SA",), leader=0)
    cands = [
        (parse_card("H7"), 100, 0.61, 40),
        (parse_card("D6"), 100, 0.50, 2),
    ]
    assert convention.choose(cands, obs, [0, 0, 0, 0]) == parse_card("H7")


def test_the_discard_asks_for_the_suit_it_wants():
    """Holding the ace of hearts, the bot wants hearts led — so it throws an Ecke."""
    hand = "HA HK H9 D6 D7 S8 S9 C6 C7"
    obs = obs_for(hand, CLUBS, trick=("SA",), leader=0)
    # Spades were led and clubs are trump, so hearts and diamonds are the discards.
    pick = convention.choose(candidates("H9", "D6", "D7"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "D6", "the low Ecke asks for hearts"


def test_the_convention_reverses_with_the_wanted_suit():
    """Holding the ace of diamonds instead, the ask runs the other way."""
    hand = "DA DK D9 H6 H7 S8 S9 C6 C7"
    obs = obs_for(hand, CLUBS, trick=("SA",), leader=0)
    pick = convention.choose(candidates("D9", "H6", "H7"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "H6", "the low heart asks for Ecken"


def test_the_black_pair_works_the_same_way():
    hand = "SA SK S9 C6 C7 H8 H9 D6 D7"
    obs = obs_for(hand, HEARTS, trick=("DA",), leader=0)
    pick = convention.choose(candidates("S9", "C6", "C7"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "C6", "the low Kreuz asks for Schaufel"


def test_it_never_throws_a_card_that_is_still_the_best_of_its_suit():
    """The point of a discard is that you can spare it. Spending a winner to send a message
    is not a convention, it is a present."""
    # Every heart above the nine is already gone, so H9 is the best heart left.
    played = ((0, tuple(parse_card(c) for c in ("HA", "HK", "HQ", "HJ"))),
              (0, tuple(parse_card(c) for c in ("HT", "D8", "D9", "DT"))))
    hand = "H9 DA DK S8 S9 C6 C7 C8 C9"
    obs = obs_for(hand, CLUBS, trick=("SA",), leader=0, tricks_played=played)
    pick = convention.choose(candidates("H9", "DK"), obs, [0, 0, 0, 0])
    assert format_card(pick) != "H9", "H9 is the best heart left and is not a throwaway"


def test_it_cashes_a_certain_trick_when_the_opponents_are_out_of_trump():
    """With no trump left against you, the best card in a side suit is not a card that might
    win — it is a trick, and it is the clearest thing a partner can be shown."""
    hand = "HA H7 D7 S8 S9 C6 C7 C8 C9"
    obs = obs_for(hand, CLUBS, seat=1)
    # Seats 0 and 2 are the opponents of seat 1; rule out every club for both.
    from krass_jass.cards import SUIT_MASK
    forbidden = [SUIT_MASK[CLUBS.trump_suit], 0, SUIT_MASK[CLUBS.trump_suit], 0]
    pick = convention.choose(candidates("HA", "D7", "S8"), obs, forbidden)
    assert format_card(pick) == "HA"


def test_it_does_not_cash_while_a_trump_is_unaccounted_for():
    hand = "HA H7 D7 S8 S9 C6 C7 C8 C9"
    obs = obs_for(hand, CLUBS, seat=1)
    pick = convention.choose(candidates("D7", "HA", "S8"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "D7", "nothing proved, so the search's pick stands"


@pytest.mark.parametrize("seed", [4, 19, 77])
def test_it_only_ever_picks_a_move_the_search_offered(seed):
    """Whole games, at a real budget: whatever comes out is one of the legal moves the
    search actually returned."""
    from krass_jass.agent import DmctsAgent
    from krass_jass.game import Game
    from krass_jass.rules import EVAL
    from krass_jass.voids import infer_forbidden

    bot = DmctsAgent(determinizations=20, iterations=40, cfg=EVAL)
    game = Game(cfg=EVAL.variant(target_score=None), seed=seed)
    game.bid(game.to_act, bot.select_trump(game.hand_of(game.to_act), True))

    while game.round is not None and not game.round.done:
        seat = game.to_act
        obs = game.observation(seat)
        cards = bot.trace(obs)
        forbidden = infer_forbidden(
            list(obs.tricks_played), list(obs.trick), obs.trick_leader, obs.contract, bot.cfg
        )
        pick = convention.choose(cards, obs, forbidden)
        assert pick in [c[0] for c in cards]
        assert obs.legal_moves & (1 << pick), "and it is legal"
        game.play(seat, pick)


@pytest.mark.parametrize("seed", [5, 23])
def test_both_implementations_choose_the_same_card(seed):
    """The offline build runs the convention in Rust. Both sides are handed the *same*
    search output here, so any difference is the convention itself and not the search."""
    core = pytest.importorskip("krass_jass_core", reason="Rust core not built")

    from krass_jass.agent import DmctsAgent
    from krass_jass.cards import SUIT_MASK  # noqa: F401  (kept for symmetry with the fixture)
    from krass_jass.game import Game
    from krass_jass.rules import EVAL
    from krass_jass.voids import infer_forbidden

    bot = DmctsAgent(determinizations=20, iterations=40, cfg=EVAL)
    game = Game(cfg=EVAL.variant(target_score=None), seed=seed)
    game.bid(game.to_act, bot.select_trump(game.hand_of(game.to_act), True))

    while game.round is not None and not game.round.done:
        seat = game.to_act
        obs = game.observation(seat)
        cands = bot.trace(obs)
        forbidden = infer_forbidden(
            list(obs.tricks_played), list(obs.trick), obs.trick_leader, obs.contract, bot.cfg
        )
        mine = convention.choose(cands, obs, forbidden)
        theirs = core.rs_convention_choose(
            [tuple(c) for c in cands],
            obs.hand,
            obs.unseen,
            obs.hand | obs.played,
            list(obs.trick),
            obs.seat,
            obs.contract.trump_suit if obs.contract.is_trump else -1,
            int(obs.contract),
            forbidden,
        )
        assert mine == theirs, (
            f"convention diverged: python {format_card(mine)} vs rust {format_card(theirs)}"
        )
        game.play(seat, mine)
