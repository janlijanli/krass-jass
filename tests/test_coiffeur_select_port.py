"""The browser build chooses Coiffeur rows with `rust/src/coiffeur_select.rs`; a human playing
offline must meet the same bots as one playing against the server. Held to
`krass_jass/coiffeur_select.py` over random hands, sheets and multipliers."""

import random

import pytest

from krass_jass.coiffeur import ALL_ROWS, Sheet, multipliers
from krass_jass.coiffeur_select import choose, choose_block, value_choices
from krass_jass.deal import deal
from krass_jass.rules import COIFFEUR, SHOVE, Contract


def core():
    from krass_jass import native

    if not hasattr(native._core, "rs_coiffeur_choose"):
        pytest.skip("Rust core predates the Coiffeur row choice")
    return native._core


@pytest.mark.parametrize("seed", range(300))
def test_rust_chooses_rows_exactly_as_python_does(seed):
    rs = core()
    rng = random.Random(seed)
    cfg = COIFFEUR.variant(coiffeur_guschti_45=seed % 3 == 0)
    sheet = Sheet.for_game(cfg)
    team = seed & 1
    # A column anywhere from full to one row left; the Chance kept or spent alike.
    rows = list(sheet.rows)
    for row in rng.sample(rows, rng.randrange(len(rows))):
        sheet.written[team][row] = rng.randrange(20)
    mults = multipliers(seed, cfg)
    hand = deal(seed, seed % 7)[seed % 4]
    choices = sheet.choices(team, cfg)
    for can_shove in (True, False):
        legal = choices + [SHOVE] if can_shove else choices
        py = choose(hand, legal, mults, cfg)
        pick, values = rs.rs_coiffeur_choose(hand, [str(c) for c in choices], can_shove, list(mults))
        assert (None if py == SHOVE else str(py)) == pick, (seed, can_shove)
    py_values = value_choices(hand, choices, mults, cfg)
    assert values == pytest.approx([py_values[c] for c in choices], abs=1e-9)
    assert len(mults) == ALL_ROWS


@pytest.mark.parametrize("seed", range(100))
def test_rust_names_3x3_blocks_as_python_does(seed):
    rs = core()
    hand = deal(seed, 0)[seed % 4]
    for options in ([0, 1, 2, 3, 4, 5], [0, 1, 2, 3], [4, 5]):
        py = choose_block(hand, [Contract(c) for c in options], COIFFEUR)
        assert rs.rs_coiffeur_block(hand, options) == int(py)
