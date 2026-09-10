# krass-jass

Web app to play **Schieber Jass** (Swiss, 4 players, French deck): one human against three
bot services. The substantial goal is training an algorithm that plays the game well.

- **`PLAN.md`** — the full plan, rules research and rationale.
- **`CLAUDE.md`** — standing constraints that apply to every session.
- **`docs/rules-config.md`** — every disputed rule, as a flag with a written-down default.
- **`docs/plan-review.md`** — review of the plan, and why M5 is gated on engine throughput.

## Status

**M1 (engine + tests) complete, and the Rust search core is in.** No web, no bots yet — that is M2.

```
                      Python          Rust        speedup
rollouts/sec          71,000       2,500,000          35x
DMCTS iterations/sec  35,000       1,482,000          42x   (6,187,000 on 8 cores)
```

| | |
|---|---|
| M0 | ✅ Rule variants locked in `docs/rules-config.md` |
| M1 | ✅ Bitboard state, legal moves, trick resolution, scoring, Weis/Stöck, property tests, benchmark harness |
| M2 | 🔶 FastAPI + WebSocket + DMCTS bots playable; containers outstanding (M2c) |
| M3 | 🔶 Rule-based trump selection + arena done; tournament persistence outstanding |
| M4 | ✅ DMCTS: void tracking, determinization, UCT, exact endgame solver, agents, arena |
| M5 | ⬜ Distillation — **gated on throughput**, see `docs/plan-review.md` §1 |
| M6 | ⬜ Polish: replay UI, security pass, difficulty levels |

## Layout

```
krass_jass/
  cards.py    bitboard primitives — a hand is a 36-bit int, a suit is a 9-bit field
  rules.py    RulesConfig: every rule variant as a flag. HOUSE and EVAL presets
  tables.py   precomputed values, trick strengths, undertrump masks
  legal.py    legal-move generation — the highest-risk function in the codebase
  trick.py    trick winner and points
  scoring.py  round scoring: tricks, last trick, match, multiplier
  weis.py     Weis and Stöck
  state.py    RoundState — the authoritative, validating object layer
  voids.py    exact inference: what the play history proves about other hands
  observation.py  THE information boundary — the security-critical function
  agent.py    random / greedy / dmcts. Observation in, move out, forget
  trump.py    rule-based bidding; weights in data/trump_weights.json
  rollout.py  the rollout kernel (Python reference implementation)
  native.py   boundary to the Rust search core
rust/
  the hot path: legal moves, rollout kernel, DMCTS tree. See rust/README.md
tests/
  reference.py  a naive implementation written from the rules text, importing nothing
                from krass_jass — it exists to disagree with the engine
web/
  app.py      FastAPI, WebSocket, bot turn loop with deliberate pacing
  session.py  signed guest-session cookie, stdlib HMAC
  static/     card fan (CSS + vanilla JS), mobile first
              cards.js — card faces generated as SVG, real pip layouts
arena/
  arena.py    double rounds + paired t-test
  cheating.py the upper bound: MCTS that sees every hand. Eval only, never served
  ladder.py   run the baseline ladder
bench/
  benchmark.py  rounds/sec and rollouts/sec. Runs in CI; the number gates M5
```

## Develop

```bash
uv venv --python 3.12
uv pip install -e '.[dev,web]'
.venv/bin/python -m pytest
.venv/bin/python bench/benchmark.py
.venv/bin/python arena/ladder.py --deals 100

# play it
.venv/bin/python -m uvicorn web.app:app --port 8099
```

## The three rules that make Jass different

Implementations of other trick-taking games get these wrong. They are not bugs:

1. **You may always trump, even when you can follow suit.** This is why the branching
   factor is high.
2. **Strict undertrumping.** Once someone has trumped a non-trump lead, a lower trump is
   illegal — unless your hand is nothing but trumps.
3. **The Puur is exempt from a trump lead.** If your only trump is the trump Jack, you need
   not play it.
