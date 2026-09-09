"""Card values and round scoring.

Note the shape of `test_every_contract_totals_152`: it is a *regression guard*, not a
correctness test. Every contract totals 152 by construction, which is exactly why a
"sums to 157" check cannot catch a mis-implemented Undenufe — so the per-card values are
asserted individually against the reference table.
"""

import pytest

from krass_jass.rules import EVAL, HOUSE, Contract, DEFAULT_MULTIPLIERS
from krass_jass.scoring import score_round, team_of
from krass_jass.tables import CARD_VALUES, DECK_POINTS
from tests import reference
from tests.helpers import CONTRACT_CODES, to_codes


@pytest.mark.parametrize("contract", list(Contract))
def test_every_contract_totals_152(contract):
    assert DECK_POINTS[contract] == 152


@pytest.mark.parametrize("contract", list(Contract))
def test_per_card_values_match_reference(contract):
    """The test that actually catches Undenufe."""
    values = CARD_VALUES[contract]
    code = CONTRACT_CODES[contract]
    for c in range(36):
        assert values[c] == reference.card_value(to_codes(1 << c)[0], code)


def test_undenufe_inverts_the_values():
    v = CARD_VALUES[Contract.UNDENUFE]
    from krass_jass.cards import parse_card

    assert v[parse_card("D6")] == 11, "the 6 is worth 11 in Undenufe"
    assert v[parse_card("DA")] == 0, "the ace is worth 0 in Undenufe"
    assert v[parse_card("D8")] == 8


def test_trump_puur_and_naell():
    v = CARD_VALUES[Contract.HEARTS]
    from krass_jass.cards import parse_card

    assert v[parse_card("HJ")] == 20
    assert v[parse_card("H9")] == 14
    assert v[parse_card("DJ")] == 2
    assert v[parse_card("D9")] == 0


def test_multipliers_use_the_correct_suit_pairs():
    """Schilten+Schellen (spades+diamonds) are cheap; Eichel+Rosen (clubs+hearts) dear."""
    assert DEFAULT_MULTIPLIERS[Contract.SPADES] == 1
    assert DEFAULT_MULTIPLIERS[Contract.DIAMONDS] == 1
    assert DEFAULT_MULTIPLIERS[Contract.CLUBS] == 2
    assert DEFAULT_MULTIPLIERS[Contract.HEARTS] == 2
    assert DEFAULT_MULTIPLIERS[Contract.OBENABE] == 3
    assert DEFAULT_MULTIPLIERS[Contract.UNDENUFE] == 4


def test_seats_to_teams():
    assert [team_of(s) for s in range(4)] == [0, 1, 0, 1]


def test_round_totals_157_before_multiplier():
    s = score_round((100, 52), (5, 4), last_trick_winner=0, contract=Contract.SPADES, cfg=HOUSE)
    assert sum(s.trick_points) + sum(s.last_trick) == 157
    assert s.total == (105, 52)


def test_match_bonus_and_multiplier():
    s = score_round((152, 0), (9, 0), last_trick_winner=2, contract=Contract.HEARTS, cfg=HOUSE)
    assert s.match == (100, 0)
    # (152 + 5 + 100) * 2
    assert s.total == (514, 0)


def test_eval_preset_disables_the_variance_sources():
    s = score_round(
        (152, 0), (9, 0), last_trick_winner=0, contract=Contract.HEARTS, cfg=EVAL,
        weis=(100, 0), stoeck=(20, 0),
    )
    assert s.match == (0, 0)
    assert s.weis == (0, 0)
    assert s.stoeck == (0, 0)
    assert s.total == (314, 0)  # (152 + 5) * 2
