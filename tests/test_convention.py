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


def test_the_discard_comes_from_the_weakest_suit():
    """Verwerfen: throw the suit you do not want led. Strong in hearts, bare in Ecken — so an
    Ecke goes, lowest first."""
    hand = "HA HK H9 D6 D7 S8 S9 C6 C7"
    obs = obs_for(hand, CLUBS, trick=("SA",), leader=0)
    # Spades were led and clubs are trump, so hearts and diamonds are the discards.
    pick = convention.choose(candidates("H9", "D6", "D7"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "D6", "the low Ecke — the weakest suit"


def test_the_discard_follows_the_weak_suit_whichever_it_is():
    """Strong in Ecken instead, and the discard is a heart."""
    hand = "DA DK D9 H6 H7 S8 S9 C6 C7"
    obs = obs_for(hand, CLUBS, trick=("SA",), leader=0)
    pick = convention.choose(candidates("D9", "H6", "H7"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "H6", "the low heart — the weakest suit"


def test_the_black_pair_works_the_same_way():
    hand = "SA SK S9 C6 C7 H8 H9 D6 D7"
    obs = obs_for(hand, HEARTS, trick=("DA",), leader=0)
    pick = convention.choose(candidates("S9", "C6", "C7"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "C6", "the low Kreuz — the weakest suit"


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


def test_it_cashes_the_ace_among_tied_leads_even_with_trumps_out():
    """Aces first, the way a human partner counts. The search already priced the chance of a
    ruff when it rated the ace level with the other leads, so among ties it is not a risk the
    convention adds."""
    hand = "HA H7 D7 S8 S9 C6 C7 C8 C9"
    obs = obs_for(hand, CLUBS, seat=1)          # declarer is seat 0: the other team
    pick = convention.choose(candidates("D7", "HA", "S8"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "HA"


def test_the_declaring_team_draws_trumps_with_the_best_one_left():
    """'Trumpf ziehen': the declarer leads the Puur, so the opponents' trumps come out."""
    hand = "CJ C9 CA HA H7 D7 S8 S9 C6"          # clubs trump; Puur and Nell in hand
    obs = obs_for(hand, CLUBS, seat=0)          # seat 0 declared
    pick = convention.choose(candidates("HA", "CJ", "C9", "D7"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "CJ", "the Puur first, not the ace"


def test_the_ace_with_two_more_trumps_leads_the_second_one():
    """'Trumpf-Ass nicht zu dritt ausspielen': without the Bauer, the trump ace with more
    trumps is kept, and the next trump goes first."""
    hand = "CA C8 HA H7 D7 S8 S9 C6 C7"          # clubs trump; Puur and Nell are out
    obs = obs_for(hand, CLUBS, seat=0)
    pick = convention.choose(candidates("C8", "CA", "HA", "D7"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "C8"


def test_the_bauer_with_one_other_trump_leads_the_other():
    """'Trumpf-Buur nicht zu zweit ausspielen'."""
    hand = "CJ C6 HA H7 D7 S8 S9 D6 D8"
    obs = obs_for(hand, CLUBS, seat=0)
    pick = convention.choose(candidates("CJ", "C6", "HA"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "C6"


def test_the_bauer_alone_is_shown_with_a_brettli_not_led():
    """'Trumpf-Buur nie blutt ausspielen' — a low card (6 to 9) of the strongest side suit
    tells the partner it is there."""
    hand = "CJ HA HK H8 D7 S6 S7 S8 S9"          # clubs trump; the Bauer is the only trump
    obs = obs_for(hand, CLUBS, seat=0)
    pick = convention.choose(candidates("CJ", "HA", "H8", "S6"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "H8", "a Brettli of hearts, the strongest side suit"


def test_anziehen_leads_the_lowest_card_of_a_strong_suit_without_its_ace():
    """Without the ace, lead low so the ace is drawn and the king becomes the best left."""
    hand = "HK HQ H8 D7 S6 C6 C7 C8 S7"          # clubs trump, the other team declared
    obs = obs_for(hand, CLUBS, seat=1)
    pick = convention.choose(candidates("HQ", "H8", "D7"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "H8"


def test_it_does_not_lead_back_a_suit_the_partner_threw_away():
    """'Wenn der Partner eine Farbe verwirft, diese nicht bringen.'"""
    played = ((0, tuple(parse_card(c) for c in ("DT", "D8", "DJ", "H6"))),)   # seat 3 threw a heart
    hand = "HA SA S7 H7 D7 S8 S9 D6 C9"
    obs = obs_for(hand, CLUBS, seat=1, leader=1, tricks_played=played)
    assert convention.partner_discards(obs) == 1 << HEARTS.trump_suit
    pick = convention.choose(candidates("HA", "SA"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "SA"


def test_obenabe_drops_the_king_under_the_partners_ace():
    obs = obs_for("HK H7 D7 S6 S7 C6 C7 C8 D8", Contract.OBENABE, trick=("HA",), leader=3, seat=1)
    pick = convention.choose(candidates("HK", "H7"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "HK"


def test_undenufe_drops_the_seven_under_the_partners_six():
    obs = obs_for("H7 HA D7 S6 S7 C6 CA C8 D8", Contract.UNDENUFE, trick=("H6",), leader=3, seat=1)
    pick = convention.choose(candidates("H7", "HA"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "H7"


def test_schmieren_gives_points_to_the_partners_trick_when_last():
    """Last to play and the partner takes it: give it the ten — not a trump, not a winner."""
    obs = obs_for("HT D6 C6 D8 D9 H7 C7 C8 H8", CLUBS, trick=("S7", "SA", "S8"), leader=2, seat=1)
    pick = convention.choose(candidates("HT", "D6", "C6"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "HT"


def test_it_does_not_trump_the_partners_trick():
    """'Du trumpfst zu viel.'"""
    obs = obs_for("C8 D7 D6 H7 H8 C6 C7 D8 H9", CLUBS, trick=("SA", "S6"), leader=3, seat=1)
    pick = convention.choose(candidates("C8", "D7"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "D7"


def test_the_defending_team_does_not_draw_trumps():
    hand = "CJ C9 CA HA H7 D7 S8 S9 C6"
    obs = obs_for(hand, CLUBS, seat=1)          # the other team declared
    pick = convention.choose(candidates("CJ", "HA", "D7"), obs, [0, 0, 0, 0])
    assert format_card(pick) == "HA"


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
            (obs.declarer_seat & 1) == (obs.seat & 1),
            0.05,
            0.01,
            convention.partner_discards(obs),
        )
        assert mine == theirs, (
            f"convention diverged: python {format_card(mine)} vs rust {format_card(theirs)}"
        )
        game.play(seat, mine)
