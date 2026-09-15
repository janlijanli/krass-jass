"""Tune the rule-based trump selector's weights against simulated contract values.

`arena/contracts.py` prices every call on every deal. Because the selector's score is
**linear in its weights** — rank weights, a length bonus, side-suit weights, void and
singleton bonuses, top runs — the whole selector can be evaluated on tens of thousands of
deals as a matrix product, and the weights searched directly for the calls that are worth
the most. The shape of `krass_jass/data/trump_weights.json` does not change, so both the
Python selector and the Rust twin that `include_str!`s the file pick the result up unchanged.

The search is a simple accept-if-not-worse coordinate walk from the shipped weights. The
objective is piecewise constant, so gradients are no use; the walk is cheap because one
evaluation is a few milliseconds. Hands are split into a fitting and a held-out half, and
only the held-out number is reported as the gain.

Usage::

    python -m arena.fit_trump contracts.npz --out krass_jass/data/trump_weights.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from arena.contracts import LABEL_CFG, load  # noqa: E402
from krass_jass.rules import SHOVE, Contract  # noqa: E402
from krass_jass.trump import WEIGHTS_PATH, select_trump  # noqa: E402

RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6"]
MULT = np.array([LABEL_CFG.multiplier(Contract(c)) for c in range(6)], dtype=np.float64)

# Parameter layout.
TRUMP_RANK = slice(0, 9)
LENGTH = slice(9, 19)
SIDE = slice(19, 28)
VOID, SINGLE = 28, 29
OBEN = slice(30, 39)
UNDEN = slice(39, 48)
RUN = 48
BASELINE, SHOVE_T = 49, 50
N_PARAMS = 51


def theta_from(w: dict) -> np.ndarray:
    t = np.zeros(N_PARAMS)
    t[TRUMP_RANK] = [w["trump_rank_weights"][r] for r in RANKS]
    t[LENGTH] = [w["trump_length_bonus"][str(i)] for i in range(10)]
    t[SIDE] = [w["side_suit_weights"][r] for r in RANKS]
    t[VOID] = w["side_void_bonus"]["void"]
    t[SINGLE] = w["side_void_bonus"]["singleton"]
    t[OBEN] = [w["obenabe_weights"][r] for r in RANKS]
    t[UNDEN] = [w["undenufe_weights"][r] for r in RANKS]
    t[RUN] = w["no_trump_top_run_bonus"]["per_card"]
    t[BASELINE] = w["baseline"]["value"]
    t[SHOVE_T] = w["shove_threshold"]["value"]
    return t


def write_theta(w: dict, t: np.ndarray, note: str) -> dict:
    r = lambda x: round(float(x), 3)  # noqa: E731 - no exponents: the Rust reader wants plain decimals
    w = json.loads(json.dumps(w))
    for i, k in enumerate(RANKS):
        w["trump_rank_weights"][k] = r(t[TRUMP_RANK][i])
        w["side_suit_weights"][k] = r(t[SIDE][i])
        w["obenabe_weights"][k] = r(t[OBEN][i])
        w["undenufe_weights"][k] = r(t[UNDEN][i])
    for i in range(10):
        w["trump_length_bonus"][str(i)] = r(t[LENGTH][i])
    w["side_void_bonus"]["void"] = r(t[VOID])
    w["side_void_bonus"]["singleton"] = r(t[SINGLE])
    w["no_trump_top_run_bonus"]["per_card"] = r(t[RUN])
    w["baseline"]["value"] = r(t[BASELINE])
    w["shove_threshold"]["value"] = r(t[SHOVE_T])
    w["_fit"] = note
    return w


def features(hands: np.ndarray) -> np.ndarray:
    """`(n, 6, 49)`: raw contract score = features @ theta[:49], before baseline and stakes."""
    n = len(hands)
    bits = ((hands[:, None].astype(np.uint64) >> np.arange(36, dtype=np.uint64)) & np.uint64(1))
    R = bits.astype(np.float64).reshape(n, 4, 9)
    lens = R.sum(axis=2)
    F = np.zeros((n, 6, 49))
    for s in range(4):
        others = [o for o in range(4) if o != s]
        F[:, s, TRUMP_RANK] = R[:, s, :]
        F[np.arange(n), s, 9 + lens[:, s].astype(int)] = 1.0
        F[:, s, SIDE] = R[:, others, :].sum(axis=1)
        long_enough = lens[:, s] >= 3
        F[:, s, VOID] = (lens[:, others] == 0).sum(axis=1) * long_enough
        F[:, s, SINGLE] = (lens[:, others] == 1).sum(axis=1) * long_enough
    counts = R.sum(axis=1)
    F[:, 4, OBEN] = counts
    F[:, 4, RUN] = np.cumprod(R, axis=2).sum(axis=(1, 2))
    F[:, 5, UNDEN] = counts
    F[:, 5, RUN] = np.cumprod(R[:, :, ::-1], axis=2).sum(axis=(1, 2))
    return F


def choices(t: np.ndarray, F_fore: np.ndarray, F_part: np.ndarray) -> np.ndarray:
    """The contract played on each deal under weights `t` — forehand calls or shoves."""
    fore = (F_fore @ t[:49] - t[BASELINE]) * MULT
    part = (F_part @ t[:49] - t[BASELINE]) * MULT
    best = fore.argmax(axis=1)
    shove = fore.max(axis=1) < t[SHOVE_T]
    return np.where(shove, part.argmax(axis=1), best)


def clustered_se(x: np.ndarray, groups: np.ndarray) -> tuple[float, float]:
    ids, inv = np.unique(groups, return_inverse=True)
    per = np.bincount(inv, weights=x) / np.bincount(inv)
    return float(per.mean()), float(per.std(ddof=1) / np.sqrt(len(ids)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--iters", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    d = load(args.data)
    values, hands, hidx = d["values"], d["hands"], d["hand_index"]
    rows = np.arange(len(values))
    w0 = json.loads(WEIGHTS_PATH.read_text())
    t0 = theta_from(w0)
    F_fore, F_part = features(hands[:, 0]), features(hands[:, 2])

    # The vectorised selector must be the selector, or everything below tunes something else.
    c0 = choices(t0, F_fore, F_part)
    for i in range(0, len(hands), max(1, len(hands) // 500)):
        a = select_trump(int(hands[i, 0]), True, LABEL_CFG)
        expect = int(select_trump(int(hands[i, 2]), False, LABEL_CFG)) if a == SHOVE else int(a)
        assert c0[i] == expect, (i, c0[i], expect)
    print("vectorised selector agrees with krass_jass.trump.select_trump")

    fit = (hidx % 2) == 0
    held = ~fit

    def score(t, mask):
        return values[rows[mask], choices(t, F_fore[mask], F_part[mask])].mean()

    rng = np.random.default_rng(args.seed)
    scale = np.maximum(np.abs(t0), 1.0) * 0.25
    t, best = t0.copy(), score(t0, fit)
    print(f"start: fitting half {best:.2f}, held-out half {score(t0, held):.2f}")
    for it in range(args.iters):
        cand = t.copy()
        k = 1 if rng.random() < 0.7 else 3
        idx = rng.choice(N_PARAMS, size=k, replace=False)
        cand[idx] += rng.standard_normal(k) * scale[idx] * (1.0 - 0.8 * it / args.iters)
        s = score(cand, fit)
        if s >= best:
            t, best = cand, s
        if it % 1000 == 999:
            print(f"  iter {it + 1}: fitting {best:.2f}, held-out {score(t, held):.2f}", flush=True)

    base = values[rows, c0]
    tuned = values[rows, choices(t, F_fore, F_part)]
    gain, se = clustered_se((tuned - base)[held], hidx[held])
    print(f"\nheld-out gain over the shipped weights: {gain:.2f} ± {se:.2f} per round "
          f"(multiplier x point difference), {held.sum()} deals")
    c1 = choices(t, F_fore, F_part)
    shove0 = ((F_fore @ t0[:49] - t0[BASELINE]) * MULT).max(axis=1) < t0[SHOVE_T]
    shove1 = ((F_fore @ t[:49] - t[BASELINE]) * MULT).max(axis=1) < t[SHOVE_T]
    names = [Contract(c).name.lower() for c in range(6)]
    print("contracts played, shipped: " + ", ".join(f"{n} {np.mean(c0 == i):.1%}" for i, n in enumerate(names))
          + f", forehand shoved {shove0.mean():.1%}")
    print("contracts played, tuned:   " + ", ".join(f"{n} {np.mean(c1 == i):.1%}" for i, n in enumerate(names))
          + f", forehand shoved {shove1.mean():.1%}")

    if args.out:
        note = (f"Tuned by arena/fit_trump.py against {len(values)} simulated deals; held-out gain "
                f"{gain:.2f} +- {se:.2f} per round in multiplied point difference.")
        args.out.write_text(json.dumps(write_theta(w0, t, note), indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
