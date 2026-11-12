# sobrinth/dl4g-bot — "Jass4Fun": greedy

**Result: our bot takes 74.2% ± 11.6% of the points (n = 100 deals, p < 1e-15).** A floor.

- Source: github.com/sobrinth/dl4g-bot @ `011f0c5` (2020-10-09).
- Licence: **GPL-3.0** (the repository is a fork of jass-kit-py, plus `dominik/`). Run in its own
  venv through `arena/opponents/jasskit_bridge.py`; nothing of it is imported by our code.
- Weights: none needed.

## What it plays (`dominik/jass4fun_agent.py`, `Jass4FunAgent`)

- **Card play:** the legal card with the highest point value under the contract (ties: the
  first). No search, no memory, no partner awareness. The repo's own service only registers a
  random player; this is the one real agent in it.
- **Trump:** the contract with the most card points in hand, shoving when that is under 55. In
  this run it never chose Undenufe and shoved in 62% of its forehand hands.
- Rules: its vendored 2020 jass-kit (needs `numpy < 1.24` for `np.str`).

## How it was run

    # venv: Python 3.11, numpy 1.23.5, scikit-learn 1.2.2, tensorflow-cpu 2.12, jass-kit 2.0.5
    #       ($OPPONENTS_DIR/venvs/old); the repo's own jass/ shadows the pip one.
    python -m arena.opponents.run --opponent sobrinth --deals 100 --seed 1 --workers 3
    python -m arena.opponents.run --diagnose .runs/opp-sobrinth-1-shipped.jsonl

Our bot: `build([], 153_600, EVAL)` (40 x 3,840, as served). `EVAL` rules (no Weis, Stöck or
match bonus; multipliers 1/1/2/2/3/4 stay). Double rounds, same game seed for both halves, paired
test on the per-deal share. 20 minutes on 3 workers.

## Numbers

| | |
|---|---|
| our share | **74.24%** ± 11.55% (std), se 1.16% |
| deals | 100 (200 rounds) |
| p | < 1e-15 |
| illegal cards | 1 (an undertrump our rules forbid; we played our fallback) |
| fallbacks / errors | 0 |
| mapping mismatches | 2, both the same rules difference (below) |

Split (our share of the points in those rounds):

| | rounds | our share |
|---|---:|---:|
| we declare | 100 | 86.5% |
| they declare | 100 | 58.4% |
| they declare a suit | 88 | 53-58% |
| they declare Obenabe | 12 | 68.3% |

Even when it holds the contract we take more than half: its greedy play throws its high cards
into tricks it cannot win.

## Mapping check

Every move the bridge also returns jass-kit's own legal set, the seat it reconstructs as next to
play, and its winner of every finished trick; all three agreed with our engine on every move except
two legal sets. Both are the undertrump: jass-kit (its vendored 2020 copy here, and pip's 2.0.5 in the Mcapozzolo
and RubenNunez runs) allows undertrumping a
trick when the player could follow suit or discard instead; our engine applies the strict rule
(`strict_undertrump`, `docs/rules-config.md`). One of those two moves the bot actually played,
which is the one illegal card above.
