# FAIKUE/DL4G — "DeAentlibuecher": threaded DMCTS on the 2018 jass-kit

**Status: triaged, not run.** Needs a second bridge (it is written against jass-kit 1.0's
`PlayerRound` API, not 2.x's `GameObservation`), and running new opponent code was refused by this
session's permission classifier before that was attempted.

- Source: github.com/FAIKUE/DL4G @ `73b59f7` (2019-12-19).
- Licence: **none** (no licence file; the tree is a fork of HSLU's jass-kit 1.0): all rights
  reserved. Run locally as an opponent only.

## What it plays

- **Card play:** `MCTSPlayer` starts 10 Python threads (GIL-bound: in effect one core), each of
  which deals one world and runs UCT on it for **9 s** (`mcts_cythonized`, a Cython build of
  `mcts.py`; only a Windows `.pyd` is checked in, the `.pyx` would have to be compiled). Root visit
  counts are summed over threads. Reward is win/loss of the round, not points.
- **The sampler is broken:** `Sampler.sample` computes the mask of unknown cards and throws it
  away (`np.ma.masked_where(...).filled(0)` is not assigned), so each other seat is dealt nine
  cards from the full deck — including the bot's own hand and cards already played. Its worlds are
  not consistent with what it has seen.
- **Trump:** hand-written rules (Jack + 4 trumps, Ace + Nine + 5, ...; Obenabe/Undenufe on > 5
  high/low cards), shoves when no rule fires.
- Rules: jass-kit 1.0 Schieber.

## How to run it (not done here)

A `PlayerRound`-based twin of `arena/opponents/jasskit_bridge.py` (fields `dealer, player, trump,
forehand, declared_trump, hand, tricks, trick_first_player, trick_winner, nr_played_cards, ...`
in `jass/base/player_round.py`), `cython` to build the `.pyx`, Python 3.11 + `numpy<1.24`
(`np.int`). At 9 s a move it is ~5 min of its own time a deal per worker: 100 deals is ~2.5 h on
4 workers.
