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
