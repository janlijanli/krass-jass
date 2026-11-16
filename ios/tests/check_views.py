"""Hold the Swift view model against what the engine really sends.

`TableState.swift` is a hand-written mirror of the JSON `game_view` builds in
`rust/src/wasm_api.rs`. A field the Swift side calls non-optional that the engine sometimes sends
as null (or leaves out) is a game that stops decoding on a phone, in the one phase where it
happens. Nothing on a Linux CI runner can compile Swift against the iOS SDK, so this reads the
struct declarations out of the Swift source and checks every view of whole games — all three
modes, dumped by `ffi_smoke.c` — against them: every declared field present, null only where
the Swift type is optional, every value of the declared type.

    ios/tests/run-ffi-smoke.sh --check-views
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SWIFT = Path(__file__).resolve().parents[1] / "KrassJass" / "Engine"
CARD = re.compile(r"^[DHSC][AKQJT9876]$")


def parse_swift(text: str) -> tuple[dict[str, dict[str, str]], dict[str, set[str]]]:
    """Struct name -> {field: type} and enum name -> raw values, by declaration."""
    structs: dict[str, dict[str, str]] = {}
    enums: dict[str, set[str]] = {}
    stack: list[tuple[str, str, int]] = []        # (kind, name, brace depth it opened at)
    depth = 0
    for raw in text.splitlines():
        line = raw.split("//")[0].strip()
        opened = re.match(r"(?:private\s+)?(struct|enum)\s+(\w+)\s*:\s*([^{]*)\{", line)
        if opened:
            kind, name, conforms = opened.groups()
            stack.append((kind, name, depth))
            if kind == "struct":
                structs[name] = {}
            elif "String" in conforms:
                enums[name] = set()
        elif stack and depth == stack[-1][2] + 1:
            kind, name, _ = stack[-1]
            field = re.match(r"let\s+(\w+)\s*:\s*([^=]+?)\s*$", line)
            if kind == "struct" and field:
                structs[name][field.group(1)] = field.group(2)
            case = re.match(r"case\s+(.+)$", line)
            if kind == "enum" and name in enums and case:
                for part in case.group(1).split(","):
                    part = part.strip()
                    explicit = re.match(r'(\w+)\s*=\s*"([^"]+)"', part)
                    enums[name].add(explicit.group(2) if explicit else part)
        depth += line.count("{") - line.count("}")
        while stack and depth <= stack[-1][2]:
            stack.pop()
    return structs, enums


def camel(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(part.capitalize() for part in rest)


class Checker:
    def __init__(self, structs, enums):
        self.structs, self.enums = structs, enums
        self.problems: set[str] = set()

    def check(self, value, swift_type: str, where: str) -> None:
        t = swift_type.strip()
        if t.endswith("?"):
            if value is not None:
                self.check(value, t[:-1], where)
            return
        if value is None:
            self.problems.add(f"{where}: null, but Swift says {t}")
            return
        if t.startswith("[") and t.endswith("]"):
            if not isinstance(value, list):
                self.problems.add(f"{where}: {type(value).__name__}, but Swift says {t}")
                return
            for item in value:
                self.check(item, t[1:-1], where + "[]")
            return
        ok = {
            "Int": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "Double": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "Bool": lambda v: isinstance(v, bool),
            "String": lambda v: isinstance(v, str),
            "Card": lambda v: isinstance(v, str) and bool(CARD.match(v)),
        }
        if t in ok:
            if not ok[t](value):
                self.problems.add(f"{where}: {value!r} is not a {t}")
        elif t in self.enums:
            if value not in self.enums[t]:
                self.problems.add(f"{where}: {value!r} is not a case of {t}")
        elif t in self.structs:
            if not isinstance(value, dict):
                self.problems.add(f"{where}: {type(value).__name__}, but Swift says {t}")
                return
            given = {camel(k): v for k, v in value.items()}
            for name, field_type in self.structs[t].items():
                if name not in given:
                    if not field_type.strip().endswith("?"):
                        self.problems.add(f"{where}.{name}: missing, but Swift says {field_type}")
                    continue
                self.check(given[name], field_type, f"{where}.{name}")
        else:
            self.problems.add(f"{where}: check_views.py does not know the Swift type {t}")


def main(dump: str) -> int:
    text = "\n".join(p.read_text() for p in sorted(SWIFT.glob("*.swift")))
    checker = Checker(*parse_swift(text))
    counts = {"V": 0, "A": 0}
    seen: set[tuple[str, str]] = set()
    for line in Path(dump).read_text().splitlines():
        tag, payload = line[0], json.loads(line[2:])
        counts[tag] += 1
        if tag == "V":
            seen.add((payload["mode"], payload["phase"]))
            checker.check(payload, "TableState", "view")
        else:
            checker.check(payload, "Advice", "advice")
    for problem in sorted(checker.problems):
        print("  " + problem)
    print(f"{counts['V']} views, {counts['A']} advice payloads, "
          f"{len(seen)} mode/phase pairs: {', '.join(sorted('/'.join(s) for s in seen))}")
    # Every phase of every game must have been seen, or the check proved less than it says.
    wanted = {("schieber", p) for p in ("bidding", "weis", "playing", "round_over", "game_over")}
    wanted |= {("sidi", p) for p in ("bidding", "playing", "round_over", "game_over")}
    wanted |= {("coiffeur", p) for p in ("bidding", "playing", "round_over", "game_over")}
    for missing in sorted(wanted - seen):
        print(f"  never saw {'/'.join(missing)}")
    return 1 if checker.problems or wanted - seen else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
