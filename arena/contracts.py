"""What each call is actually worth — contract values by simulation, and the selector's regret.

`docs/measurements.md` §2 measured the rule-based trump selector against *random* bidding and
nothing else. Its weights in `krass_jass/data/trump_weights.json` were written by hand, and
the baseline and shove threshold have never been tuned, so the obvious question — how far is
it from the best call the hand could have made? — had no answer.

Common practice in trick-taking engines is to price calls by simulation: hold the bidder's
hand, deal the rest at random many times, play each contract out with the real card-play
bot, and read off what each call is worth. That is what this does.

**One design point makes the data far more useful than it looks.** The only thing in card
play that reads `declarer_seat` is the bidding prior (`DmctsAgent.read_bidding`), and it
measured null (§5e). Switch it off and a round's play no longer depends on *who* declared,
only on the contract and the deal. Forehand leads either way. So one value per contract per
deal prices the shove exactly as well — a shove is worth whatever contract the partner then
calls, on that same deal — and any selector, including one with retuned weights, can be scored
offline against the stored table without playing another card.

**The unit.** Values are `multiplier × (declaring team's points − the other team's)`, the
quantity the game score actually moves by. `RoundScore.total` already carries the multiplier,
so the difference of the two totals *is* that quantity — multiplying again, which the first
version of this file did, scores every call by the square of its multiplier and drives any fit
straight into Undenufe.

Usage::

    python -m arena.contracts generate --hands 2000 --deals 8 --out contracts.npz
    python -m arena.contracts regret contracts.npz
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from arena.arena import play_round  # noqa: E402
from krass_jass.agent import DmctsAgent  # noqa: E402
from krass_jass.rules import EVAL, SHOVE, Contract, RulesConfig  # noqa: E402
from krass_jass.trump import select_trump  # noqa: E402

N_CONTRACTS = 6

#: Card scoring as the game plays it, minus Weis and Stöck. Both are mostly independent of the
#: call and add variance; the match bonus is not, because a 157-point sweep is what Obenabe
#: and Undenufe hands are for.
LABEL_CFG: RulesConfig = EVAL.variant(match_bonus=100)


def label_agent(iterations: int = 2400) -> DmctsAgent:
    """The card player that prices the calls. `read_bidding` off, for the reason above."""
    return DmctsAgent(
        determinizations=40,
        iterations=max(1, iterations // 40),
        cfg=LABEL_CFG,
        read_bidding=False,
        label="contract-labeller",
    )


def _deal(seed: int, hand_index: int, deals: int) -> tuple[int, list[list[int]]]:
    """A forehand hand and `deals` completions of the other 27 cards, from `(seed, index)`."""
    rng = random.Random(f"contracts:{seed}:{hand_index}")
    deck = list(range(36))
    rng.shuffle(deck)
    own = deck[:9]
    rest = deck[9:]
    hand = sum(1 << c for c in own)
    out = []
    for _ in range(deals):
        rng.shuffle(rest)
        out.append([hand] + [sum(1 << c for c in rest[i * 9 : (i + 1) * 9]) for i in range(3)])
    return hand, out


def _label_chunk(args) -> list[tuple[int, int, list[int], list[int]]]:
    seed, indices, deals, iterations = args
    agent = label_agent(iterations)
    seats = {s: agent for s in range(4)}
    rows = []
    for h in indices:
        _, completions = _deal(seed, h, deals)
        for k, hands in enumerate(completions):
            # Common random numbers: every contract on this deal shares the decision seeds,
            # so the differences between contracts are not diluted by search noise.
            game_seed = seed * 1_000_003 + h * 64 + k
            values = []
            for c in range(N_CONTRACTS):
                contract = Contract(c)
                pts = play_round(hands, contract, 0, seats, LABEL_CFG, game_seed, "contracts")
                # `total` is already multiplied — see the note on the unit above.
                values.append(pts[0] - pts[1])
            rows.append((h, k, hands, values))
    return rows


def generate(hands: int, deals: int, seed: int, iterations: int, workers: int, out: Path) -> None:
    workers = max(1, min(workers, hands))
    chunks = [list(range(i, hands, workers)) for i in range(workers)]
    payload = [(seed, c, deals, iterations) for c in chunks if c]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for part in pool.map(_label_chunk, payload):
            rows.extend(part)
    rows.sort(key=lambda r: (r[0], r[1]))
    np.savez_compressed(
        out,
        hand_index=np.array([r[0] for r in rows], dtype=np.int32),
        hands=np.array([r[2] for r in rows], dtype=np.uint64),
        values=np.array([r[3] for r in rows], dtype=np.float64),
        seed=seed,
        iterations=iterations,
    )
    print(f"wrote {len(rows)} deals ({hands} hands x {deals}) to {out}")


# --------------------------------------------------------------------------------------------
# Regret


def load(path: Path) -> dict:
    data = np.load(path)
    return {k: data[k] for k in data.files}


def rule_choices(hands: np.ndarray, cfg: RulesConfig = LABEL_CFG, weights: dict | None = None):
    """Per deal: forehand's action (contract index, or 6 for a shove) and the contract played."""
    action = np.empty(len(hands), dtype=np.int64)
    played = np.empty(len(hands), dtype=np.int64)
    cache: dict[tuple[int, bool], object] = {}

    def choose(hand: int, forehand: bool):
        key = (hand, forehand)
        if key not in cache:
            cache[key] = select_trump(hand, forehand, cfg, weights)
        return cache[key]

    for i, row in enumerate(hands):
        first = choose(int(row[0]), True)
        if first == SHOVE:
            action[i] = N_CONTRACTS
            played[i] = int(choose(int(row[2]), False))
        else:
            action[i] = int(first)
            played[i] = int(first)
    return action, played


def _mean_se_by_hand(per_deal: np.ndarray, hand_index: np.ndarray) -> tuple[float, float]:
    """Mean over deals, standard error clustered by hand — deals sharing a hand correlate."""
    hands = np.unique(hand_index)
    per_hand = np.array([per_deal[hand_index == h].mean() for h in hands])
    return float(per_hand.mean()), float(per_hand.std(ddof=1) / np.sqrt(len(per_hand)))


def regret(path: Path) -> None:
    d = load(path)
    values, hands, hidx = d["values"], d["hands"], d["hand_index"]
    n = len(values)
    rows = np.arange(n)
    action, played = rule_choices(hands)
    rule_value = values[rows, played]

    # Seven actions per deal: the six contracts called by forehand, and the shove, whose value
    # is whatever the partner calls with the rule selector on that deal — computed for every
    # deal, whatever forehand actually chose.
    partner_call = np.array([int(select_trump(int(h), False, LABEL_CFG)) for h in hands[:, 2]])
    shove_value = values[rows, partner_call]
    actions = np.concatenate([values, shove_value[:, None]], axis=1)  # (n, 7)

    # Per-hand best action, cross-fitted: choose on half of a hand's deals, score on the other
    # half, then swap. Choosing and scoring on the same deals rewards picking the luckiest
    # noise, which is what an in-sample maximum measures.
    deal_k = np.zeros(n, dtype=np.int64)
    for h in np.unique(hidx):
        m = np.where(hidx == h)[0]
        deal_k[m] = np.arange(len(m))
    best_cf = np.empty(n)
    for fold in (0, 1):
        choose_on = deal_k % 2 == fold
        score_on = ~choose_on
        for h in np.unique(hidx):
            m = hidx == h
            pick = actions[m & choose_on].mean(axis=0).argmax()
            best_cf[m & score_on] = actions[m & score_on, pick]

    random_value = values.mean(axis=1)
    hindsight = values.max(axis=1)

    print(f"{n} deals, {len(np.unique(hidx))} hands, card play at {int(d['iterations'])} iterations")
    print("value = multiplier x (declaring team's points - other team's), per round\n")
    for name, v in [
        ("random contract", random_value),
        ("rule-based selector", rule_value),
        ("per-hand best call (cross-fitted)", best_cf),
        ("best contract in hindsight (unattainable)", hindsight),
    ]:
        mean, se = _mean_se_by_hand(v, hidx)
        print(f"  {name:<44} {mean:8.2f} ± {se:5.2f}")

    gap = best_cf - rule_value
    mean, se = _mean_se_by_hand(gap, hidx)
    print(f"\n  regret of the rule selector vs per-hand best {mean:8.2f} ± {se:5.2f}")

    freq = np.bincount(action, minlength=7) / n
    names = [Contract(c).name.lower() for c in range(6)] + ["shove"]
    print("\n  rule selector's calls: " + ", ".join(f"{nm} {f:.1%}" for nm, f in zip(names, freq)))
    best_fh = np.array([actions[hidx == h].mean(axis=0).argmax() for h in np.unique(hidx)])
    freq = np.bincount(best_fh, minlength=7) / len(best_fh)
    print("  per-hand best calls:   " + ", ".join(f"{nm} {f:.1%}" for nm, f in zip(names, freq)))

    # Where the regret lives: by what the selector called.
    print("\n  regret by the selector's call")
    for a in range(7):
        m = action == a
        if m.sum() < 20:
            continue
        print(f"    {names[a]:<9} n={m.sum():<6} {gap[m].mean():7.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--hands", type=int, default=2000)
    g.add_argument("--deals", type=int, default=8)
    g.add_argument("--seed", type=int, default=1)
    g.add_argument("--iterations", type=int, default=2400)
    g.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    g.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("regret")
    r.add_argument("path", type=Path)
    args = ap.parse_args()
    if args.cmd == "generate":
        generate(args.hands, args.deals, args.seed, args.iterations, args.workers, args.out)
    else:
        regret(args.path)


if __name__ == "__main__":
    main()
