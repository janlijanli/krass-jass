"""Coiffeur rules, written from `docs/rules-config.md` ("Coiffeur").

`tests/test_game_port.py` holds Python and Rust to the same event stream; this holds the
Python engine to the rule text.
"""

import random

import pytest

from krass_jass.cards import card_list
from krass_jass.coiffeur import ROW_NAMES, Choice, Choosing, Sheet, multipliers, row_value
from krass_jass.game import Game, Phase
from krass_jass.rules import COIFFEUR, SHOVE, Contract
from krass_jass.state import IllegalMove

FIXED = COIFFEUR.variant(coiffeur_random_multipliers=False)


def play_out(game, rng):
    """Random legal cards to the end of the round."""
    while game.phase is Phase.PLAYING:
        seat = game.to_act
        game.play(seat, rng.choice(card_list(game.round.legal_moves(seat))))


def test_preset_has_no_weis_no_stoeck_no_target_and_unit_contract_multipliers():
    assert COIFFEUR.coiffeur and not COIFFEUR.sidi
    assert not COIFFEUR.weis_enabled and not COIFFEUR.stoeck_enabled
    assert COIFFEUR.target_score is None
    assert all(COIFFEUR.multiplier(c) == 1 for c in Contract)


def test_multipliers_are_random_by_default_and_fixed_on_request():
    assert COIFFEUR.coiffeur_random_multipliers
    assert multipliers(3, FIXED) == (4, 2, 3, 1, 5, 6, 7, 8)
    # Same seed, same sheet — replay depends on it.
    assert multipliers(3, COIFFEUR) == multipliers(3, COIFFEUR)
    assert multipliers(3, COIFFEUR) != multipliers(4, COIFFEUR) or multipliers(5, COIFFEUR) != multipliers(4, COIFFEUR)


def test_choice_wire_form_round_trips():
    for choice in Sheet().choices(0):
        assert Choice.parse(str(choice)) == choice
    assert str(Choice(Contract.HEARTS, 1)) == "HEARTS"
    assert str(Choice(Contract.OBENABE, 7)) == "OBENABE/JOKER2"
    with pytest.raises(ValueError):
        Choice.parse("HEARTS/OBENABE")      # only a Joker takes a foreign contract


def test_a_fresh_sheet_offers_six_rows_and_two_jokers_of_six():
    assert len(Sheet().choices(0)) == 6 + 2 * 6


def test_shoving_goes_round_the_table_and_forehand_ends_up_in_the_hole():
    choosing = Choosing(forehand=1, sheet=Sheet())
    seats = []
    for _ in range(4):
        seats.append(choosing.chooser)
        choosing.act(choosing.chooser, SHOVE)
    # To the next seat — an opponent, not the partner — and back to forehand.
    assert seats == [1, 2, 3, 0]
    assert choosing.chooser == 1
    assert SHOVE not in choosing.legal()
    with pytest.raises(ValueError):
        choosing.act(1, SHOVE)


def test_once_a_team_is_done_only_the_other_chooses_and_shoves_to_the_partner_and_back():
    sheet = Sheet()
    sheet.written[0] = [100] * 8
    choosing = Choosing(forehand=0, sheet=sheet)      # forehand's team is finished
    assert choosing.chooser == 1
    choosing.act(1, SHOVE)
    assert choosing.chooser == 3
    choosing.act(3, SHOVE)
    assert choosing.chooser == 1
    assert SHOVE not in choosing.legal()


def test_a_played_row_is_closed_but_its_contract_can_still_go_to_a_joker():
    sheet = Sheet()
    sheet.written[1][Contract.HEARTS] = 80
    choices = sheet.choices(1)
    assert Choice(Contract.HEARTS, 1) not in choices
    assert Choice(Contract.HEARTS, 6) in choices
    # The other team's column is its own.
    assert Choice(Contract.HEARTS, 1) in sheet.choices(0)


def test_the_chooser_leads_and_only_the_choosing_team_writes():
    game = Game(cfg=FIXED, seed=11)
    chooser = game.to_act
    game.bid(chooser, SHOVE)
    second = game.to_act
    assert second == (chooser + 1) % 4
    game.bid(second, "OBENABE")
    assert game.round.leader == second
    play_out(game, random.Random(0))

    team = second % 2
    points = game.last_score["round_total"]
    assert sum(points) in (157, 257)
    tens = (points[team] + 5) // 10
    assert game.last_score["written"][team] == tens * 5     # Obenabe is x5 in the table
    assert game.last_score["written"][1 - team] == 0
    assert game.scores[1 - team] == 0
    assert game.sheet.written[team][Contract.OBENABE] == tens


def test_points_are_written_in_tens_rounded_half_up_or_in_full_on_request():
    assert [row_value(p, COIFFEUR) for p in (0, 4, 5, 84, 85, 157, 257)] == [0, 0, 1, 8, 9, 16, 26]
    full = COIFFEUR.variant(coiffeur_tens=False)
    assert row_value(85, full) == 85


def test_score_opponents_credits_the_defenders_at_the_rows_multiplier():
    game = Game(cfg=FIXED.variant(coiffeur_score_opponents=True), seed=11)
    seat = game.to_act
    game.bid(seat, "CLUBS")                 # x1 in the table
    play_out(game, random.Random(1))
    points = game.last_score["round_total"]
    assert game.scores == [(p + 5) // 10 for p in points]
    # ...but only the choosing team's row is filled.
    assert game.sheet.written[1 - seat % 2] == [None] * 8


def test_illegal_choices_are_refused():
    game = Game(cfg=FIXED, seed=5)
    seat = game.to_act
    with pytest.raises(IllegalMove):
        game.bid((seat + 1) % 4, "HEARTS")          # not on turn
    with pytest.raises(IllegalMove):
        game.bid(seat, "HEARTS/UNDENUFE")


def test_a_game_is_sixteen_rounds_and_ends_with_the_sheet():
    rng = random.Random(9)
    game = Game(cfg=COIFFEUR, seed=9)
    rounds = 0
    while game.phase is not Phase.GAME_OVER:
        if game.phase is Phase.ROUND_OVER:
            game.next_round()
        while game.phase is Phase.BIDDING:
            game.bid(game.to_act, rng.choice(game.legal_choices()))
        play_out(game, rng)
        rounds += 1
    assert rounds == 16
    assert game.sheet.complete
    total = [
        sum(p * m for p, m in zip(game.sheet.written[t], game.row_multipliers)) for t in (0, 1)
    ]
    assert total == game.scores
    over = game.log.all()[-1]
    assert over.payload["decided_by"] == "sheet"
    assert over.payload["winner"] == (-1 if total[0] == total[1] else int(total[1] > total[0]))


def test_row_names_cover_the_sheet():
    assert ROW_NAMES[:6] == tuple(c.name for c in Contract)


# --- the rule-based choice --------------------------------------------------

from krass_jass.cards import parse_card  # noqa: E402
from krass_jass.coiffeur_select import choose, value_choices  # noqa: E402


def hand(*codes):
    out = 0
    for code in codes:
        out |= 1 << parse_card(code)
    return out


def test_the_selector_always_returns_something_legal():
    rng = random.Random(3)
    for seed in range(30):
        game = Game(cfg=COIFFEUR, seed=seed)
        while game.phase is not Phase.GAME_OVER:
            if game.phase is Phase.ROUND_OVER:
                game.next_round()
            while game.phase is Phase.BIDDING:
                legal = game.legal_choices()
                action = choose(game.hand_of(game.to_act), legal, game.row_multipliers, COIFFEUR)
                assert action in legal
                game.bid(game.to_act, action)
            play_out(game, rng)


def test_a_monster_trump_hand_goes_into_the_dearest_row_that_takes_it():
    monster = hand("HJ", "H9", "HA", "HK", "HQ", "HT", "H8", "S6", "D7")
    mults = (1, 3, 2, 4, 5, 6, 7, 8)        # hearts x3, the Jokers x7 and x8
    choice = choose(monster, Sheet().choices(0) + [SHOVE], mults, COIFFEUR)
    assert choice == Choice(Contract.HEARTS, 7)


def test_a_weak_hand_shoves_when_it_may_and_chooses_when_it_must():
    # Queens and tens: no Puur, no Nell, no aces, no sixes — nothing in any contract.
    weak = hand("DQ", "DT", "HQ", "HT", "SQ", "ST", "CQ", "CT", "DK")
    legal = Sheet().choices(0)
    assert choose(weak, legal + [SHOVE], COIFFEUR.coiffeur_multipliers, COIFFEUR) == SHOVE
    forced = choose(weak, legal, COIFFEUR.coiffeur_multipliers, COIFFEUR)
    assert forced in legal
    # Forced, it spends the cheapest row it can rather than a dear one.
    values = value_choices(weak, legal, COIFFEUR.coiffeur_multipliers, COIFFEUR)
    assert values[forced] == max(values.values())
