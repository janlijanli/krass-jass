# dl4g_hslu: "Jass Queen", root-parallel ISMCTS (Joelius300)

- **Source:** github.com/Joelius300/dl4g_hslu @ 9257812 (2024-01-16). It needs Joelius300's fork of
  jass-kit-py @ 806b379 (its `jass_kit` submodule).
- **Licence:** GPL-3.0, and so is the kit. It runs in its own venv (`venvs/dl4g`, Python 3.11,
  numpy 1.25.2 + pandas) behind `arena/opponents/jasskit_bridge.py`. Nothing of it is imported by us.
- **Runnable:** yes. It is all code, with no weights, and its ML trump models are not used by the
  served bot. 4th place in its HSLU tournament (README).
- **Status: measured, 2026-11-12.** Our bot wins clearly: **60.5% ± 12.5%, n = 100, p < 1e-15**
  at C = 8, 3 workers x 2 s a move.

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

`python -m arena.opponents.jasskit --bot dl4g --deals 100 --seed 1 --start 1 --workers 2`. Our shipped
bot (40 x 3,840) against C = 8, 3 workers x 2 s, on `EVAL` rules, double rounds on the same seed:

| | |
|---|---|
| our share of points (multiplied, as every arena number) | **60.47% ± 12.50%** (std over deals), n = 100, paired p < 1e-15 |
| our share of raw card points (what they play for) | 57.86% |
| opponent errors / fallbacks | 0 of ~3,600 calls |
| illegal cards | 1, a jass-kit rule bug (below) |
| time | ~2 h (100 deals, 1.2 min a deal) |

**Diagnosis.** It loses on both sides of the table, more so when it declares:

| declaring side | rounds | our share of the round | declarer's raw points | declarer under 79 |
|---|---|---|---|---|
| we declare | 100 | 72.6% | 110.6 | 15% |
| they declare | 100 | 42.7% | 86.7 | 34% |

- **Trump choice is its weakest part.** The Graf heuristic shoves from forehand in **82%** of rounds
  (we shove in 61%). When it does declare, it falls short of half the points a third of the time.
  Its Undenufe calls fail 7 of 11 times (mean 70.6 raw points). Its Obenabe calls fail 6 of 14.
  Its suit contracts average 88-95 raw points; ours average 106-113.
- **Our Obenabe/Undenufe.** We declare them in half our rounds (21 Obe + 29 Une of 100). That is the
  2026-10 fitted selector CLAUDE.md asks to check against human play. Against this opponent they fail
  (declarer under 79) more often than our suit calls: 20% against ~10%. They still average the same raw
  points (111.7 against 109.5) and the same share of the round (73%), so at x3/x4 they pay. Three of
  our five worst deals turn on one of them:
  - deal 58 (19.7%): shoved to, we called Undenufe holding DA DK DQ H10 H9 H8 S7 S6 C8 and made 31.
  - deal 68 (37.3%): forehand Obenabe on DA D8 D7 HK H7 SK S10 CA C8, two aces and no long suit. Made 64.
  - deal 90 (38.5%): forehand Obenabe on DA D6 H7 SA SK S8 CA C8 C6, three aces and nothing behind them.
    Made 62.
  These are worth a look by whoever owns trump selection: three aces with no length is a thin Obenabe.
- **The card play is not where it loses most.** Defending our contracts it concedes 72.6% of the round;
  declaring its own it keeps 57.3%, but a third of those contracts it should not have called. Uniform determinization (no voids) and a win/lose payoff cost it points, but less
  than its bidding does.

**The illegal card is a jass-kit bug, in both kits.** `RuleSchieber.get_valid_cards` keeps the *lower*
of two trumps already in the trick as the undertrump bar, and compares them by card index, not trump
rank. With H10 and HJ (the Puur) on the table under Hearts, it lets a player under-trump the Puur with
H9. dl4g did this once (`.runs/opp-dl4g-illegal.log`). Our engine refused the card and played our
lowest legal card for it. Every jass-kit bot shares this rule, so expect rare cases of it elsewhere.

Not run: the tournament budget (15 workers x 9.75 s, ~10 h for 100 deals here). The margin is 8 standard
errors, so a 25x budget is unlikely to turn it around, but it would narrow it.
