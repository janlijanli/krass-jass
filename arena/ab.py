"""A/B two `DmctsAgent` configurations from the command line, and keep the result.

Every experiment in `docs/measurements.md` was a one-off script. This is the same protocol —
double rounds, common random numbers, paired test — with the configuration named on the
command line and every result appended as a JSON line, so a number can be traced back to the
exact settings that produced it.

    python -m arena.ab --a belief_alpha=1.0 --deals 2000 --seed 91 --cfg house

`--a` and `--b` take `field=value` pairs for `DmctsAgent`; anything not named keeps its
default, so `--b` empty is the shipped bot. Points are already scaled by the contract
multiplier (`RoundScore.total`), so a share across a double round prices bidding changes too.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.arena import match  # noqa: E402
from krass_jass.agent import DmctsAgent  # noqa: E402
from krass_jass.rules import EVAL, HOUSE  # noqa: E402

CFGS = {"eval": EVAL, "house": HOUSE.variant(target_score=None)}


def parse(pairs: list[str]) -> dict:
    fields = {f.name: f for f in dataclasses.fields(DmctsAgent)}
    out = {}
    for pair in pairs:
        key, _, raw = pair.partition("=")
        if key not in fields:
            raise SystemExit(f"DmctsAgent has no field {key!r}")
        default = fields[key].default
        if isinstance(default, tuple):
            out[key] = tuple(float(v) for v in raw.split(","))
        elif isinstance(default, bool):
            out[key] = raw.lower() in ("1", "true", "yes", "on")
        elif isinstance(default, int):
            out[key] = int(raw)
        elif isinstance(default, float):
            out[key] = float(raw)
        else:
            out[key] = raw
    return out


def build(pairs: list[str], iterations: int, cfg) -> DmctsAgent:
    # The shared budget is a default; an arm may name its own `iterations` or `determinizations`,
    # which is how an equal-time comparison gives a dearer search fewer of them.
    kw = {"determinizations": 40, "iterations": max(1, iterations // 40), "cfg": cfg,
          "label": ",".join(pairs) or "shipped"}
    kw.update(parse(pairs))
    return DmctsAgent(**kw)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", nargs="*", default=[])
    ap.add_argument("--b", nargs="*", default=[])
    ap.add_argument("--deals", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--iterations", type=int, default=153600)
    ap.add_argument("--cfg", choices=sorted(CFGS), default="house")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--log", type=Path, default=Path("arena/results.jsonl"))
    args = ap.parse_args()

    cfg = CFGS[args.cfg]
    a = build(args.a, args.iterations, cfg)
    b = build(args.b, args.iterations, cfg)
    t = time.time()
    result = match(a, b, deals=args.deals, seed=args.seed, cfg=cfg, workers=args.workers)
    elapsed = time.time() - t
    print(result, f"({elapsed / 60:.1f} min)")
    record = {
        "a": args.a, "b": args.b, "deals": args.deals, "seed": args.seed,
        "iterations": args.iterations, "cfg": args.cfg,
        "a_share": result.a_share, "std": result.std, "p": result.p_value,
        "se": result.std / (args.deals ** 0.5), "minutes": round(elapsed / 60, 1),
        "when": time.strftime("%Y-%m-%d %H:%M"),
    }
    with args.log.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
