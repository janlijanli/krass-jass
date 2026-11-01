"""Fit the Coiffeur row choice to simulated game values — steps 2 and 3 of `docs/coiffeur-plan.md`.

`arena/coiffeur_contracts.py` prices every game a chooser can name, in points written. The row
choice (`krass_jass/coiffeur_select.py`) scores a hand per game with the Schieber's trump weights
— an *edge* in the selector's own units — and until now compared edges directly. This turns each
game's edge into expected points with a per-game line, `points ≈ a + b × edge`, fitted on half the
hands and scored on the other half, and sets each row's reserve to what a random hand is expected
to write in it at its best. A richer per-game ridge fit on the selector's 49 hand features is
reported beside it, so it is visible what the one-number edge leaves on the table.

Usage::

    python -m arena.fit_coiffeur arena/runs/2026-10-31/coiffeur_games.npz --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from arena.fit_trump import features  # noqa: E402
from krass_jass.coiffeur import CHANCE_ROW, EXTRA_SLOTS, ROW_NAMES  # noqa: E402
from krass_jass.coiffeur_select import WEIGHTS_PATH, game_edge, load_coiffeur_weights  # noqa: E402
from krass_jass.deal import deal  # noqa: E402
from krass_jass.rules import COIFFEUR, Contract  # noqa: E402
from krass_jass.schedule import for_row, parse  # noqa: E402
from krass_jass.trump import load_weights, score_all  # noqa: E402

UNIT = COIFFEUR.variant(multipliers={c: 1 for c in Contract})


def edges(hand: int, tw: dict) -> dict:
    return score_all(hand, UNIT, tw)


def game_of(name: str):
    """`(contract, schedule)` for a game's wire name."""
    try:
        return Contract[name], None
    except KeyError:
        s = parse(name)
        return s.count, s


def r2(y: np.ndarray, pred: np.ndarray) -> float:
    return 1.0 - float(np.mean((y - pred) ** 2) / np.var(y))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--write", action="store_true", help="write the fit into coiffeur_weights.json")
    ap.add_argument("--reserve-hands", type=int, default=20000)
    args = ap.parse_args()

    data = np.load(args.path)
    values, games = data["values"], [str(g) for g in data["games"]]
    hands0 = data["hands"][:, 0]
    fit = data["hand_index"] % 2 == 0
    test = ~fit
    tw = load_weights()

    E = np.array([[game_edge(edges(int(h), tw), *game_of(g)) for g in games] for h in hands0])
    F = features(hands0.astype(np.uint64))          # (n, 6, 49)

    value_map = {}
    print(f"{len(values)} deals, fit on {fit.sum()}, held out {test.sum()}")
    print(f"{'game':18s} {'a':>7s} {'b':>6s}  R2 line  R2 ridge(49)")
    for i, g in enumerate(games):
        y = values[:, i]
        x = E[:, i]
        b, a = np.polyfit(x[fit], y[fit], 1)
        line = r2(y[test], a + b * x[test])

        contract, schedule = game_of(g)
        tricks = [contract] if schedule is None else [c for c in schedule.tricks if c is not None]
        X = np.mean([F[:, int(c)] for c in tricks], axis=0)
        X = np.hstack([X, np.ones((len(X), 1))])
        lam = 10.0
        A = X[fit].T @ X[fit] + lam * np.eye(X.shape[1])
        w = np.linalg.solve(A, X[fit].T @ y[fit])
        ridge = r2(y[test], X[test] @ w)
        value_map[g] = [round(float(a), 3), round(float(b), 4)]
        print(f"{g:18s} {a:7.2f} {b:6.3f}  {line:7.3f}  {ridge:7.3f}")

    # Tutti was added after the games were priced (2026-11-01): until it is, it borrows the trump
    # suits' line — it is valued on the hand's best suit, which it makes trump with the first card.
    if "TUTTI" not in value_map:
        suits = [value_map[c.name] for c in Contract if c.is_trump]
        value_map["TUTTI"] = [round(float(np.mean([v[0] for v in suits])), 3),
                              round(float(np.mean([v[1] for v in suits])), 4)]
        print("TUTTI not priced: borrowed the trump suits' mean line", value_map["TUTTI"])

    # Reserves: what a random hand is expected to write in each row at its best — in points now.
    extras = {ROW_NAMES[r]: [s.name for s in for_row(ROW_NAMES[r], COIFFEUR)] for r in EXTRA_SLOTS}
    rows = {
        **{name: [name] for name in ROW_NAMES[:6]},
        # The Chance takes any game (`coiffeur_chance_takes_extra`).
        ROW_NAMES[CHANCE_ROW]: [c.name for c in Contract] + [n for names in extras.values() for n in names],
        **extras,
    }
    best = {row: [] for row in rows}
    for seed in range(args.reserve_hands // 4):
        for h in deal(seed, 0):
            e = edges(h, tw)
            for row, names in rows.items():
                best[row].append(max(
                    value_map[n][0] + value_map[n][1] * game_edge(e, *game_of(n)) for n in names
                ))
    reserve = {row: round(float(np.mean(v)), 2) for row, v in best.items()}
    print("reserves (points):", reserve)

    if args.write:
        w = load_coiffeur_weights()
        w["value_map"] = {
            "_comment": f"Per game, expected points written = a + b x edge, where edge is the "
                        f"selector's (see value_choices). Fitted on half of {args.path.name} "
                        f"({len(values)} deals), 2026-11-01, arena/fit_coiffeur.py.",
            "value": value_map,
        }
        w["points_reserve"] = {
            "_comment": "Per row, in points: what a random hand is expected to write in it at its "
                        "best, under value_map. CHANCE is any game.",
            "value": reserve,
        }
        Path(WEIGHTS_PATH).write_text(json.dumps(w, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {WEIGHTS_PATH}")


if __name__ == "__main__":
    main()
