# jass-kit's own example agents (floor)

- **Source:** github.com/thomas-koller/jass-kit-py @ 20c70de (2026-08-17).
- **Licence:** GPL-3.0. It runs in `venvs/kit` behind the bridge and is never imported by us. This
  is the kit CLAUDE.md allows as a test-only oracle at most.
- **What exists:** `AgentRandomSchieber` (random trump, a random legal card) and cheating random
  agents. The current kit has **no rule-based example agent**. As the rule-based floor, the bridge
  offers dl4g_hslu's `RuleBasedAgent` (`--bot dl4g-rule`): Graf trump heuristic, play the
  highest-scoring winning card, else the lowest. See `dl4g_hslu.md`.
- **Status: measured, 2026-11-12.** Random: **75.7% ± 12.5%**; dl4g's rule-based agent: **63.8% ±
  10.6%**; n = 100 each, p < 1e-15.

```sh
python -m arena.opponents.jasskit --bot kit-random --deals 400 --seed 1 --start 2 --workers 4
python -m arena.opponents.jasskit --bot dl4g-rule  --deals 400 --seed 1 --start 2 --workers 4
```

These are floors. A result much below ~80% against random would point at the bridge, not at our bot.

## Numbers

`--deals 100 --start 2 --workers 4`, our shipped bot, `EVAL` rules, double rounds on the same seed:

| | kit random (`kit-random`) | dl4g rule-based (`dl4g-rule`) |
|---|---|---|
| our share of points (multiplied) | **75.65% ± 12.49%**, p < 1e-15 | **63.81% ± 10.57%**, p < 1e-15 |
| our share of raw card points | 74.96% | 61.22% |
| our share when we declare / they declare | 82.5% / 67.2% | 74.5% / 48.4% |
| their declarations under 79 raw | 81 of 100 | 52 of 100 |
| errors, illegal cards | 0, 1 (the jass-kit undertrump bug) | 0, 0 |
| time | 16 min | 15 min |

The floor holds where it should. Against random we take 75.7%, not ~100%: random still takes the
tricks its high cards win, and its contracts make 50 raw points on average. Our own `RandomAgent` rung on this
protocol would be the comparison; it was not re-run here.

**The rule-based floor sits close to the search bots.** Our share is 63.8% against it, 60.5% against
dl4g's ISMCTS with the same Graf trump rule, and 59.7% against jassager. With the trump rule
held fixed, dl4g's ISMCTS buys 3.3 points over that greedy card rule. Most of the gap to us is elsewhere:
trump choice, and reading the other hands.

The illegal card from the random agent is the jass-kit undertrump bug (`dl4g_hslu.md`): Clubs trump,
the trick D10 C8 C9, and it played CQ, under C9, holding Diamonds. The kit checked CQ against C8.

100 deals rather than 400: each margin is over 10 standard errors.
