"""Fit the Mitte row's value for the Coiffeur row choice (owner, 2026-11-06).

The other games are valued on the Schieber's trump weights (`arena/fit_coiffeur.py`); the Mitte's
card order is none of theirs, so it gets an edge of its own: each card weighted by how far it sits
from the ten — the ten, 9/Under, 8/Ober, 7/King, 6/Ace (`coiffeur_select.mitte_edge`). The weights
are a ridge fit on what the chooser's team wrote in simulated Mitte rounds
(`arena/coiffeur_contracts.py generate --games MITTE`), on half the hands and scored on the other
half. Nine cards a hand, so the five counts sum to 9 and carry the intercept: the edge *is* the
expected points, and the value line is `0 + 1 x edge`.

Then, as `fit_coiffeur.py` does for every row: the reserve — what a random hand is expected to
write in the Mitte row — and the spread of it, which the option value scales (`coiffeur_sheet_sim`);
and the Chance's reserve again, since the Chance may now take a Mitte too.

Usage::

    python -m arena.fit_mitte arena/runs/2026-11-06/mitte_games.npz --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from arena.fit_coiffeur import edges, game_of, r2  # noqa: E402
from krass_jass.cards import RANK_T, card_list, card_rank  # noqa: E402
from krass_jass.coiffeur import CHANCE_ROW, EXTRA_SLOTS, ROW_NAMES  # noqa: E402
from krass_jass.coiffeur_select import MITTE_CLASSES, WEIGHTS_PATH, game_edge, load_coiffeur_weights  # noqa: E402
from krass_jass.deal import deal  # noqa: E402
from krass_jass.rules import COIFFEUR, Contract  # noqa: E402
from krass_jass.schedule import for_row  # noqa: E402
from krass_jass.trump import load_weights  # noqa: E402


def counts(hand: int) -> np.ndarray:
    """How many of the hand's cards sit at each distance from the ten."""
    out = np.zeros(len(MITTE_CLASSES))
    for c in card_list(hand):
        out[abs(card_rank(c) - RANK_T)] += 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--write", action="store_true", help="write the fit into coiffeur_weights.json")
    ap.add_argument("--reserve-hands", type=int, default=20000)
    args = ap.parse_args()

    data = np.load(args.path)
    games = [str(g) for g in data["games"]]
    y = data["values"][:, games.index("MITTE")]
    hands0 = data["hands"][:, 0]
    fit = data["hand_index"] % 2 == 0
    test = ~fit

    X = np.array([counts(int(h)) for h in hands0])
    lam = 1.0
    w = np.linalg.solve(X[fit].T @ X[fit] + lam * np.eye(X.shape[1]), X[fit].T @ y[fit])
    held = r2(y[test], X[test] @ w)
    # For scale: the same hands valued as if the Mitte were their better no-trump game.
    tw = load_weights()
    O, U = Contract.OBENABE, Contract.UNDENUFE
    nt = np.array([max(e[O], e[U]) for e in (edges(int(h), tw) for h in hands0)])
    b, a = np.polyfit(nt[fit], y[fit], 1)
    print(f"{len(y)} deals, fit on {fit.sum()}, held out {test.sum()}; mean {y.mean():.1f}, sd {y.std():.1f}")
    print("weights per card:", dict(zip(MITTE_CLASSES, np.round(w, 2))))
    print(f"held-out R2: Mitte edge {held:.3f}; best of Obenabe/Undenufe edge {r2(y[test], a + b * nt[test]):.3f}")

    weights = load_coiffeur_weights()
    weights["mitte_edge"] = {"value": {k: round(float(v), 3) for k, v in zip(MITTE_CLASSES, w)}}
    value_map = dict(weights["value_map"]["value"])
    value_map["MITTE"] = [0.0, 1.0]

    def value(name: str, hand: int, e: dict) -> float:
        a_, b_ = value_map[name.replace("GUSCHTI4_", "GUSCHTI_")]
        if name == "MITTE":
            return a_ + b_ * float(counts(hand) @ w)
        return a_ + b_ * game_edge(e, *game_of(name))

    # The reserve and the Chance's, on the hands and seeds `fit_coiffeur.py` used.
    extras = {ROW_NAMES[r]: [s.name for s in for_row(ROW_NAMES[r], COIFFEUR)] for r in EXTRA_SLOTS}
    chance = [c.name for c in Contract] + [n for names in extras.values() for n in names]
    mitte, best = [], []
    for seed in range(args.reserve_hands // 4):
        for h in deal(seed, 0):
            e = edges(h, tw)
            mitte.append(value("MITTE", h, e))
            best.append(max(value(n, h, e) for n in chance))
    # The spread on `coiffeur_sheet_sim`'s own hands.
    spread = float(np.std([value("MITTE", h, {}) for s in range(2500) for h in deal(10_000_000 + s, 0)]))
    reserve, chance_reserve = float(np.mean(mitte)), float(np.mean(best))
    share = float(np.mean(np.array(best) == np.array(mitte)))
    print(f"reserve MITTE {reserve:.2f}, spread {spread:.2f}; CHANCE reserve {chance_reserve:.2f} "
          f"(was {weights['points_reserve']['value']['CHANCE']}), Mitte a random hand's best game {share:.1%}")

    if args.write:
        weights["mitte_edge"]["_comment"] = (
            f"Mitte (owner, 2026-11-06): a card's weight by its distance from the ten, in points "
            f"written — the five counts sum to 9, so they carry the intercept and value_map's MITTE "
            f"line is 0 + 1 x edge. Ridge fit on half of {args.path.name} ({len(y)} deals at "
            f"{int(data['iterations'])} iterations), held-out R2 {held:.3f}; arena/fit_mitte.py."
        )
        weights["value_map"]["value"]["MITTE"] = [0.0, 1.0]
        weights["points_reserve"]["value"]["MITTE"] = round(reserve, 2)
        weights["points_reserve"]["value"]["CHANCE"] = round(chance_reserve, 2)
        weights["option_value"]["value"]["spread"]["MITTE"] = round(spread, 2)
        # The untrained path is in edge units; the Mitte's edge is in points, so its reserve is too.
        weights["extra_reserve"]["value"][5] = round(reserve, 2)
        Path(WEIGHTS_PATH).write_text(json.dumps(weights, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {WEIGHTS_PATH}")


if __name__ == "__main__":
    main()
