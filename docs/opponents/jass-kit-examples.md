# jass-kit's own example agents (floor)

- **Source:** github.com/thomas-koller/jass-kit-py @ 20c70de (2026-08-17).
- **Licence:** GPL-3.0. It runs in `venvs/kit` behind the bridge and is never imported by us. This
  is the kit CLAUDE.md allows as a test-only oracle at most.
- **What exists:** `AgentRandomSchieber` (random trump, a random legal card) and cheating random
  agents. The current kit has **no rule-based example agent**. As the rule-based floor, the bridge
  offers dl4g_hslu's `RuleBasedAgent` (`--bot dl4g-rule`): Graf trump heuristic, play the
  highest-scoring winning card, else the lowest. See `dl4g_hslu.md`.
- **Status: not measured.** The session's permission classifier refused to execute the kit code.

```sh
python -m arena.opponents.jasskit --bot kit-random --deals 400 --seed 1 --start 2 --workers 4
python -m arena.opponents.jasskit --bot dl4g-rule  --deals 400 --seed 1 --start 2 --workers 4
```

These are floors. A result much below ~80% against random would point at the bridge, not at our bot.

## Numbers

None yet.
