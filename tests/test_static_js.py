"""The browser modules have to parse, and nothing in Python's test suite runs them.

This exists because a broken one *shipped*. Two string literals were written on consecutive
lines without the `+` joining them — legal-looking prose, and a syntax error. The module
failed to parse, the dynamic `import("./about.js")` in menu.js rejected, and the catch there
turned it into "the measurements could not be loaded" — a message that points at the data
rather than at the code, on a page that had been tested a commit earlier.

There is no JavaScript runtime in CI, so this does not try to *execute* the modules. It
checks the one structural property that broke, plus the brace and quote balance that catches
most of the rest. A real parser would be better; a cheap check that runs is better than a
good one that does not.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "web/static"
MODULES = sorted(STATIC.glob("*.js")) + sorted(
    (Path(__file__).resolve().parents[1] / "site-src").glob("*.js")
)

#: A line ending a string literal, where the next line starts one, with nothing joining
#: them. In JavaScript that is `"a" "b"` and it does not parse.
ENDS_STRING = re.compile(r'"\s*$')


def _code_lines(source: str) -> list[tuple[int, str]]:
    """Lines with block comments and full-line `//` comments removed.

    Crude on purpose: prose in this repo is full of apostrophes and quotes, and anything
    clever enough to tokenise properly would be a parser, which is the thing we do not have.
    """
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    out = []
    for n, line in enumerate(source.splitlines(), 1):
        if line.lstrip().startswith("//"):
            continue
        out.append((n, line))
    return out


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_adjacent_string_literals_are_joined(path: Path):
    """`"a"` then `"b"` on the next line needs a `+`. This is the bug that shipped."""
    lines = _code_lines(path.read_text())
    for i in range(len(lines) - 1):
        _, cur = lines[i]
        nxt_no, nxt = lines[i + 1]
        stripped = cur.rstrip()
        if not ENDS_STRING.search(stripped):
            continue
        if stripped.endswith(("+", ",", "{", "[", "(", ";", "=")):
            continue
        if nxt.lstrip().startswith('"'):
            pytest.fail(
                f"{path.name}:{nxt_no} starts a string literal right after one ends — "
                f"insert a '+' or a ',':\n  {stripped.strip()}\n  {nxt.strip()}"
            )


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_braces_balance(path: Path):
    source = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    for open_c, close_c in (("{", "}"), ("[", "]"), ("(", ")")):
        assert source.count(open_c) == source.count(close_c), (
            f"{path.name}: unbalanced {open_c}{close_c}"
        )


def test_every_documented_language_carries_the_same_keys():
    """A key added to one language and forgotten in three is invisible until somebody
    switches language — `about()` falls back to English and nothing looks broken."""
    import json

    source = (STATIC / "about-i18n.js").read_text()
    blocks = re.findall(r"\n  (en|de|fr|it): \{(.*?)\n  \},", source, flags=re.S)
    assert len(blocks) == 4, "expected four language blocks"
    keys = {lang: set(re.findall(r'^\s+"([\w.]+)":', body, flags=re.M)) for lang, body in blocks}
    reference = keys["en"]
    for lang in ("de", "fr", "it"):
        missing = reference - keys[lang]
        assert not missing, f"{lang} is missing {sorted(missing)}"
    assert json.dumps(sorted(reference))          # keys are plain strings
