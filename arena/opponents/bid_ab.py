"""Two bidders for our bot, A/B'd against one opponent on the same deals: only the deals they bid differently.

Our card play does not read the trump selector (the bid likelihood in the beliefs models every seat
by the shipped selector on the house table, whatever the arm), the opponents are deterministic given
the seed, and in a double round our team holds the forehand seat in exactly one half. So on a deal
where both bidders make the same call for our team — forehand's choice, and the partner's when
forehand shoves — the two arms play the same two rounds card for card and their difference is
exactly zero. Only the deals where the bids differ are played: the opponent's half once (it is the
same for both arms), ours once per arm. The paired difference is over *all* deals, the rest
counting as zeros, and it is exact, not an estimate of them.

    python -m arena.opponents.bid_ab jassformer --cfg chibre --deals 400 --a trump_scale=1
    python -m arena.opponents.bid_ab self --cfg flat --deals 1000 --a trump_scale=1
    python -m arena.opponents.bid_ab pyschieber --cfg eval --deals 400 --a <field=value>

Opponents: `jassformer` (chibre: our bids restricted to the suits, as `arena.opponents.jassformer`),
`pyschieber`, `donald_trumpf`, and `self` — the shipped bot as the opponent. Every deal goes to a
JSON-lines file as it is decided and a rerun resumes from it.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from arena.ab import build  # noqa: E402
from arena.arena import choose_contract, deal_spec, paired_test  # noqa: E402
from arena.opponents.common import play_round_logged  # noqa: E402
from krass_jass.rules import EVAL, HOUSE, Contract  # noqa: E402

FLAT = EVAL.variant(multipliers={c: 1 for c in Contract})
CHIBRE = EVAL.variant(multipliers={
    Contract.DIAMONDS: 1, Contract.HEARTS: 1, Contract.SPADES: 2, Contract.CLUBS: 1,
    Contract.OBENABE: 1, Contract.UNDENUFE: 1,
})
CFGS = {"eval": EVAL, "house": HOUSE.variant(target_score=None), "flat": FLAT, "chibre": CHIBRE}
OPPONENTS = ("jassformer", "pyschieber", "donald_trumpf", "self")


def make_opponent(name: str, cfg, seed: int, iterations: int = 153_600):
    if name == "jassformer":
        from arena.opponents.jassformer import JassFormer
        return JassFormer(cfg=cfg, log=f".runs/bid_ab-jassformer-{seed}.log")
    if name == "pyschieber":
        from arena.opponents.pyschieber import Pyschieber
        return Pyschieber(cfg=cfg, log=f".runs/bid_ab-pyschieber-{seed}.jsonl")
    if name == "donald_trumpf":
        from arena.opponents.donald_trumpf import DonaldTrumpf
        return DonaldTrumpf(cfg=cfg, log=f".runs/bid_ab-donald_trumpf-{seed}.jsonl")
    if name == "self":
        return build([], iterations, cfg)
    raise SystemExit(f"unknown opponent {name!r}")


def make_ours(pairs: list[str], cfg, cfg_name: str, iterations: int = 153_600):
    inner = build(pairs, iterations, cfg)  # 40 x 3,840 as served, unless the pairs say otherwise
    if cfg_name == "chibre":
        from arena.opponents.jassformer import SuitsOnly
        return SuitsOnly(inner=inner, cfg=cfg)
    return inner


def _bid(agent, hands, leader, cfg):
    return choose_contract(hands, leader, {leader: agent, (leader + 2) % 4: agent}, cfg)


def _deal(args) -> dict:
    a, b, theirs, cfg, seed, index = args
    hands, _, leader, game_seed = deal_spec(seed, index, None)
    bid_a, bid_b = _bid(a, hands, leader, cfg), _bid(b, hands, leader, cfg)
    row = {"deal": index, "leader": leader,
           "bid_a": [int(bid_a[0]), bid_a[1]], "bid_b": [int(bid_b[0]), bid_b[1]]}
    if bid_a == bid_b:
        return {**row, "diff": 0.0}
    # Half 0: ours on seats 0/2. Our team bids in the half where it holds the forehand seat.
    ours_bid_half = leader % 2
    shares = {}
    other = None
    for arm, agent in (("a", a), ("b", b)):
        halves = [None, None]
        for h, seats in enumerate(({0: agent, 2: agent, 1: theirs, 3: theirs},
                                   {1: agent, 3: agent, 0: theirs, 2: theirs})):
            if h != ours_bid_half and other is not None:
                halves[h] = other
                continue
            halves[h] = play_round_logged(hands, leader, seats, cfg, game_seed)
            if h != ours_bid_half:
                other = halves[h]
        ours = halves[0]["points"][0] + halves[1]["points"][1]
        total = ours + halves[0]["points"][1] + halves[1]["points"][0]
        shares[arm] = ours / total if total else 0.5
        row[f"points_{arm}"] = halves[ours_bid_half]["points"]
    row["points_other"] = other["points"]
    return {**row, "share_a": shares["a"], "share_b": shares["b"], "diff": shares["a"] - shares["b"]}


def load(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {r["deal"]: r for r in rows}


def summarise(rows: dict[int, dict], deals: int) -> dict:
    rows = {i: r for i, r in rows.items() if i < deals}
    diffs = [r["diff"] for r in rows.values()]
    _, pv = paired_test(diffs)
    n = len(diffs)
    mean, std = statistics.fmean(diffs), statistics.stdev(diffs)
    changed = [r for r in rows.values() if r["bid_a"] != r["bid_b"]]
    print(f"A - B: {mean:+.3%} ± {std / n ** 0.5:.3%} (se)  n={n}  p={pv:.3g}  "
          f"bids differ on {len(changed)} deals ({len(changed) / n:.1%})")
    for label, key in (("A", "bid_a"), ("B", "bid_b")):
        nt = sum(r[key][0] >= 4 for r in rows.values())
        sh = sum(r[key][1] != r["leader"] for r in rows.values())
        print(f"  {label}: our forehand shoves {sh / n:.1%}, Obenabe/Undenufe {nt / n:.1%} of our calls")
    return {"diff": mean, "se": std / n ** 0.5, "p": pv, "n": n, "changed": len(changed)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("opponent", choices=OPPONENTS)
    ap.add_argument("--cfg", choices=sorted(CFGS), default="eval")
    ap.add_argument("--a", nargs="*", default=[], help="the candidate: DmctsAgent field=value pairs")
    ap.add_argument("--b", nargs="*", default=[], help="the baseline; empty is the shipped bot")
    ap.add_argument("--deals", type=int, default=400)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--iterations", type=int, default=153_600, help="ours (and `self`'s); smoke tests only")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    cfg = CFGS[args.cfg]
    a = make_ours(args.a, cfg, args.cfg, args.iterations)
    b = make_ours(args.b, cfg, args.cfg, args.iterations)
    theirs = make_opponent(args.opponent, cfg, args.seed, args.iterations)
    tag = f"{'-'.join(args.a) or 'shipped'}-vs-{'-'.join(args.b) or 'shipped'}"
    out = args.out or Path(f".runs/bid_ab-{args.opponent}-{args.cfg}-{args.seed}-{tag}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    done = load(out)
    todo = [i for i in range(args.deals) if i not in done]
    print(f"{out}: {len(done)} done, {len(todo)} to decide", flush=True)
    t = time.time()
    # Cheap first: which deals need playing at all. Bidding is a few microseconds a hand.
    with out.open("a") as fh:
        same = []
        for i in todo:
            hands, _, leader, _ = deal_spec(args.seed, i, None)
            ba, bb = _bid(a, hands, leader, cfg), _bid(b, hands, leader, cfg)
            if ba == bb:
                row = {"deal": i, "leader": leader, "bid_a": [int(ba[0]), ba[1]],
                       "bid_b": [int(bb[0]), bb[1]], "diff": 0.0}
                fh.write(json.dumps(row) + "\n")
                same.append(i)
        fh.flush()
        todo = [i for i in todo if i not in set(same)]
        print(f"  {len(same)} deals bid alike (difference 0), {len(todo)} to play", flush=True)
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(_deal, (a, b, theirs, cfg, args.seed, i)) for i in todo]
            for n, f in enumerate(as_completed(futures), 1):
                fh.write(json.dumps(f.result()) + "\n")
                fh.flush()
                if n % 10 == 0:
                    print(f"  {n}/{len(todo)} ({(time.time() - t) / 60:.0f} min)", flush=True)

    s = summarise(load(out), args.deals)
    if args.iterations != 153_600:
        return  # a smoke test, not a result
    record = {"kind": "bid_ab", "opponent": args.opponent, "cfg": args.cfg, "a": args.a, "b": args.b,
              "seed": args.seed, **s, "minutes": round((time.time() - t) / 60, 1),
              "when": time.strftime("%Y-%m-%d %H:%M")}
    with (Path(__file__).resolve().parent / "results.jsonl").open("a") as fh:
        fh.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
