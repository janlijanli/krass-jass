# Opponents: HSLU "Deep Learning for Games" bots, group A

Student bots from the HSLU DL4G module, all built on Thomas Koller's jass-kit. One shared
bridge seats any of them at our engine's table; one runner measures them.

Our shipped bot (`build([], 153_600, EVAL)`) against each, measured 2026-11-12: `EVAL` rules,
double rounds on the same seed, paired t-test. Share is of multiplied points, ± the std over deals.

| Opponent | Licence | What it plays | Our share | n | Errors / illegal |
|---|---|---|---|---|---|
| [jassager](jassager.md) FullMCTS (d-sbrgr), 2 s a move | none | ISMCTS, void-aware worlds, points reward; trump by the same search | **59.7% ± 11.0%** | 100 | 0 / 0 |
| [dl4g_hslu](dl4g_hslu.md) (Joelius300), 3 workers x 2 s | GPL-3.0 | root-parallel ISMCTS, uniform worlds, win/lose reward; Graf trump rule | **60.5% ± 12.5%** | 100 | 0 / 1 |
| dl4g rule-based ([floor](jass-kit-examples.md)) | GPL-3.0 | Graf trump rule, greedy card rule | **63.8% ± 10.6%** | 100 | 0 / 0 |
| [jass-bot](jass-bot.md) (tramasys) | none | one-ply hand-written heuristic, no search | **65.5% ± 12.0%** | 200 | 0 / 0 |
| [kurtoid](kurtoid.md) (skiapoden) | none | "Bockchain" trump rule, one random sample per card | **65.6% ± 12.1%** | 100 | 0 / 0 |
| [jassager](jassager.md) CNN rollout | none | the same tree, a CNN leaf value | **67.5% ± 12.2%** | 100 | 0 / 1 |
| [jass-kit random](jass-kit-examples.md) | GPL-3.0 | random | **75.7% ± 12.5%** | 100 | 0 / 1 |

Every p < 1e-15. Our share is never at or below 52%, so no opponent needed the full diagnosis the
brief asks for at that level; each file still says where its bot loses.

**What they have in common.**

- **Trump choice is where every one of them loses most.** A third to a half of their contracts make
  under 79 raw points; ours fail 4-15%. jassager chooses by search and shoves once in 100 forehand
  rounds, which reproduces "MCTS-based trump selection rarely learns to shove". jass-bot almost never
  calls Obenabe/Undenufe.
- **Our Obenabe/Undenufe, mostly when shoved to, are in our worst deals against every opponent**
  (deal 58, a shoved Undenufe on DA DK DQ H10 H9 H8 S7 S6 C8, is in our worst five in five of the seven runs). They
  still pay on average, but thin calls (three aces and no length) are worth a look by whoever owns
  trump selection. The fitted selector calls them in half our rounds.
- **The illegal cards (3 in ~29,000 opponent cards) are all one jass-kit bug.** `RuleSchieber` uses
  the lower of two trumps in the trick as the undertrump bar, compared by card index. Our engine
  refuses the card and plays our lowest legal card instead. See `dl4g_hslu.md`.

The opponents' budgets are scaled to this 4-core machine (2 s a move, not their 9.5-9.75 s). Each file
says what was not run.

## How it fits together

- `arena/opponents/jasskit_bridge.py`: runs in the opponent's own venv, never in ours. It
  loads one jass-kit agent (`--bot`) and answers jass-kit's REST format (V0.2, the JSON the HSLU
  jass server sends): `POST /action_trump`, `POST /action_play_card`. It is single-threaded, so
  a time-budgeted search never shares its cores with another of its own requests. jass-bot (C++)
  serves the same format itself.
- `arena/opponents/jasskit.py`: the `Agent` subclass and the runner, after `arena/jass_the_ripper.py`.
  `--start N` launches N servers of the bot and assigns each call to a free one under a file lock.
  Every returned card is checked against our legal moves: an illegal one is logged and our lowest
  legal played instead; an error or timeout is logged and a seeded random legal card played.
  Per-deal JSON lines record both halves' contract, declarer, shove and points, raw and
  multiplied, and the cards. A rerun resumes. `--report` prints the diagnosis.
- Nothing under `krass_jass/` imports either file, and neither imports the other. jass-kit and the
  bots stay in `/home/user/ext/`, outside the repository.

**Seats.** jass-kit's `next_player = [3, 0, 1, 2]` (the player after j is j-1), so our seat s is
their -s mod 4. Partners stay partners, and their dealer is the seat after forehand in their
numbering. Cards (suit*9 + rank, A K Q J 10 9 8 7 6, suits D H S C) and trumps (0-3, 4 Obenabe, 5
Undenufe, 10 push) are encoded the same as ours. Completed tricks carry `win` and `points` from our
engine, because jassager's search reads `obs.trick_points`.

**Self-check.** `python -m arena.opponents.jasskit --bot stub --deals 2 --start 1` seats a stand-in
of our own that rebuilds every trick leader from the dealer and the cards, as jass-bot's parser
does, and asserts it against `first`, `win` and `currentPlayer`. Result: 2 deals (8 rounds), 0
errors, 0 illegal cards.

## Setup (done once, in /home/user/ext)

```sh
for r in Joelius300/dl4g_hslu tramasys/jass-bot skiapoden/kurtoid d-sbrgr/jassager thomas-koller/jass-kit-py; do
  GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/$r /home/user/ext/${r#*/}
done
# dl4g's jass_kit submodule points at Joelius300's fork of the kit:
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/Joelius300/jass-kit-py /home/user/ext/joelius-jass-kit
cd /home/user/ext/venvs
uv venv -p 3.12 kit      && VIRTUAL_ENV=kit uv pip install numpy
uv venv -p 3.11 dl4g     && VIRTUAL_ENV=dl4g uv pip install "numpy~=1.25.2" pandas
uv venv -p 3.12 jassager && VIRTUAL_ENV=jassager uv pip install jass-kit==2.0.5 torch==2.5.1 \
                              pandas==2.2.3 scikit-learn==1.5.2
```

The kits are not pip-installed from their checkouts. The bridge puts the checkouts on
`sys.path`, so no `setup.py` of theirs runs. jassager pins jass-kit 2.0.5, which is on PyPI.

## Measurement protocol (each file has its command)

Our shipped bot (`build([], 153_600, EVAL)`, 40 x 3,840), `EVAL` rules (no Weis, Stöck or match
bonus), double rounds on the same game seed, paired t-test, 100 deals first, 400 if cheap. The
share counts the contract multipliers (1/1/2/2/3/4), as every arena number does. None of these
bots knows about multipliers: jass-kit scores raw points. So `--report` also prints the raw
card-point share.
