# FAIKUE/DL4G — "DeAentlibuecher": threaded DMCTS on the 2018 jass-kit

**Result: our bot takes 71.8% ± 14.0% of the points (n = 100 deals, p < 1e-15).** No illegal
cards, no fallbacks, no mapping mismatches.

- Source: github.com/FAIKUE/DL4G @ `73b59f7` (2019-12-19).
- Licence: **none** (no licence file; the tree is a fork of HSLU's jass-kit 1.0): all rights
  reserved. Run locally as an opponent only.

## What it plays

- **Card play:** `MCTSPlayer` starts 10 Python threads (GIL-bound: in effect one core), each of
  which deals one world and runs UCT on it for **9 s** (`mcts_cythonized`, a Cython build of
  `mcts.py`; only a Windows `.pyd` is checked in; the `.pyx` was compiled in place for this run). Root visit
  counts are summed over threads. Reward is win/loss of the round, not points.
- **The sampler is broken:** `Sampler.sample` computes the mask of unknown cards and throws it
  away (`np.ma.masked_where(...).filled(0)` is not assigned), so each other seat is dealt nine
  cards from the full deck — including the bot's own hand and cards already played. Its worlds are
  not consistent with what it has seen.
- **Trump:** hand-written rules (Jack + 4 trumps, Ace + Nine + 5, ...; Obenabe/Undenufe on > 5
  high/low cards), shoves when no rule fires.
- Rules: jass-kit 1.0 Schieber.

## How it was run

<<<<<<< HEAD
A `PlayerRound`-based twin of `arena/opponents/jasskit_bridge_b.py` (fields `dealer, player, trump,
forehand, declared_trump, hand, tricks, trick_first_player, trick_winner, nr_played_cards, ...`
in `jass/base/player_round.py`), `cython` to build the `.pyx`, Python 3.11 + `numpy<1.24`
(`np.int`). At 9 s a move it is ~5 min of its own time a deal per worker: 100 deals is ~2.5 h on
4 workers.
=======
The bridge's `--api v1` mode builds a jass-kit 1.0 `PlayerRound` (`jass_type="SCHIEBER_1000"`,
the forehand flag as None/False/True) and calls `select_trump` / `play_card`; legal cards come
from `PlayerRound.get_valid_cards()`. `mcts_cythonized.pyx` was compiled in place with
`cython<3` (`python setup.py build_ext --inplace` equivalent), outside our repository.

    # venv: $OPPONENTS_DIR/venvs/old (Python 3.11, numpy 1.23.5 for np.int, cython<3)
    python -m arena.opponents.run --opponent faikue --deals 100 --seed 1 --workers 3

Our bot `build([], 153_600, EVAL)`, `EVAL` rules, double rounds, same seed both halves, paired
test. 150 minutes on 3 workers; it spends 116 s a half, ours 18 s.

## Numbers

| | |
|---|---|
| our share | **71.81%** ± 14.04% (std), se 1.40% |
| deals | 100 |
| p | < 1e-15 |
| fallbacks / illegal cards / mapping mismatches | 0 / 0 / 0 |

| | rounds | our share |
|---|---:|---:|
| we declare | 100 | 82.6% |
| they declare | 100 | 62.7% |

**Its trump rules are the leak.** It calls Obenabe or Undenufe in 70 of 100 contracts (">5
high/low cards" fires easily) and loses them: we take 66% of its Obenabe and 63% of its Undenufe,
against 46-56% of its suit contracts. It shoves in 29% of forehand hands. Behind that, a 9 s
search over worlds that include cards already seen does not hold up: second weakest card play
after greedy sobrinth (we keep 83% in our own contracts).

Worst deal (58, 28.0%): our shoved partner's Undenufe x4, 124:504 — the same hand as against
Rico, Mcapozzolo and Nolonar.
>>>>>>> origin/claude/opponent-dl4g-b
