#!/usr/bin/env python3
"""Generate site/index.html and site/render.js from the hosted UI.

Deliberately *derived* rather than copied by hand. The card fan, the Weis bubbles, the
scorecard and the CSS are the same code the server version uses; only the transport differs,
so keeping a second copy in sync by hand would guarantee they drift.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

CONTRACTS = {"DIAMONDS": 1, "HEARTS": 2, "SPADES": 1, "CLUBS": 2, "OBENABE": 3, "UNDENUFE": 4}
TARGETS = (1000, 2000, 2500)


def build_render_js() -> None:
    """Everything from table.js up to the WebSocket, with the sender left injectable."""
    src = (ROOT / "web/static/table.js").read_text()
    # Cut at the transport, not at the menu: the menu and the "How it works" panels are a
    # shared module now, so both builds get them.
    render = src[: src.index('import { initMenu } from "./menu.js";')]
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


def asset_version() -> str:
    """Short hash over the built assets.

    Appended to the asset URLs so a deploy is not served half-old. Static hosts cache
    aggressively, and a page running new HTML against old CSS fails in ways that look like
    bugs in the code — which cost time here before it cost a user anything.
    """
    digest = hashlib.sha256()
    # The wasm is in the hash *and* gets a versioned URL. Leaving the engine unversioned is
    # the worst version of this bug: new JavaScript against an old engine is a view that is
    # missing fields the page expects, which looks like a code bug rather than a stale file.
    for name in sorted(
        (
            "table.css", "cards.js", "about.js", "menu.js", "tafel.js",
            "i18n.js", "about-i18n.js", "walkthrough.js", "talk.js",
            "render.js", "solo.js", "engine.js", "krass_jass_core.wasm",
        )
    ):
        path = SITE / name
        if path.exists():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:8]


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
        row = body.replace("{{ name|upper }}", name)
        row = row.replace("{{ name|capitalize }}", name.capitalize())
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

    # A source that already carries a version froze one in: the first build stamped it, and
    # every later build's replace then matched nothing. That is how `solo.js` spent several
    # builds importing an engine from a deploy nobody could name. Fail loudly instead.
    stale = [
        f"{path}:{line}"
        for folder in (ROOT / "site-src", ROOT / "web/static")
        for path in sorted(folder.glob("*.js"))
        for line in path.read_text().splitlines()
        if "?v=" in line
    ]
    if stale:
        raise SystemExit(f"versioned URL in a source file: {stale[:3]}")

    version = asset_version()
    html = html.replace('href="table.css"', f'href="table.css?v={version}"')
    html = html.replace('src="solo.js"', f'src="solo.js?v={version}"')
    (SITE / "index.html").write_text(html)

    # The modules import each other by bare name, so version those too — otherwise solo.js
    # is fresh and everything it pulls in is not.
    for name in ("solo.js", "render.js", "menu.js", "engine.js", "about.js", "walkthrough.js"):
        path = SITE / name
        text = path.read_text()
        for dep in (
            "engine.js", "render.js", "menu.js", "cards.js", "about.js", "tafel.js",
            "i18n.js", "about-i18n.js", "walkthrough.js", "talk.js",
        ):
            text = text.replace(f'"./{dep}"', f'"./{dep}?v={version}"')
        text = text.replace('"measurements.json"', f'"measurements.json?v={version}"')
        text = text.replace('"krass_jass_core.wasm"', f'"krass_jass_core.wasm?v={version}"')
        path.write_text(text)


def copy_assets() -> None:
    """Everything in `site/` is generated. Nothing is edited there.

    That is not tidiness — the versioning step below rewrites asset URLs, and when the
    sources lived in the output directory it rewrote *them*, so the second build found
    `"engine.js?v=<first build>"` instead of `"engine.js"` and the first version froze in
    permanently. Sources live in `site-src/` and `web/static/`; `site/` is output.

    `docs/measurements.json` is copied for the same reason it is copied into `web/static/`:
    it is the single source for every number either build shows a reader.
    """
    for name in (
        "table.css", "cards.js", "about.js", "menu.js", "tafel.js",
        "i18n.js", "about-i18n.js", "walkthrough.js", "talk.js",
    ):
        (SITE / name).write_text((ROOT / "web/static" / name).read_text())
    for name in ("engine.js", "solo.js", "README.md"):
        (SITE / name).write_text((ROOT / "site-src" / name).read_text())
    (SITE / "measurements.json").write_text((ROOT / "docs/measurements.json").read_text())


if __name__ == "__main__":
    SITE.mkdir(exist_ok=True)
    copy_assets()
    build_render_js()
    build_index()
    print("site/index.html and site/render.js generated from the hosted UI")
