"""The trump selector on other multiplier tables, priced offline from one set of contract values.

`arena/contracts.py` prices all six calls on each deal under `LABEL_CFG` (the `EVAL` multipliers,
match bonus 100). Card play for a fixed contract does not depend on the multiplier — it only scales
the round — so dividing each value by its `EVAL` multiplier gives the raw point difference, and a
match is the only way to reach ±257. From that, any table's values follow: its own multipliers, its
own match bonus, its own set of allowed contracts. One labelling run prices the selector on `EVAL`,
on a flat table (every contract ×1, jass-mu-zero) and on the suits-only tables (JassFormer's chibre,
♠×2; PIMC's suits ×1) without playing another card.

    python -m arena.trump_tables .runs/labels-*.npz

For each table it reports the shipped selector, the table-scaled shove threshold
(`krass_jass.trump.table_scale`), the best single threshold for that table (an upper bound on any
threshold-only fix, chosen on half the hands and scored on the other half), and the calls behind
each: shove rate, Obenabe/Undenufe by who called them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from arena.contracts import LABEL_CFG  # noqa: E402
from arena.fit_trump import BASELINE, SHOVE_T, clustered_se, features, theta_from  # noqa: E402
from krass_jass.rules import EVAL, SHOVE, Contract  # noqa: E402
from krass_jass.trump import WEIGHTS_PATH, select_trump, table_scale  # noqa: E402

LABEL_MULT = np.array([LABEL_CFG.multiplier(Contract(c)) for c in range(6)], dtype=np.float64)
ALL = np.ones(6, dtype=bool)
SUITS = np.array([True] * 4 + [False] * 2)

#: name -> (multipliers, allowed contracts, match bonus). The match bonus is 0 because every
#: opponent run was on `EVAL` or a variant of it.
TABLES = {
    "eval": (LABEL_MULT, ALL, 0),
    "flat": (np.ones(6), ALL, 0),
    "chibre": (np.array([1, 1, 2, 1, 1, 1], dtype=np.float64), SUITS, 0),
    "suits x1": (np.ones(6), SUITS, 0),
}


def load_many(paths: list[Path]) -> dict:
    """Several labelling runs as one: hand indices offset so they stay distinct clusters."""
    hidx, hands, values, offset = [], [], [], 0
    for p in paths:
        d = np.load(p)
        hidx.append(d["hand_index"] + offset)
        hands.append(d["hands"])
        values.append(d["values"])
        offset = int(hidx[-1].max()) + 1
    return {"hand_index": np.concatenate(hidx), "hands": np.concatenate(hands),
            "values": np.concatenate(values)}


def raw_values(values: np.ndarray, match_bonus: int) -> np.ndarray:
    """Per contract, (declaring team − other team) in card points, ×1, with `match_bonus`."""
    raw = values / LABEL_MULT
    match = np.isclose(np.abs(raw), 157 + LABEL_CFG.match_bonus)
    return np.where(match, np.sign(raw) * (157 + match_bonus), raw)


def choices(theta, F_fore, F_part, mult, allowed, threshold):
    """Contract played and whether forehand shoved, the selector vectorised for one table."""
    def scores(F):
        s = (F @ theta[:49] - theta[BASELINE]) * mult
        return np.where(allowed, s, -np.inf)

    fore, part = scores(F_fore), scores(F_part)
    shove = fore.max(axis=1) < threshold
    return np.where(shove, part.argmax(axis=1), fore.argmax(axis=1)), shove


def describe(played, shove, V, hidx, label):
    n = len(played)
    v, se = clustered_se(V[np.arange(n), played], hidx)
    nt = played >= 4
    fh = ~shove
    mix = " ".join(f"{Contract(c).name[:3].lower()} {np.mean(played == c):.0%}" for c in range(6))
    print(f"    {label:<30} {v:7.2f} ± {se:4.2f}   shove {shove.mean():5.1%}   "
          f"Obe/Une: forehand {nt[fh].mean() if fh.any() else 0:5.1%}, partner "
          f"{nt[shove].mean() if shove.any() else 0:5.1%}   [{mix}]")
    return V[np.arange(n), played]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data", type=Path, nargs="+")
    ap.add_argument("--weights", type=Path, default=WEIGHTS_PATH)
    args = ap.parse_args()

    d = load_many(args.data)
    values, hands, hidx = d["values"], d["hands"], d["hand_index"]
    w = json.loads(args.weights.read_text())
    t = theta_from(w)
    F_fore, F_part = features(hands[:, 0]), features(hands[:, 2])

    # The vectorised selector must be the selector, on a table other than the one it was fitted to.
    flat_cfg = EVAL.variant(multipliers={c: 1 for c in Contract})
    for scaled in (False, True):
        thr = t[SHOVE_T] * (table_scale(flat_cfg, w) if scaled else 1.0)
        c, _ = choices(t, F_fore[:400], F_part[:400], np.ones(6), ALL, thr)
        for i in range(0, 400, 7):
            a = select_trump(int(hands[i, 0]), True, flat_cfg, w, scale=scaled)
            e = int(select_trump(int(hands[i, 2]), False, flat_cfg, w, scale=scaled)) if a == SHOVE else int(a)
            assert c[i] == e, (i, c[i], e, scaled)

    fit = hidx % 2 == 0
    print(f"{len(values)} deals, {len(np.unique(hidx))} hands. Value per round = multiplier x "
          f"(declaring team - other), the forehand team's view; ± clustered by hand.\n")
    for name, (mult, allowed, bonus) in TABLES.items():
        V = raw_values(values, bonus) * mult
        cfg = EVAL.variant(multipliers={Contract(c): int(mult[c]) for c in range(6)})
        scale = table_scale(cfg, w)
        print(f"  {name}  (multipliers {mult.astype(int).tolist()}, "
              f"{'all six' if allowed.all() else 'suits only'}; table scale {scale:.3f})")
        base_c, base_s = choices(t, F_fore, F_part, mult, allowed, t[SHOVE_T])
        base = describe(base_c, base_s, V, hidx, "shipped (threshold 3.022)")
        sc_c, sc_s = choices(t, F_fore, F_part, mult, allowed, t[SHOVE_T] * scale)
        sc = describe(sc_c, sc_s, V, hidx, f"table-scaled ({t[SHOVE_T] * scale:.3f})")
        g, se = clustered_se(sc - base, hidx)
        print(f"      scaled - shipped: {g:+.2f} ± {se:.2f}")
        # The best one threshold for this table: chosen on the fitting half, scored held out.
        grid = np.linspace(-15, 15, 301)
        rows = np.arange(len(values))
        fit_v = [V[rows[fit], choices(t, F_fore[fit], F_part[fit], mult, allowed, x)[0]].mean() for x in grid]
        best = grid[int(np.argmax(fit_v))]
        bc, bs = choices(t, F_fore, F_part, mult, allowed, best)
        bv = V[rows, bc]
        g, se = clustered_se((bv - base)[~fit], hidx[~fit])
        g2, se2 = clustered_se((bv - sc)[~fit], hidx[~fit])
        describe(bc, bs, V, hidx, f"best threshold ({best:.2f})")
        print(f"      best - shipped, held out: {g:+.2f} ± {se:.2f};  best - scaled: {g2:+.2f} ± {se2:.2f}")
        # The shoved-to partner's no-trump calls: what they made against the partner's best suit.
        part_scores = np.where(SUITS, (F_part @ t[:49] - t[BASELINE]) * mult, -np.inf)
        best_suit = part_scores.argmax(axis=1)
        for label, played, shoved in (("shipped", base_c, base_s), ("scaled", sc_c, sc_s)):
            m = shoved & (played >= 4)
            if m.sum() > 50:
                diff, dse = clustered_se(V[rows[m], played[m]] - V[rows[m], best_suit[m]], hidx[m])
                print(f"      {label}: partner's Obe/Une (n={m.sum()}) vs its best suit on the same "
                      f"deals: {diff:+.2f} ± {dse:.2f}")
        print()


if __name__ == "__main__":
    main()
