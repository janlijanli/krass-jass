# Opponents: HSLU "Deep Learning for Games" bots, group A

Student bots from the HSLU DL4G module, all built on Thomas Koller's jass-kit. One shared
bridge seats any of them at our engine's table; one runner measures them.

| Opponent | Licence | Runnable? | What it plays | Measured |
|---|---|---|---|---|
| [dl4g_hslu](dl4g_hslu.md) (Joelius300) | GPL-3.0 | yes: code complete, no weights needed | root-parallel ISMCTS, random rollouts, Graf trump heuristic | **not yet**, see below |
| [jass-bot](jass-bot.md) (tramasys) | none | yes once compiled (C++, no weights) | one-ply hand-written heuristic, no search | **not yet** |
| [kurtoid](kurtoid.md) (skiapoden) | none | yes, through a shim for the 2019 jass-kit API | "Bockchain" trump rule, one random sample per card | **not yet** |
| [jassager](jassager.md) (d-sbrgr) | none | yes: code and `.pth` weights in the repo | ISMCTS 9.5 s, void-aware determinization; a CNN-rollout variant | **not yet** |
| [jass-kit examples](jass-kit-examples.md) | GPL-3.0 | yes | random; the kit has no rule-based agent, dl4g's Graf agent stands in | **not yet** |

**Why nothing is measured yet.** In the session that built this (2026-11-11) the auto-mode
permission classifier refused every command that executes the cloned opponent code: installing
the kits from their checkouts, compiling jass-bot, and starting the bridge, even on jass-kit's
own random agent. The bridge, the runner and the venvs (PyPI dependencies only) are ready. The
seat and card mapping is verified against a stub opponent of our own (below). What is left is to
run the commands in each file. That needs a permission rule that lets Bash run
`/home/user/ext/venvs/*/bin/python` and build `/home/user/ext/jass-bot`, or a session where
the owner approves those commands.

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
