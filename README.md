# krass-jass

### ▶ [Play it](https://janlijanli.github.io/krass-jass/)

Runs entirely in the browser — the engine compiled to WebAssembly, no server, works offline.

---

Web app to play **Schieber Jass** (Swiss, 4 players, French deck): one human against three
bot services. The substantial goal is training an algorithm that plays the game well.

- **`PLAN.md`** — the full plan, rules research and rationale.
- **`CLAUDE.md`** — standing constraints that apply to every session.
- **`docs/rules-config.md`** — every disputed rule, as a flag with a written-down default.
- **`docs/plan-review.md`** — review of the plan, and why M5 is gated on engine throughput.
- **`docs/measurements.md`** — every measurement, dated, in the order it was taken, with the ones
  that turned out wrong left in and marked.
- **[Engine report](https://janlijanli.github.io/krass-jass/report.html)** — the same, as a page with
  charts: what happens when, a timeline, and every experiment on one axis (`web/static/report.*`).
- **`docs/engine-report.md`** — the statistical summary: protocol, the search, beliefs, trump
  selection, and every number that decides how the bots play.

## Status

**Playable.** Against search bots, in the browser or as a container stack. The rules and the
search exist in Python and Rust; the Rust build also targets WebAssembly, which is what makes
the hosted page work with nothing behind it.

The bots run **Information Set MCTS** — one search tree shared across imagined deals — at
153,600 iterations a move, with the imagined deals weighted by how likely the other seats'
cards and bid were (a learned play model), and trump chosen by weights tuned against simulated
contract values. Measured bot against bot, the trump weights win 58% of games against the
originals and the weighting is worth +1.3 points of a round's share, replicated. See
`docs/engine-report.md`.

```
                      Python          Rust         wasm      speedup vs Python
rollouts/sec          71,000       2,500,000          —              35x
DMCTS iterations/sec  35,000       1,664,000    1,194,000       48x / 34x
ms per move @ 2,400        69           1.44         2.01
```

2,400 iterations is the like-for-like benchmark, not the serve budget. It was once measured as
the point past which search stopped paying; that held for the voting search the bots started
with and not for the shared tree that replaced it, which keeps gaining to 64× (§3b). The bots
serve 153,600.

| | |
|---|---|
| M0 | ✅ Rule variants locked in `docs/rules-config.md` |
| M1 | ✅ Bitboard state, legal moves, trick resolution, scoring, Weis/Stöck, property tests, benchmark harness |
| M2 | ✅ FastAPI + WebSocket + card fan; bots in containers on isolated networks |
| M3 | ✅ Rule-based trump selection, weights tuned by simulation; arena with double rounds and whole games. Tournament persistence outstanding |
| M4 | ✅ ISMCTS: void tracking, determinization, one shared tree; beliefs from play, bid and Weis. The exact endgame solver exists behind a flag and is off (§3e) |
| M5 | ⬜ Distillation — **gated on throughput**, see `docs/plan-review.md` §1 |
| M6 | ⬜ Polish: replay UI, security pass, difficulty levels |
| — | ✅ Serverless build: whole engine in wasm, [live on Pages](https://janlijanli.github.io/krass-jass/) |

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
  trump.py    rule-based bidding; weights in data/trump_weights.json, tuned by arena/fit_trump.py
  bidding.py  what a bid says about the hand behind it
  data/       trump weights, the play model and the belief network — each one file, read by
              Python and compiled into Rust
  rollout.py  the rollout kernel (Python reference implementation)
  native.py   boundary to the Rust search core
rust/
  the full rules again, plus the hot path: legal moves, trick resolution, scoring,
  claim order, Weis, Stöck, voids, trump selection, round state, rollout, and the search:
  ISMCTS, the play model, belief weighting, the belief network (and the voting DMCTS and exact
  endgame solver, kept behind flags). Targets both PyO3 and wasm32. See rust/README.md
tests/
  reference.py  a naive implementation written from the rules text, importing nothing
                from krass_jass — it exists to disagree with the engine
web/
  app.py      FastAPI, WebSocket, bot turn loop with deliberate pacing
  session.py  signed guest-session cookie, stdlib HMAC
  static/     card fan (CSS + vanilla JS), mobile first
              cards.js — card faces generated as SVG, real pip layouts
site/
  the serverless build — whole game in one tab, no network after load. See site/README.md
bot/
  service.py  the bot service — a thin wrapper; the agent stays a library
  models.py   Pydantic wire contract between engine and bots
arena/
  arena.py    double rounds + paired t-test
  games.py    whole games to the target, paired, counted in games won
  ab.py       A/B any two DmctsAgent configurations from the command line; logs results.jsonl
  cheating.py the upper bound: MCTS that sees every hand. Eval only, never served
  oracle.py   the search with a fraction of its imagined deals replaced by the truth
  ladder.py   run the baseline ladder
  contracts.py / fit_trump.py      price every call by simulation, tune the trump weights
  policy_data.py / train_policy.py record self-play, fit the play model
  belief_data.py / train_belief.py record self-play with the true deal, fit the belief network
  belief_quality.py                score beliefs offline as an oracle-equivalent fraction
bench/
  benchmark.py  rounds/sec and rollouts/sec. Runs in CI; the number gates M5
```

## Develop

```bash
uv venv --python 3.12
uv pip install -e '.[dev,web]'
.venv/bin/python -m pytest
.venv/bin/python bench/benchmark.py
.venv/bin/python site/
  the serverless build — whole game in one tab, no network after load. See site/README.md
bot/
  service.py  the bot service — a thin wrapper; the agent stays a library
  models.py   Pydantic wire contract between engine and bots
arena/ladder.py --deals 100

# play it, in process
.venv/bin/python -m uvicorn web.app:app --port 8099

# or the real stack: web + three bot containers on isolated internal networks
echo "KRASS_JASS_SECRET=$(openssl rand -hex 32)" > .env
docker compose up -d --build      # http://localhost:8099

# or with no server at all — the engine compiled to wasm, playable offline
./scripts/build-site.sh
python3 -m http.server 8124 --directory site   # http://127.0.0.1:8124
```

## The three rules that make Jass different

Implementations of other trick-taking games get these wrong. They are not bugs:

1. **You may always trump, even when you can follow suit.** This is why the branching
   factor is high.
2. **Strict undertrumping.** Once someone has trumped a non-trump lead, a lower trump is
   illegal — unless your hand is nothing but trumps.
3. **The Puur is exempt from a trump lead.** If your only trump is the trump Jack, you need
   not play it.

---

## Licence

[MIT](LICENSE). The card faces, the bidding and play conventions the bots speak, and the model
weights in `krass_jass/data/` are our own work and fall under the same licence; no printed card
art is reproduced here.
