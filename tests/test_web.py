"""Web layer. The game invariants are tested at the engine level (`test_events.py`); what
is left here is the session cookie, which is the only security-relevant code in `web/`."""

import pytest

from web import session as sessions


def test_round_trips_a_session():
    data = {"game_id": "abc123", "seat": 0}
    assert sessions.decode(sessions.encode(data)) == data


def test_rejects_a_tampered_payload():
    """The whole point of signing: a client must not be able to promote itself to another
    seat, or into someone else's game, by editing its own cookie."""
    cookie = sessions.encode({"game_id": "abc123", "seat": 0})
    payload, signature = cookie.rsplit(".", 1)

    from base64 import urlsafe_b64decode, urlsafe_b64encode
    import json

    forged = json.loads(urlsafe_b64decode(payload))
    forged["seat"] = 1
    forged_payload = urlsafe_b64encode(json.dumps(forged, separators=(",", ":")).encode()).decode()

    assert sessions.decode(f"{forged_payload}.{signature}") is None


@pytest.mark.parametrize(
    "cookie", [None, "", "garbage", "a.b", "....", "no-dot", "eyJ9.zzzz"]
)
def test_rejects_malformed_cookies_without_raising(cookie):
    """A malformed cookie is a normal event — a restart rotates the secret — so it must
    return None rather than throw and take the request down."""
    assert sessions.decode(cookie) is None


def test_secret_is_not_hardcoded():
    """A default secret in source is the kind of thing that ships."""
    import inspect

    source = inspect.getsource(sessions)
    assert "token_hex" in source, "the fallback secret must be generated, not literal"


def test_hand_is_sorted_ascending_left_to_right():
    """The engine's rank index runs ace-first, which is backwards for a player looking at
    their own cards."""
    from krass_jass.cards import parse_hand
    from web.app import sorted_hand
    from krass_jass.cards import format_card

    hand = parse_hand("CK C8 SQ S6 HK DK C9 CJ")
    codes = [format_card(c) for c in sorted_hand(hand)]
    assert codes == ["DK", "HK", "S6", "SQ", "C8", "C9", "CJ", "CK"]


def test_a_completed_trick_is_held_until_acknowledged():
    """Four cards appearing and vanishing faster than they can be read is unplayable, and
    the bots must not race ahead while the player is still looking."""
    from krass_jass.cards import card_list
    from krass_jass.game import Game
    from krass_jass.rules import HOUSE
    from web.app import Table, view

    game = Game(cfg=HOUSE, seed=6)
    game.bid(game.to_act, "HEARTS")
    table = Table(game=game, human_seat=0, bots={})

    for _ in range(4):
        seat = game.round.to_play
        game.play(seat, card_list(game.round.legal_moves(seat))[0])

    frame = view(table, 0)
    assert table.awaiting_ack()
    assert frame["trick_complete"] is True
    assert len(frame["trick"]) == 4, "the finished trick must still be on the table"
    assert frame["trick_winner"] is not None
    assert frame["legal"] == [], "no play is offered while the trick is held"

    table.acked_tricks = table.completed_tricks()
    after = view(table, 0)
    assert after["trick_complete"] is False
    assert len(after["trick"]) < 4


def test_hidden_attribute_is_forced_in_css():
    """Regression. `[hidden] { display: none }` lives in the UA stylesheet at the same
    specificity as a class rule, so `.scorecard-backdrop { display: grid }` — written later —
    beat it, and the round scorecard sat over the table with `hidden` set. Any element whose
    class sets `display` needs this rule to make `hidden` mean anything."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "web/static/table.css").read_text()
    assert "[hidden] { display: none !important; }" in css
