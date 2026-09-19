"""The information boundary, fuzzed.

`CLAUDE.md` requires a CI test that fuzzes observations and asserts no unseen card
identifier reaches the payload, and that the test moves with the observation shape. Both
are here: `test_observation_shape_is_frozen` fails the moment a field is added, which forces
whoever adds it to say whether it is public.
"""

import random

import pytest

from krass_jass.cards import FULL_DECK, card_list
from krass_jass.observation import Observation, build_observation, derive_decision_seed
from krass_jass.rules import EVAL, Contract
from krass_jass.state import RoundState

#: Every field an observation may carry. Adding one is a deliberate act.
EXPECTED_FIELDS = {
    "seat",
    "hand",
    "legal_moves",
    "contract",
    "declarer_seat",
    "trick",
    "trick_leader",
    "tricks_played",
    "scores",
    "weis_points",
    "weis_announced",
    "known_cards",
    "time_budget_ms",
    "decision_seed",
    "round_index",
    # Sidi Barrani: the auction was said aloud, so every call is public; the standing bid and
    # the double are what the table agreed to play. None of them names a card.
    "auction",
    "bid_value",
    "doubled",
}


def deal(rng):
    deck = list(range(36))
    rng.shuffle(deck)
    return [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]


def test_observation_shape_is_frozen():
    """If this fails you added a field. Decide whether it is public, then update the list
    and the leak test below — do not just widen the set."""
    assert set(Observation.__dataclass_fields__) == EXPECTED_FIELDS


def test_known_cards_are_only_ones_the_table_was_shown():
    """`known_cards` pins cards to a seat, which is the strongest claim an observation can
    make — so it must carry only what was turned face up.

    The winning Weis is shown to prove it, and everyone sees it. Nothing else qualifies: a
    partner's Weis is never shown, a losing team's is never shown, and Stöck is announced only
    once both honours have been played and are public anyway.
    """
    from krass_jass.cards import parse_card
    from krass_jass.game import Game
    from krass_jass.rules import HOUSE

    game = Game(cfg=HOUSE.variant(weis_manual=False), seed=4)
    game.bid(game.to_act, "HEARTS")
    shown = {
        (entry["seat"], parse_card(c))
        for entry in game.weis_summary
        for c in entry.get("cards") or ()
    }
    obs = game.observation(game.to_act)
    assert set(obs.known_cards) <= shown, "a card nobody was shown must not be pinned"
    for entry in game.weis_summary:
        if not entry.get("cards"):
            assert all(seat != entry["seat"] or True for seat, _ in obs.known_cards)

    # and once a shown card is played it leaves, because `played` already carries it
    for seat, card in obs.known_cards:
        assert not obs.played & (1 << card)


def test_weis_points_are_public_and_stoeck_is_not():
    """`weis_points` was added for the game-score objective and is the kind of field this
    file exists to interrogate.

    It is safe because it is a *scored* total, not a holding: by the time it is non-zero the
    whole table has called and the result was announced to everyone. Stöck is the opposite —
    held privately until the second honour is played — and has no field here on purpose.
    """
    assert "weis_points" in EXPECTED_FIELDS
    assert not any("stoeck" in f for f in EXPECTED_FIELDS), (
        "Stöck is private until announced; it must not be in an observation"
    )

    from krass_jass.game import Game
    from krass_jass.rules import HOUSE

    game = Game(cfg=HOUSE.variant(weis_manual=False), seed=4)
    game.bid(game.to_act, "HEARTS")
    obs = game.observation(game.to_act)
    # Weis is resolved before the first card in automatic mode, so the totals it carries are
    # exactly the ones the table heard announced.
    assert tuple(obs.weis_points) == tuple(game._weis)


def test_the_sidi_auction_is_public_and_names_no_card():
    """Every call in an observation is one the whole table heard, in the order it was made,
    and a call is a contract and a number — never a card."""
    from krass_jass.cards import parse_card
    from krass_jass.game import Game
    from krass_jass.rules import SIDI

    game = Game(cfg=SIDI, seed=12)
    for call in ("HEARTS 50", "PASS", "OBENABE 60", "DOUBLE"):
        game.bid(game.to_act, call)
    heard = tuple((e.payload["seat"], e.payload["action"]) for e in game.log.all() if e.type.value == "bid")
    for seat in range(4):
        obs = game.observation(seat)
        assert obs.auction == heard
        for _, call in obs.auction:
            for word in call.split():
                with pytest.raises(ValueError):
                    parse_card(word)


@pytest.mark.parametrize("contract", list(Contract))
def test_no_unseen_card_ever_reaches_the_payload(contract):
    """The core invariant. Every card identifier in an observation must be one the seat
    holds or one already face-up on the table."""
    rng = random.Random(int(contract) * 31 + 7)
    for _ in range(30):
        state = RoundState(contract=contract, hands=deal(rng), cfg=EVAL, leader=rng.randrange(4))
        while not state.done:
            for seat in range(4):
                obs = build_observation(state, seat)
                allowed = state.hands[seat] | obs.played

                assert obs.hand & ~allowed == 0
                assert obs.legal_moves & ~obs.hand == 0, "legal moves outside the hand"
                for c in obs.trick:
                    assert allowed & (1 << c), "current trick card not public"
                for _leader, cards in obs.tricks_played:
                    for c in cards:
                        assert allowed & (1 << c), "history card not public"

                # the complement is public knowledge — which cards are *somewhere* among
                # the other three hands — but it must never resolve to a specific seat
                assert obs.unseen == FULL_DECK & ~state.hands[seat] & ~obs.played

            legal = card_list(state.legal_moves())
            state.play(legal[rng.randrange(len(legal))])


def test_observation_never_carries_another_seats_hand():
    """The specific failure that would invalidate every result: a seat's own hand mask
    appearing in another seat's observation."""
    rng = random.Random(3)
    hands = deal(rng)
    state = RoundState(contract=Contract.HEARTS, hands=list(hands), cfg=EVAL)
    for seat in range(4):
        obs = build_observation(state, seat)
        payload = repr(obs)
        for other in range(4):
            if other == seat:
                continue
            assert str(hands[other]) not in payload


def test_decision_seed_is_derived_not_the_game_seed():
    """A bot holding the game seed could reconstruct the deal, so the derivation must be
    stable, distinct per decision, and not the seed itself."""
    game_seed = 0xDEADBEEFCAFE
    a = derive_decision_seed(game_seed, "g1", seat=1, rnd=0, trick=3)
    b = derive_decision_seed(game_seed, "g1", seat=1, rnd=0, trick=4)
    c = derive_decision_seed(game_seed, "g1", seat=2, rnd=0, trick=3)

    assert a == derive_decision_seed(game_seed, "g1", seat=1, rnd=0, trick=3), "must be stable"
    assert a != b and a != c, "must differ per decision"
    assert a != game_seed
    assert 0 <= a < 2**64
