#!/usr/bin/env python3
"""Generate site/index.html and site/render.js from the hosted UI.

Deliberately *derived* rather than copied by hand. The card fan, the Weis bubbles, the
scorecard and the CSS are the same code the server version uses; only the transport differs,
so keeping a second copy in sync by hand would guarantee they drift.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

CONTRACTS = {"DIAMONDS": 1, "HEARTS": 2, "SPADES": 1, "CLUBS": 2, "OBENABE": 3, "UNDENUFE": 4}
TARGETS = (1000, 2000, 2500)


def build_render_js() -> None:
    """Everything from table.js up to the WebSocket, with the sender left injectable."""
    src = (ROOT / "web/static/table.js").read_text()
    render = src[: src.index('const menu = document.getElementById("menu");')]
    render = render.replace(
        """function send(message) {
  if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
}""",
        """// Injected by the controller. Same message shapes the server accepted, so nothing in
// the rendering code below had to change.
let send = () => {};
export function setSender(fn) { send = fn; }""",
    )
    render = render.replace("let lifted = null;\nlet socket = null;", "let lifted = null;")
    render = render.replace(
        "const mySeat = Number(document.body.dataset.seat);", "const mySeat = 0;"
    )
    render = render.replace(
        'import { cardFace, SUIT_GLYPHS, SUIT_IS_RED } from "./cards.js";',
        'import { cardFace, SUIT_GLYPHS, SUIT_IS_RED } from "./cards.js";\n\nexport { render };',
    )
    (SITE / "render.js").write_text(render)


def build_index() -> None:
    html = (ROOT / "web/templates/table.html").read_text()
    html = html.replace(
        '<script type="module" src="/static/table.js"></script>',
        '<script type="module" src="solo.js"></script>',
    )
    html = html.replace(
        '<link rel="stylesheet" href="/static/table.css">',
        '<link rel="stylesheet" href="table.css">',
    )
    html = html.replace('<body data-seat="{{ seat }}">', '<body data-seat="0">')
    html = html.replace("<title>krass-jass</title>", "<title>krass-jass — offline</title>")
    html = html.replace('<form class="menu" method="post" action="/new">', '<form class="menu">')
    html = html.replace(
        '<p class="menu-note">Changing these starts a new game.</p>',
        '<p class="menu-note">Changing these starts a new game. '
        "Everything runs in this tab — no server.</p>",
    )

    # Resolve the *inner* loop first. A non-greedy match on the outer one stops at the inner
    # `endfor` and leaves a stray tag behind — which is exactly what happened the first time.
    inner = re.search(r"[ \t]*\{% for value in multiplier_range %\}.*?\{% endfor %\}\n", html, re.S)
    chips = "\n".join(
        '            <label class="chip small">\n'
        f'              <input type="radio" name="mult_KEYSLOT" value="{v}"CHECK{v}>\n'
        f"              <span>×{v}</span>\n"
        "            </label>"
        for v in (1, 2, 3, 4)
    )
    html = html[: inner.start()] + chips + "\n" + html[inner.end() :]

    outer = re.search(
        r"[ \t]*\{% for name, key in contracts %\}\n(.*?)\{% endfor %\}\n", html, re.S
    )
    body = outer.group(1)
    rows = []
    for name, mult in CONTRACTS.items():
        row = body.replace("{{ name|capitalize }}", name.capitalize())
        row = row.replace("mult_KEYSLOT", f"mult_{name.lower()}")
        for v in (1, 2, 3, 4):
            row = row.replace(f"CHECK{v}", " checked" if v == mult else "")
        rows.append(row)
    html = html[: outer.start()] + "".join(rows) + html[outer.end() :]

    targets = "\n".join(
        '          <label class="chip">\n'
        f'            <input type="radio" name="target" value="{v}"'
        f'{" checked" if v == 1000 else ""}>\n'
        f"            <span>{v}</span>\n"
        "          </label>"
        for v in TARGETS
    )
    html = re.sub(
        r"[ \t]*\{% for value in targets %\}.*?\{% endfor %\}\n", targets + "\n", html, flags=re.S
    )
    html = html.replace("{% if settings.weis %}checked{% endif %}", "checked")
    html = html.replace("{% if not settings.weis %}checked{% endif %}", "")

    leftovers = [line for line in html.splitlines() if "{%" in line or "{{" in line]
    if leftovers:
        raise SystemExit(f"unresolved template tags: {leftovers[:3]}")
    (SITE / "index.html").write_text(html)


if __name__ == "__main__":
    SITE.mkdir(exist_ok=True)
    build_render_js()
    build_index()
    print("site/index.html and site/render.js generated from the hosted UI")
