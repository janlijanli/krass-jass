"""Our bot against an external opponent: double rounds, same seed both halves, paired test.

    python -m arena.opponents.match luegl --deals 100 --seed 1
    python -m arena.opponents.match luegl --deals 400 --seed 1 --ours belief_alpha=0
    python -m arena.opponents.match --report .runs/opp-luegl-1-shipped.jsonl [other.jsonl]
    python -m arena.opponents.match --diagnose .runs/opp-luegl-1-shipped.jsonl

After `arena/jass_the_ripper.py`, generalised over the JSON bridge (`bridge.py`). Every deal goes to
a JSON-lines file as it finishes and a rerun resumes from it. Each record carries what the diagnosis
needs, per half: the contract, the forehand, the declaring seat (so who chose trump and whether the
forehand shoved) and both teams' points — `--diagnose` cuts the share by those.

Opponents are registered in `OPPONENTS`; their checkouts and venvs live outside the repo, under
`$KJ_EXT` (default `/home/user/ext`), as `docs/opponents/<name>.md` describes.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import arena.arena as A  # noqa: E402
from arena.ab import build  # noqa: E402
from arena.arena import deal_spec, paired_test, play_round  # noqa: E402
from arena.opponents.bridge import BridgeAgent, count_events  # noqa: E402
from krass_jass.rules import EVAL, HOUSE, Contract  # noqa: E402

CFGS = {"eval": EVAL, "house": HOUSE.variant(target_score=None)}
EXT = Path(os.environ.get("KJ_EXT", "/home/user/ext"))
SERVERS = Path(__file__).resolve().parent / "servers"
LOG_DIR = ".runs/opponents"


def opponent(name: str, cfg) -> BridgeAgent:
    if name == "luegl":
        return BridgeAgent(cfg=cfg, name="luegl", python=str(EXT / "venvs/luegl/bin/python"),
                           server=str(SERVERS / "luegl_server.py"),
                           args=(str(EXT / "luegl_JassAI"),), log_dir=LOG_DIR)
    if name == "standin":
        # Our own random-legal server: tests the bridge and this runner, runs no external code.
        return BridgeAgent(cfg=cfg, name="standin", python=sys.executable,
                           server=str(SERVERS / "standin_server.py"), log_dir=LOG_DIR)
    raise SystemExit(f"unknown opponent {name!r}")


OPPONENTS = ("luegl", "standin")

# -- one deal ----------------------------------------------------------------------------------

_BIDS: list = []
_choose = A.choose_contract


def _recording_choose(hands, forehand, seats, cfg):
    contract, declarer = _choose(hands, forehand, seats, cfg)
    _BIDS.append((int(contract), declarer))
    return contract, declarer


A.choose_contract = _recording_choose  # play_round looks it up at call time; arena-only patch


def _half(hands, leader, seats, cfg, game_seed, ours_even: bool) -> dict:
    _BIDS.clear()
    pts = play_round(hands, None, leader, seats, cfg, game_seed)
    contract, declarer = _BIDS[-1]
    ours = 0 if ours_even else 1
    return {"contract": contract, "forehand": leader, "declarer": declarer,
            "ours_declare": declarer % 2 == ours, "shoved": declarer != leader,
            "ours": pts[ours], "theirs": pts[1 - ours]}


def _deal(args) -> dict:
    ours, theirs, cfg, seed, index = args
    hands, _, leader, game_seed = deal_spec(seed, index, None)
    first = _half(hands, leader, {0: ours, 2: ours, 1: theirs, 3: theirs}, cfg, game_seed, True)
    second = _half(hands, leader, {0: theirs, 2: theirs, 1: ours, 3: ours}, cfg, game_seed, False)
    a = first["ours"] + second["ours"]
    total = a + first["theirs"] + second["theirs"]
    return {"deal": index, "share": a / total if total else 0.5, "halves": [first, second]}


# -- files and reports ---------------------------------------------------------------------------

def _rows(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {r["deal"]: r for r in rows}


def report(paths: list[Path]) -> None:
    arms = [{i: r["share"] for i, r in _rows(p).items()} for p in paths]
    for p, arm in zip(paths, arms):
        shares = list(arm.values())
        _, pv = paired_test([s - 0.5 for s in shares])
        print(f"{p.name}: {statistics.fmean(shares):.2%} ± {statistics.stdev(shares):.2%}  "
              f"n={len(shares)}  p={pv:.2e}")
    if len(arms) == 2:
        common = sorted(set(arms[0]) & set(arms[1]))
        diff = [arms[0][i] - arms[1][i] for i in common]
        _, pv = paired_test(diff)
        print(f"{paths[0].name} - {paths[1].name}: {statistics.fmean(diff):+.2%} "
              f"± {statistics.stdev(diff) / len(diff) ** 0.5:.2%} (se)  n={len(diff)}  p={pv:.2e}")


def diagnose(path: Path, worst: int = 5) -> None:
    """Points share cut by contract, by who declared, and by shoving; then the worst deals."""
    rows = _rows(path)
    halves = [h for r in rows.values() for h in r["halves"]]

    def line(label, hs):
        o, t = sum(h["ours"] for h in hs), sum(h["theirs"] for h in hs)
        print(f"  {label:<28} n={len(hs):<4} our share {o / (o + t) if o + t else 0.5:6.1%}  "
              f"mean ours {o / max(1, len(hs)):6.1f}  theirs {t / max(1, len(hs)):6.1f}")

    print(f"{path.name}: {len(rows)} deals, {len(halves)} rounds")
    for who in (True, False):
        sub = [h for h in halves if h["ours_declare"] == who]
        line("we declare" if who else "they declare", sub)
        by = defaultdict(list)
        for h in sub:
            by[Contract(h["contract"]).name].append(h)
        for k in sorted(by):
            line(f"  {k}", by[k])
        line("  after a shove", [h for h in sub if h["shoved"]])
    ours_fh = [h for r in rows.values() for i, h in enumerate(r["halves"]) if (h["forehand"] % 2) == i % 2]
    theirs_fh = [h for r in rows.values() for i, h in enumerate(r["halves"]) if (h["forehand"] % 2) != i % 2]
    print(f"  shove rate: ours {sum(h['shoved'] for h in ours_fh) / max(1, len(ours_fh)):.1%} "
          f"(n={len(ours_fh)}), theirs {sum(h['shoved'] for h in theirs_fh) / max(1, len(theirs_fh)):.1%} "
          f"(n={len(theirs_fh)})")
    print(f"  worst {worst} deals for us:")
    for r in sorted(rows.values(), key=lambda r: r["share"])[:worst]:
        desc = "; ".join(f"{'we' if h['ours_declare'] else 'they'} {Contract(h['contract']).name}"
                         f"{' (shoved)' if h['shoved'] else ''} {h['ours']}:{h['theirs']}" for h in r["halves"])
        print(f"    deal {r['deal']:>4} share {r['share']:.1%}  {desc}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("opponent", nargs="?", choices=OPPONENTS)
    ap.add_argument("--deals", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--cfg", choices=sorted(CFGS), default="eval")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--iterations", type=int, default=153_600)
    ap.add_argument("--ours", nargs="*", default=[], help="DmctsAgent field=value pairs, as arena.ab")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--report", type=Path, nargs="+")
    ap.add_argument("--diagnose", type=Path)
    args = ap.parse_args()
    if args.report:
        return report(args.report)
    if args.diagnose:
        return diagnose(args.diagnose)
    if not args.opponent:
        ap.error("name an opponent")

    cfg = CFGS[args.cfg]
    ours = build(args.ours, args.iterations, cfg)  # 40 x 3,840 as served, unless told otherwise
    theirs = opponent(args.opponent, cfg)
    tag = "-".join(args.ours) or "shipped"
    out = args.out or Path(f".runs/opp-{args.opponent}-{args.seed}-{tag}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    before = count_events(LOG_DIR, theirs.name)
    done = _rows(out)
    todo = [i for i in range(args.deals) if i not in done]
    print(f"{out}: {len(done)} done, {len(todo)} to play", flush=True)
    t = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool, out.open("a") as fh:
        futures = [pool.submit(_deal, (ours, theirs, cfg, args.seed, i)) for i in todo]
        for n, f in enumerate(as_completed(futures), 1):
            fh.write(json.dumps(f.result()) + "\n")
            fh.flush()
            if n % 10 == 0:
                print(f"  {n}/{len(todo)} ({(time.time() - t) / 60:.0f} min)", flush=True)

    rows = _rows(out)
    shares = [r["share"] for r in rows.values()]
    _, pv = paired_test([s - 0.5 for s in shares])
    mean, std = statistics.fmean(shares), statistics.stdev(shares)
    after = count_events(LOG_DIR, theirs.name)
    ev = {k: after[k] - before[k] for k in after}
    print(f"{ours.name} vs {args.opponent}: {mean:.2%} ± {std:.2%}  n={len(shares)}  p={pv:.2e}  "
          f"(this run: {ev['calls']} calls, {ev['errors']} errors, {ev['illegal']} illegal)")
    record = {
        "a": args.ours or ["shipped"], "b": [args.opponent], "deals": len(shares), "seed": args.seed,
        "iterations": ours.determinizations * ours.iterations, "cfg": args.cfg, "a_share": mean,
        "std": std, "p": pv, "se": std / len(shares) ** 0.5, "opponent_calls": ev["calls"],
        "opponent_errors": ev["errors"], "opponent_illegal": ev["illegal"],
        "minutes": round((time.time() - t) / 60, 1), "when": time.strftime("%Y-%m-%d %H:%M"),
    }
    if args.opponent == "standin":
        return  # a test of the plumbing, not a result
    with (Path(__file__).resolve().parent / "results.jsonl").open("a") as fh:
        fh.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
