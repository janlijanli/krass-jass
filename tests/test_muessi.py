"""The Müessi: whoever was dealt the Ecken 10 opens a game's first round.

Owner, 2026-11-06 and 2026-11-07 (`ecken_ten_muss`): in the Schieber the Ecken 10 must choose in the
first round; in the Coiffeur it only opens, and may shove. After the first round the choice passes
on one seat in play order — counter-clockwise. The table marks who is in the Müessi: the Schieber's
first round, and every Coiffeur round's first chooser.
"""

from __future__ import annotations

import random

import pytest

from krass_jass.cards import card_list
from krass_jass.game import ECKEN_TEN, Game, Phase
from krass_jass.rules import COIFFEUR, EVAL, HOUSE, SHOVE, Contract
from krass_jass.state import IllegalMove

core = pytest.importorskip("krass_jass_core")


def ecken_seat(game: Game) -> int:
    return next(s for s in range(4) if game.hand_of(s) & (1 << ECKEN_TEN))


def finish_round(game: Game, rng: random.Random) -> None:
    while game.phase is not Phase.ROUND_OVER:
        seat = game.to_act
        if game.phase is Phase.BLOCK:
            game.choose_block(seat, rng.choice(game.legal_blocks()))
        else:
            game.play(seat, rng.choice(card_list(game.round.legal_moves(seat))))


@pytest.mark.parametrize("seed", [1, 2, 3, 17, 404])
def test_schieber_ecken_ten_opens_and_may_not_shove(seed):
    game = Game(cfg=HOUSE, seed=seed)
    seat = ecken_seat(game)
    assert game.to_act == game.forehand == seat
    assert not game.may_shove(seat)
    with pytest.raises(IllegalMove, match="Müessi"):
        game.bid(seat, SHOVE)
    game.bid(seat, Contract.HEARTS)
    assert game.contract is Contract.HEARTS and game.declarer == seat


@pytest.mark.parametrize("seed", [1, 2, 3, 17, 404])
def test_coiffeur_ecken_ten_opens_and_may_shove(seed):
    game = Game(cfg=COIFFEUR, seed=seed)
    seat = ecken_seat(game)
    assert game.to_act == seat == game.muessi_seat
    assert SHOVE in game.legal_choices() and game.may_shove(seat) and not game.muss
    game.bid(seat, SHOVE)
    assert game.to_act == (seat + 1) % 4
    assert game.muessi_seat == seat, "the M stays with the seat that chose first"


@pytest.mark.parametrize("cfg", [HOUSE.variant(target_score=None), COIFFEUR], ids=["schieber", "coiffeur"])
def test_after_the_first_round_the_choice_passes_counter_clockwise_and_shoving_returns(cfg):
    rng = random.Random(5)
    game = Game(cfg=cfg, seed=31)
    first = ecken_seat(game)
    for r in range(4):
        seat = game.to_act
        assert seat == (first + r) % 4, "one seat on in play order each round"
        assert game.may_shove(seat) == (r > 0 or cfg.coiffeur)
        assert game.muessi_seat == (seat if cfg.coiffeur or r == 0 else None)
        if cfg.coiffeur:
            game.bid(seat, str(next(c for c in game.legal_choices() if c != SHOVE)))
        else:
            game.bid(seat, Contract.OBENABE)
        finish_round(game, rng)
        game.next_round()


def test_off_in_the_measurement_preset_and_by_flag():
    assert not EVAL.ecken_ten_muss
    game = Game(cfg=HOUSE.variant(ecken_ten_muss=False), seed=1)
    assert game.may_shove(game.to_act)
    game = Game(cfg=COIFFEUR.variant(ecken_ten_muss=False), seed=1)
    assert SHOVE in game.legal_choices()


@pytest.mark.parametrize("seed", [1, 2, 3, 17, 404])
def test_rust_agrees(seed):
    py = Game(cfg=HOUSE.variant(target_score=1000), seed=seed)
    rs = core.RsGame(seed, target_score=1000)
    seat = py.to_act
    assert rs.to_act == seat
    assert [py.may_shove(s) for s in range(4)] == [rs.may_shove(s) for s in range(4)] == [False] * 4
    with pytest.raises(Exception):
        rs.bid(seat, -1)

    py = Game(cfg=COIFFEUR, seed=seed)
    rs = core.RsGame(seed, coiffeur=True)
    assert [str(c) for c in py.legal_choices()] == rs.legal_choices()
    assert "SHOVE" in rs.legal_choices()
    assert rs.may_shove(py.to_act)


def test_the_view_names_the_muessi_seat_for_the_whole_first_round():
    """The table marks who was in the Müessi with a gold M through the first round, and only then."""
    from web.app import new_table, view

    table = new_table(settings={"mode": "schieber"})
    game = table.game
    seat = ecken_seat(game)
    frame = view(table, 0)
    assert frame["muessi"] and frame["muessi_seat"] == seat
    game.bid(seat, Contract.OBENABE)
    while game.phase is not Phase.ROUND_OVER:
        frame = view(table, 0)
        assert frame["muessi_seat"] == seat and not frame["muessi"]
        s = game.to_act
        if game.phase is Phase.WEIS:
            game.choose_weis(s, False)
            continue
        game.play(s, card_list(game.round.legal_moves(s))[0])
    game.next_round()
    frame = view(table, 0)
    assert frame["muessi_seat"] is None and not frame["muessi"]


def test_in_the_coiffeur_every_round_marks_its_first_chooser():
    from web.app import new_table, view

    table = new_table(settings={"mode": "coiffeur"})
    game = table.game
    first = ecken_seat(game)
    frame = view(table, 0)
    assert frame["muessi"] and frame["muessi_seat"] == first and not frame["muss"]
    rng = random.Random(2)
    for r in range(3):
        assert view(table, 0)["muessi_seat"] == (first + r) % 4
        game.bid(game.to_act, SHOVE)                    # the M does not move with a shove
        assert view(table, 0)["muessi_seat"] == (first + r) % 4
        game.bid(game.to_act, str(next(c for c in game.legal_choices() if c != SHOVE)))
        finish_round(game, rng)
        game.next_round()
