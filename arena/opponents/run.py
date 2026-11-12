"""Our bot against an external opponent: double rounds, same seed for both halves, paired test.

    python -m arena.opponents.run --opponent sobrinth --deals 100 --seed 1
    python -m arena.opponents.run --report .runs/opp-sobrinth-1-shipped.jsonl
    python -m arena.opponents.run --diagnose .runs/opp-sobrinth-1-shipped.jsonl

The `JassTheRipper` runner, generalised over `arena/opponents/registry.py`, and with each half
of each deal written out — who chose trump, what, whether it was shoved, both teams' points —
so a result that is not a clear win can be taken apart by contract and by side.

`play_half` is `arena.arena.play_round` with the bidding's outcome kept; the rest is the same
code path (`choose_contract`, `resolve_weis`, `build_observation`, `RoundState`). The deals
come from `deal_spec`, so the same seed is the same deals for every opponent.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from arena.ab import build
from arena.arena import choose_contract, deal_spec, paired_test, resolve_weis
from arena.opponents.registry import OPPONENTS, make
from krass_jass.observation import build_observation, derive_decision_seed
from krass_jass.rules import EVAL, HOUSE
from krass_jass.state import RoundState

CFGS = {"eval": EVAL, "house": HOUSE.variant(target_score=None)}


def play_half(hands, leader, seats, cfg, game_seed, game_id="arena") -> dict:
    contract, declarer = choose_contract(hands, leader, seats, cfg)
    weis, stoeck, shown, announced = resolve_weis(hands, contract, leader, cfg)
    state = RoundState(contract=contract, hands=list(hands), cfg=cfg, leader=leader)
    trick_no = 0
    seconds = defaultdict(float)
    while not state.done:
        seat = state.to_play
        obs = build_observation(
            state, seat, declarer_seat=declarer,
            decision_seed=derive_decision_seed(game_seed, game_id, seat, 0, trick_no),
            known_cards=tuple((s, c) for s, c in shown if state.hands[s] & (1 << c)),
            weis_announced=announced,
        )
        t = time.time()
        card = seats[seat].decide(obs)
        seconds[seat % 2] += time.time() - t
        state.play(card)  # the engine re-validates
        trick_no = len(state.tricks_played)
    total = state.score(weis=weis, stoeck=stoeck).total
    return {"forehand": leader, "declarer": declarer, "contract": int(contract),
            "shoved": declarer != leader, "points": list(total),
            "seconds": [round(seconds[0], 2), round(seconds[1], 2)]}


def _deal(args) -> dict:
    ours, theirs, cfg, seed, index = args
    hands, _, leader, game_seed = deal_spec(seed, index, None)
    # Half 0: we sit 0/2 (team 0). Half 1: we sit 1/3 (team 1). Same seed: common random numbers.
    halves = [play_half(hands, leader, {0: ours, 2: ours, 1: theirs, 3: theirs}, cfg, game_seed),
              play_half(hands, leader, {0: theirs, 2: theirs, 1: ours, 3: ours}, cfg, game_seed)]
    halves[0]["us"], halves[1]["us"] = 0, 1
    ours_pts = halves[0]["points"][0] + halves[1]["points"][1]
    total = sum(halves[0]["points"]) + sum(halves[1]["points"])
    return {"deal": index, "share": ours_pts / total if total else 0.5, "halves": halves}


def _load(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {r["deal"]: r for r in rows}


def summary(rows: list[dict]) -> tuple[float, float, float]:
    shares = [r["share"] for r in rows]
    _, pv = paired_test([s - 0.5 for s in shares])
    return statistics.fmean(shares), statistics.stdev(shares), pv


def report(paths: list[Path]) -> None:
    arms = [_load(p) for p in paths]
    for p, arm in zip(paths, arms):
        mean, std, pv = summary(list(arm.values()))
        print(f"{p.name}: {mean:.2%} ± {std:.2%}  n={len(arm)}  p={pv:.2e}")
    if len(arms) == 2:
        common = sorted(set(arms[0]) & set(arms[1]))
        diff = [arms[0][i]["share"] - arms[1][i]["share"] for i in common]
        _, pv = paired_test(diff)
        print(f"difference: {statistics.fmean(diff):+.2%} ± "
              f"{statistics.stdev(diff) / len(diff) ** 0.5:.2%} (se)  n={len(diff)}  p={pv:.2e}")


CONTRACTS = ["Diamonds", "Hearts", "Spades", "Clubs", "Obenabe", "Undenufe"]


def diagnose(path: Path, worst: int = 5) -> None:
    """Our points share split by who chose trump, which contract, and shoves; then the worst deals."""
    rows = list(_load(path).values())
    mean, std, pv = summary(rows)
    print(f"{path.name}: {mean:.2%} ± {std:.2%}  n={len(rows)}  p={pv:.2e}")
    by = defaultdict(lambda: [0, 0, 0])  # key -> [our points, all points, halves]
    shoves = {"us": [0, 0], "them": [0, 0]}  # [shoved, forehand halves]
    secs = [0.0, 0.0]
    for r in rows:
        for h in r["halves"]:
            us = h["us"]
            ours, total = h["points"][us], sum(h["points"])
            side = "us" if h["declarer"] % 2 == us else "them"
            fh = "us" if h["forehand"] % 2 == us else "them"
            shoves[fh][0] += h["shoved"]
            shoves[fh][1] += 1
            for key in (("declarer", side), ("contract", side, CONTRACTS[h["contract"]]),
                        ("shoved", side, h["shoved"])):
                by[key][0] += ours
                by[key][1] += total
                by[key][2] += 1
            secs[0] += h["seconds"][us]
            secs[1] += h["seconds"][1 - us]
    print(f"seconds per half: ours {secs[0] / (2 * len(rows)):.1f}, theirs {secs[1] / (2 * len(rows)):.1f}")
    for side in ("us", "them"):
        s, n = shoves[side]
        print(f"shove rate when {side} hold forehand: {s / n:.1%} ({s}/{n})")
    print(f"{'split':<34}{'halves':>7}{'our share':>11}{'our pts/half':>14}")
    for key in sorted(by, key=str):
        ours, total, n = by[key]
        print(f"{' / '.join(map(str, key)):<34}{n:>7}{ours / total:>11.1%}{ours / n:>14.1f}")
    print(f"worst {worst} deals:")
    for r in sorted(rows, key=lambda r: r["share"])[:worst]:
        desc = "; ".join(
            f"{'we' if h['declarer'] % 2 == h['us'] else 'they'} {CONTRACTS[h['contract']]}"
            f"{' (shoved)' if h['shoved'] else ''} -> us {h['points'][h['us']]}:{h['points'][1 - h['us']]}"
            for h in r["halves"])
        print(f"  deal {r['deal']}: {r['share']:.1%}  {desc}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--opponent", choices=sorted(OPPONENTS))
    ap.add_argument("--deals", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--cfg", choices=sorted(CFGS), default="eval")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--ours", nargs="*", default=[], help="DmctsAgent field=value pairs, as arena.ab")
    ap.add_argument("--set", nargs="*", default=[], help="opponent overrides, key=value (see registry)")
    ap.add_argument("--out", type=Path, help="per-deal results, one JSON line each; a rerun resumes")
    ap.add_argument("--report", type=Path, nargs="+", help="report one or two --out files and stop")
    ap.add_argument("--diagnose", type=Path, help="split one --out file by contract and side, and stop")
    ap.add_argument("--log", type=Path, default=Path("arena/opponents/results.jsonl"))
    args = ap.parse_args()
    if args.report:
        return report(args.report)
    if args.diagnose:
        return diagnose(args.diagnose)

    cfg = CFGS[args.cfg]
    ours = build(args.ours, 153_600, cfg)  # 40 x 3,840, as served, unless --ours says otherwise
    theirs = make(args.opponent, cfg, args.set)
    tag = "-".join(args.ours) or "shipped"
    variant = "-".join(args.set)
    out = args.out or Path(f".runs/opp-{args.opponent}{'-' + variant if variant else ''}-{args.seed}-{tag}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    done = _load(out)
    todo = [i for i in range(args.deals) if i not in done]
    if not done:  # a fresh run counts its own illegal cards and fallbacks; a resumed one keeps them
        for k in ("illegal", "fallback", "mismatch"):
            (Path(theirs.log_dir) / f"{theirs.name}-{k}.log").unlink(missing_ok=True)
    print(f"{out}: {len(done)} done, {len(todo)} to play", flush=True)
    t = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool, out.open("a") as fh:
        futures = [pool.submit(_deal, (ours, theirs, cfg, args.seed, i)) for i in todo]
        for n, f in enumerate(as_completed(futures), 1):
            fh.write(json.dumps(f.result()) + "\n")
            fh.flush()
            if n % 10 == 0 or n == len(todo):
                print(f"  {n}/{len(todo)} ({(time.time() - t) / 60:.0f} min)", flush=True)

    rows = [r for i, r in _load(out).items() if i < args.deals]
    mean, std, pv = summary(rows)
    print(f"{ours.name} vs {theirs.name}: {mean:.2%} ± {std:.2%}  n={len(rows)}  p={pv:.2e}")
    if not todo:
        return
    log_dir = Path(theirs.log_dir)
    counts = {k: sum(1 for _ in open(p)) if (p := log_dir / f"{theirs.name}-{k}.log").exists() else 0
              for k in ("illegal", "fallback", "mismatch")}
    record = {
        "a": args.ours or ["shipped"], "b": [theirs.name, *args.set], "deals": len(rows),
        "seed": args.seed, "iterations": ours.determinizations * ours.iterations, "cfg": args.cfg,
        "a_share": mean, "std": std, "p": pv, "se": std / len(rows) ** 0.5,
        "illegal": counts["illegal"], "fallback": counts["fallback"], "mismatch": counts["mismatch"],
        "minutes": round((time.time() - t) / 60, 1), "when": time.strftime("%Y-%m-%d %H:%M"),
    }
    with args.log.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
