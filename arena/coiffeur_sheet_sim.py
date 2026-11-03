"""Train the Coiffeur row choice on whole sheets — steps 3 and 4 of `docs/coiffeur-plan.md`.

The selector values a choice as `multiplier x (expected points - keep)`. Until now `keep` was a
constant per row: what a random hand writes in that row at its best. That is the value of a row
with *no choice left*. A row kept open while other hands are still to come is worth more — the
team may get a better hand for it — and that option shrinks as the sheet fills. This fits it:

    keep(row, n) = reserve[row] + a x ((n - 1) / 11) ** b x spread[row]

where `n` is the team's own open rows (the bot reads it off its legal choices), `spread` the
spread of a random hand's best value in the row, and `a`, `b` fitted. The shove threshold `tau`
(in multiplier x points, the selector's units) is fitted with it, sloped by `tau_n` in `n`.
`a = 0, tau = 0` is the shipped selector exactly.

**No search.** Whole games are simulated at the choosing level: every round deals four hands
from the game seed, each hand is valued per game by the fitted lines (`value_map`), and what a
choice actually writes is that value plus a residual drawn from the overnight prices
(`arena/coiffeur_contracts.py`) — the deal's luck, the right size and shape, matches included,
scored by the rules of 2026-11-03 (a match is 157 in the row and a stroke of 10). The choosing
itself is the engine's (`Sheet`, `Choosing`): who is on turn, shoving round the table, the partner
phase. Candidates are compared on paired games — the same seed twice, the sides swapped, every
residual drawn the same — and fitted by the cross-entropy method on the mean score difference.

Usage::

    python -m arena.coiffeur_sheet_sim arena/runs/2026-11-01/coiffeur_games.npz --out arena/runs/<date>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from arena.fit_coiffeur import game_of  # noqa: E402
from krass_jass.coiffeur import ROW_NAMES, Choosing, Sheet, multipliers  # noqa: E402
from krass_jass.coiffeur_select import game_edge, load_coiffeur_weights  # noqa: E402
from krass_jass.deal import deal  # noqa: E402
from krass_jass.rules import COIFFEUR, SHOVE, Contract  # noqa: E402
from krass_jass.scoring import team_of  # noqa: E402
from krass_jass.trick import NUM_SEATS  # noqa: E402
from krass_jass.trump import load_weights, score_all  # noqa: E402

CFG = COIFFEUR
UNIT = CFG.variant(multipliers={c: 1 for c in Contract})
STROKE = CFG.coiffeur_match_stroke or 0
#: The shipped selector.
BASE = {"a": 0.0, "b": 1.0, "tau": 0.0, "tau_n": 0.0}

_M: "Model | None" = None


class Model:
    """The fitted lines, the residuals behind them, and each row's reserve and spread."""

    def __init__(self, path: Path, weights: dict) -> None:
        data = np.load(path)
        self.games = [str(g) for g in data["games"]]
        self.index = {g: i for i, g in enumerate(self.games)}
        self.parsed = [game_of(g) for g in self.games]
        self.misere = np.array([s is not None and s.misere for _, s in self.parsed])
        vm = weights["value_map"]["value"]
        self.a = np.array([vm[g][0] for g in self.games])
        self.b = np.array([vm[g][1] for g in self.games])
        self.tw = load_weights()
        values = data["values"]
        est = np.array([self.estimate(int(h)) for h in data["hands"][:, 0]])
        # A deal's luck: what it wrote, less what its hand was expected to write. A match is
        # kept as a match, not as a residual: it is an outcome of its own under the stroke rule.
        self.matched = values >= 257
        self.residual = np.where(self.matched, 0.0, values - est)
        self.reserve = dict(weights["points_reserve"]["value"])
        self._cache: dict[int, np.ndarray] = {}
        self.spread = self._spread()

    def estimate(self, hand: int) -> np.ndarray:
        edge = score_all(hand, UNIT, self.tw)
        e = np.array([game_edge(edge, c, s) for c, s in self.parsed])
        return self.a + self.b * e

    def est(self, hand: int) -> np.ndarray:
        v = self._cache.get(hand)
        if v is None:
            if len(self._cache) > 200_000:
                self._cache.clear()
            v = self._cache[hand] = self.estimate(hand)
        return v

    def _spread(self) -> dict[str, float]:
        """The spread of a random hand's best value in each row: how much a better hand can add."""
        rows = rows_games(self)
        best = {r: [] for r in rows}
        for seed in range(2500):
            for h in deal(10_000_000 + seed, 0):
                v = self.est(h)
                for r, idx in rows.items():
                    best[r].append(v[idx].max())
        return {r: float(np.std(v)) for r, v in best.items()}


def rows_games(m: Model) -> dict[str, list[int]]:
    """Each row's games, by index into `m.games`. The Chance takes any game."""
    out: dict[str, list[int]] = {}
    for name in ROW_NAMES:
        if name == "CHANCE":
            out[name] = list(range(len(m.games)))
        elif name in Contract.__members__:
            out[name] = [m.index[name]]
        else:
            out[name] = [i for i, g in enumerate(m.games) if g == name or g.startswith(name + "_")]
    return out


def _init(path: str, weights: dict) -> None:
    global _M
    _M = Model(Path(path), weights)


def choose(m: Model, theta: dict, hand: int, legal: list, mults: tuple) -> object:
    """The selector, with a reserve that shrinks as the sheet fills and a fitted shove."""
    choices = [c for c in legal if c != SHOVE]
    n = len({c.row for c in choices})
    v = m.est(hand)
    lift = theta["a"] * ((n - 1) / 11) ** theta["b"] if n > 1 else 0.0
    best, best_val = None, -1e18
    for c in choices:
        name = c.schedule.name if c.schedule is not None else c.contract.name
        row = ROW_NAMES[c.row]
        keep = m.reserve[row] + lift * m.spread[row]
        val = mults[c.row] * (v[m.index[name]] - keep)
        if val > best_val:
            best, best_val = c, val
    if SHOVE in legal and len(choices) > 1:
        if best_val < theta["tau"] + theta["tau_n"] * (n - 1) / 11:
            return SHOVE
    return best


def play(m: Model, thetas: tuple[dict, dict], seed: int) -> tuple[list[int], int, int]:
    """One game, `thetas[t]` choosing for team t. Returns the totals, shoves and choices."""
    rng = np.random.default_rng(seed)
    sheet = Sheet.for_game(CFG)
    mults = multipliers(seed, CFG)
    scores = [0, 0]
    dealer = int(rng.integers(NUM_SEATS))
    shoves = choices = 0
    rnd = 0
    while not sheet.complete:
        hands = deal(seed, rnd)
        # The deal's luck per seat, fixed before anyone chooses: common to both sides of a pair.
        luck = rng.integers(len(m.residual), size=NUM_SEATS)
        choosing = Choosing(forehand=(dealer + 1) % NUM_SEATS, sheet=sheet, cfg=CFG)
        while True:
            seat = choosing.chooser
            action = choose(m, thetas[team_of(seat)], hands[seat], choosing.legal(), mults)
            if action == SHOVE:
                choosing.act(seat, SHOVE)
                shoves += 1
                continue
            break
        choices += 1
        c = action
        team = team_of(seat)
        g = m.index[c.schedule.name if c.schedule is not None else c.contract.name]
        j = luck[seat]
        if m.matched[j, g]:
            # Misère: the opponents took every trick — 0, and the stroke is theirs. Otherwise the
            # choosing team's match: 157 in the row and the stroke.
            if m.misere[g]:
                row_tens, stroke_team = 0, 1 - team
            else:
                row_tens, stroke_team = 16, team
        else:
            pts = float(np.clip(m.est(hands[seat])[g] + m.residual[j, g], 0, 157))
            row_tens, stroke_team = (int(pts) + 5) // 10, None
        sheet.written[team][c.row] = row_tens
        scores[team] += row_tens * mults[c.row]
        if stroke_team is not None:
            sheet.strokes[stroke_team] += 1
            scores[stroke_team] += STROKE
        dealer = (dealer + 1) % NUM_SEATS
        rnd += 1
    return scores, shoves, choices


def _pairs(args) -> list[tuple[float, float, int, int]]:
    theta, base, seeds = args
    out = []
    for s in seeds:
        a0, s0, c0 = play(_M, (theta, base), s)
        b1, s1, c1 = play(_M, (base, theta), s)
        diff = (a0[0] - a0[1]) + (b1[1] - b1[0])
        wins = (a0[0] > a0[1]) + (b1[1] > b1[0]) + 0.5 * ((a0[0] == a0[1]) + (b1[0] == b1[1]))
        out.append((diff, wins / 2, s0 + s1, c0 + c1))
    return out


def evaluate(pool, theta: dict, base: dict, seeds: list[int], workers: int) -> dict:
    chunks = [seeds[i::workers] for i in range(workers)]
    rows = [r for part in pool.map(_pairs, [(theta, base, c) for c in chunks]) for r in part]
    d = np.array([r[0] for r in rows])
    return {
        "diff": float(d.mean()),
        "se": float(d.std(ddof=1) / np.sqrt(len(d))),
        "win": float(np.mean([r[1] for r in rows])),
        "shove_rate": float(sum(r[2] for r in rows) / max(1, sum(r[2] + r[3] for r in rows))),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path, help="the overnight prices (arena/coiffeur_contracts.py)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--generations", type=int, default=12)
    ap.add_argument("--population", type=int, default=24)
    ap.add_argument("--pairs", type=int, default=1500, help="paired games per candidate")
    ap.add_argument("--final-pairs", type=int, default=20000)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    log = (args.out / "sheet_sim.jsonl").open("a")

    weights = load_coiffeur_weights()
    keys = ["a", "b", "tau", "tau_n"]
    mu = np.array([0.5, 1.0, 0.0, 0.0])
    sd = np.array([1.0, 0.5, 40.0, 40.0])
    lo = np.array([-1.0, 0.2, -300.0, -300.0])
    hi = np.array([4.0, 4.0, 300.0, 300.0])
    rng = np.random.default_rng(args.seed)
    t0 = time.time()
    with ProcessPoolExecutor(args.workers, initializer=_init, initargs=(str(args.path), weights)) as pool:
        base_vs_base = evaluate(pool, BASE, BASE, list(range(1000, 1000 + 400)), args.workers)
        print(f"base vs base (should be 0): {base_vs_base}", flush=True)
        for gen in range(args.generations):
            # Fresh seeds every generation, shared by every candidate in it.
            seeds = list(range(10**6 * (gen + 1), 10**6 * (gen + 1) + args.pairs))
            pop = np.clip(mu + sd * rng.standard_normal((args.population, len(keys))), lo, hi)
            scored = []
            for x in pop:
                theta = dict(zip(keys, map(float, x)))
                r = evaluate(pool, theta, BASE, seeds, args.workers)
                scored.append((r["diff"], x, r))
            scored.sort(key=lambda s: -s[0])
            elite = np.array([s[1] for s in scored[: max(2, args.population // 4)]])
            mu, sd = elite.mean(axis=0), np.maximum(elite.std(axis=0), [0.05, 0.05, 2.0, 2.0])
            top = scored[0][2]
            rec = {"gen": gen, "mu": dict(zip(keys, map(float, mu))), "sd": dict(zip(keys, map(float, sd))),
                   "best": dict(zip(keys, map(float, scored[0][1]))), "best_result": top,
                   "elapsed_s": round(time.time() - t0)}
            log.write(json.dumps(rec) + "\n")
            log.flush()
            print(f"gen {gen}: mu {np.round(mu, 3)}  best {top['diff']:+.1f} ± {top['se']:.1f}, "
                  f"win {top['win']:.3f}, shove {top['shove_rate']:.3f}  [{time.time() - t0:.0f}s]", flush=True)

        theta = dict(zip(keys, map(float, mu)))
        final = evaluate(pool, theta, BASE, list(range(9 * 10**7, 9 * 10**7 + args.final_pairs)), args.workers)
        base = evaluate(pool, BASE, BASE, list(range(9 * 10**7, 9 * 10**7 + 200)), args.workers)
    result = {"theta": theta, "final": final, "base_shove_rate": base["shove_rate"],
              "spread": _spread_of(args.path, weights), "pairs": args.final_pairs}
    (args.out / "sheet_sim_result.json").write_text(json.dumps(result, indent=2))
    print("final:", json.dumps(result["final"]), "theta:", theta, flush=True)


def _spread_of(path: Path, weights: dict) -> dict:
    return {k: round(v, 2) for k, v in Model(path, weights).spread.items()}


if __name__ == "__main__":
    main()
