# AlessioVerardo/jass-reinforcement-learning: PIMC

**Status: adapted, single-call smoke passed, match not yet run.** One trump call and one card call
went through the server correctly (2026-11-11: forehand with ♦A K Q J declares diamonds; over a
led ♦9 it plays the Puur). The match itself (`match.py` spawning the server from worker processes)
was refused by this session's permission classifier ("code from external"), so there are no numbers.

## What it is

- `github.com/AlessioVerardo/jass-reinforcement-learning` (2026). **MIT** (`pyproject.toml`; there
  is no LICENSE file). It runs in its own venv and process and nothing of it enters this repo.
- The repo's learned agents (DQN+PER, Rainbow, PPO, AlphaZero-PIMC) ship **no checkpoints**. Its
  **PIMC** needs none: K = 20 sampled worlds, each searched by plain UCB1 MCTS (50 simulations,
  c = 1.41, uniform-random rollouts), Q averaged over worlds, argmax. Each world is a perfect-information
  search, so this is the strategy-fusion design our §3e/§5h measurements moved away from. Their
  README puts it level with their PPO (50.0%, 100 games) and at 61% against their rule-based bot.
- Trump: every legal option is scored by the same search (4K worlds for a shove; the shoved partner
  is modelled by their power heuristic). It **can shove**.
- World sampling honours voids only. Their void flags are not sound under the Puur exemption: a
  seat holding only the Puur that discards on a trump lead is marked void in trump.
- **Rules: suit trumps only. Their engine has no Obenabe and no Undenufe.** Follow suit or trump,
  the Puur exemption, a strict undertrump rule, +5 for the last trick, +100 for a match, no multipliers.

## The table it is measured on

Its search cannot model Obenabe/Undenufe, so `EVAL` is not a fair table: either we would forbid it
contracts we may choose, or it would have to play rounds it cannot search. The measurement uses
`--cfg suits`: `EVAL` (no Weis, Stöck or match bonus) with **every contract ×1**, and **our bidding
restricted to suits** (`SuitsOnly` in `match.py`). Our bot names its best suit by our trump weights and
shoves from forehand under the usual threshold. Only the table changes; our card play is the shipped
bot's (153,600 iterations). If an Obenabe/Undenufe round reaches the server anyway, it answers with an
error, and the bridge logs it and plays our lowest legal card.

## How it is seated

`arena/opponents/servers/verardo_pimc_server.py`, in its own venv (torch + numpy; it reuses the
luegl venv here):

- **Seats.** Their play order is seat+1 and their teams are P0&P2, so the seat numbers are the same.
- **Cards.** Their index is `color * 9 + height`, with heights in our rank order. Our suits D H S C
  map to their DIAMOND HEART SPADE CLUB = 3 1 0 2.
- **State.** For every request their `JassEngine` is rebuilt by replaying the public tricks through
  their own `play_card` / `resolve_trick`, so their void flags and scores arise exactly as in their
  own games. Unseen cards start as filler; their `sample_world` redeals them in every world.
  The server asserts that it reaches the right seat and hand.
- **Not loaded.** Their `jass/agents/__init__.py` (it imports their DQN with pydantic and torchrl);
  only `pimc.py`, `engine.py`, `constant.py` and `trump_heuristic.py` are.
- **Workers.** Their worker pool is replaced by an in-process `map`, because the match already runs
  one server per core. `random` is seeded from each request, so reruns repeat.

## How to run it

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/AlessioVerardo/jass-reinforcement-learning \
  /home/user/ext/AlessioVerardo_jass-reinforcement-learning
/home/user/ext/venvs/luegl/bin/pip install torch numpy        # or any venv; see luegl.md
python -m arena.opponents.match verardo-pimc --cfg suits --deals 2 --workers 2          # smoke
python -m arena.opponents.match verardo-pimc --cfg suits --deals 100 --seed 1
python -m arena.opponents.match --diagnose .runs/opp-verardo-pimc-1-shipped.jsonl
```

Cost: their search is pure Python, about 1,000 simulations per card and up to 8,000 per trump call
(K × 4 suits + 4K for a shove). That is likely seconds per move, so about as slow as our bot. Time
the smoke run before choosing 100 or 400 deals.

## Numbers

Not yet measured. The result line goes to `arena/opponents/results.jsonl`.
