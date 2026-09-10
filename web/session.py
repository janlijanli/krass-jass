"""Guest sessions.

`PLAN.md` §7: no accounts means no password surface and essentially no personal data to
protect. That is a design win — do not build auth that is not needed.

A session is a signed, HTTP-only, SameSite cookie carrying a game id and a seat. Signed with
stdlib HMAC rather than a dependency: it is fifteen lines and one less thing in the supply
chain (threat T6).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode

COOKIE_NAME = "kj_session"

#: A restart invalidates sessions unless this is set. Fine for development, and the
#: alternative — a hardcoded default — is the kind of thing that ships to production.
SECRET = os.environ.get("KRASS_JASS_SECRET", secrets.token_hex(32)).encode()


def _sign(payload: bytes) -> bytes:
    return hmac.new(SECRET, payload, hashlib.sha256).digest()[:16]


def encode(data: dict) -> str:
    payload = urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode())
    return f"{payload.decode()}.{urlsafe_b64encode(_sign(payload)).decode()}"


def decode(cookie: str | None) -> dict | None:
    """Returns None for anything not signed by us — tampered, truncated or from a restart."""
    if not cookie or "." not in cookie:
        return None
    payload_b64, sig_b64 = cookie.rsplit(".", 1)
    payload = payload_b64.encode()
    try:
        signature = urlsafe_b64decode(sig_b64)
    except Exception:
        return None
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        return json.loads(urlsafe_b64decode(payload))
    except Exception:
        return None
