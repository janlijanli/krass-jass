# dl4g_hslu: "Jass Queen", root-parallel ISMCTS (Joelius300)

- **Source:** github.com/Joelius300/dl4g_hslu @ 9257812 (2024-01-16). It needs Joelius300's fork of
  jass-kit-py @ 806b379 (its `jass_kit` submodule).
- **Licence:** GPL-3.0, and so is the kit. It runs in its own venv (`venvs/dl4g`, Python 3.11,
  numpy 1.25.2 + pandas) behind `arena/opponents/jasskit_bridge.py`. Nothing of it is imported by us.
- **Runnable:** yes. It is all code, with no weights, and its ML trump models are not used by the
  served bot. 4th place in its HSLU tournament (README).
- **Status: not measured.** The session's permission classifier refused to execute the opponent
  code (see `README.md`).

## What it plays

- **Cards:** ISMCTS (`jass_bot/agents/ISMCTS.py`) with root parallelisation
  (`multi_processing_ISMCTS.py`): N worker processes each grow their own tree until a wall-clock
  deadline, and the root visit counts are summed. UCB1 selection, **random-walk rollouts**, and a
  **binary payoff**: 1 for the team with more points in the round, else 0. It plays to win the
  round, not to maximise points; the author found that stronger in its own tournament. Our share of
  points measures something different.
- **Determinization:** a uniform shuffle of the unseen cards (`_sample_state`). **No void
  inference.** A seat that showed out of a suit is still dealt that suit in imagined worlds.
- **Trump:** the "Graf" heuristic: a per-card score table per contract, summed. It pushes from
  forehand if the best score is below 68. The ISMCTS is not used for trump.
- **Budget as deployed:** `docker-compose.yaml` and the report: 9.75 s a move, 15 workers. The report
  tunes C: `1 < sqrt(2) < 5 < 10 < 7 < 8`, so **C = 8** is its strongest documented setting.
- **Rules:** jass-kit's `RuleSchieber`: the strict undertrump rule and the Puur exemption, as ours.
  No Weis. Raw points, so it does not know our 1/1/2/2/3/4 multipliers.

## Running it

The bridge's `dl4g` is `MultiProcessingISMCTS(time_budget, ucb1_c_param=8, num_workers=W,
ignore_same_player_safety=True)`, exactly as `jass_bot/bot_service.py` builds it.

This machine has 4 cores. The tournament budget (15 workers x 9.75 s, ~146 core-seconds a move)
would take ~10 hours of opponent time for 100 deals (~3,600 opponent card decisions). The runner's
default is **C = 8, 3 workers x 2 s** (~1/25 of the tournament's core-seconds). Run one deal at a
time so our search does not take cores from their time-budgeted one:

```sh
python -m arena.opponents.jasskit --bot dl4g --deals 100 --seed 1 --start 1 --workers 1
python -m arena.opponents.jasskit --report .runs/opp-dl4g-1-shipped.jsonl
# the floor: their rule-based agent (Graf trump + highest-winning-or-lowest card)
python -m arena.opponents.jasskit --bot dl4g-rule --deals 400 --seed 1 --start 2 --workers 2
```

If 2 s loses clearly, rerun 40 deals at `--time-budget 9.75` (edit `OPPONENTS["dl4g"]`). That
checks whether budget changes the verdict.

## Expected (from the code, not measured)

It is a strong-ish search held back by uniform determinization (no voids) and a win/lose payoff.
Our bot weights worlds by voids, plays and bid, and plays for points. Expect us to win clearly on
points. The interesting part of the diagnosis is the Graf trump choice against ours: its push
threshold of 68 and its contract mix.

## Numbers

None yet.
