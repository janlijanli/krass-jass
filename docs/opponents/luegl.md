# luegl/JassAI: PPO bot (Kantonsschule Uetikon am See, 2026)

**Status: runnable, not yet measured.** Running the opponent's code in this cloud session was
refused by the session's permission classifier ("code from external"). The adapter, the server and
the runner are written and the plumbing is tested end to end against a stand-in (below). The match
itself still has to be run, either in a session that allows it or on the owner's machine.

## What it is

- `github.com/luegl/JassAI`, commit of 2026-05-08. **No licence file**, so all rights are reserved:
  we run it locally as an opponent, in its own venv and process, and nothing of it enters this repo.
- Two small actor-critic MLPs trained with PPO: `TrumpNet` (37 → 128 → 128 → 6) and `CardNet`
  (272 → 256 → 256 → 36, masked to their own legal cards). Inference is argmax: one forward pass, no search.
- Trained weights **are shipped**: `checkpoints/rl_checkpoint_{10000..160000}.pt` and `_latest.pt`
  (~676 KB each, PyTorch `state_dict`s, loaded with `weights_only=True`).
- Trained against a rule-based "Standardspielerin" (two bots against two of her). `train.py` imports
  `standardspielerin`, which is not in the repository; only `standardspielerin1.py` (a simpler
  heuristic) is. Their README claims about 60% against her.
- Rules in their engine (`jass_2.py`): Schieber with suit trumps, Obenabe and Undenufe; follow suit
  or trump; the Puur is exempt from following a trump lead; no undertrumping unless you hold only
  trumps; +5 for the last trick, +100 for a match; game to 2500; Weis exist in the engine.
  **No multipliers** (every contract counts ×1) and **no shoving by the bot**: `TrumpNet` has six
  outputs and no "schieben", so it always declares, whether forehand or shoved to.
- Their legality check matches ours in every case I read (follow suit or trump; the Puur keeps a
  trump lead free; strict undertrump). The runner still checks every card against our legal moves.

What to expect against our `EVAL` rules: it never shoves, and it was never trained on our
multipliers (Obenabe/Undenufe ×3, hearts/clubs ×2 in `DEFAULT_MULTIPLIERS`). It also cannot see
them, so it plays every contract as if worth ×1.

## How it is seated

`arena/opponents/servers/luegl_server.py` runs in their venv and talks the bridge's JSON lines
(`arena/opponents/bridge.py`). It builds `act_trump` / `act_card` arguments exactly as their
`train.py` did:

- **Seats.** Their play order is seat+1 and their teams are 0&2 / 1&3, the same as ours, so our seat
  is their seat. `my_team = seat % 2`, `leader_seat` = the leader of the current trick (used for
  their "who is winning the trick" feature).
- **Cards.** D/H/S/C → Schellen/Rosen/Schilten/Eichel; A K Q J T 9 8 7 6 → As König Ober Under
  Banner 9 8 7 6. Contracts 0–3 map to those suits, 4 to Obenabe, 5 to Undenufe.
- **Score features.** Game score 0:0 (each deal is a game's first round). The round's points so
  far are counted with their own `Karte.punkte` / `schlaegt` from the tricks played.
- **Trump.** `muss_wahlen = not forehand`. It never answers "shove".

## How to run it

```bash
# our core (once)
cd rust && pip install maturin && maturin build --release -o /tmp/wheels \
  && pip install --force-reinstall --no-deps /tmp/wheels/*.whl && cd ..
# the opponent, outside the repo
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/luegl/JassAI /home/user/ext/luegl_JassAI
python3 -m venv /home/user/ext/venvs/luegl
/home/user/ext/venvs/luegl/bin/pip install torch   # CPU is enough; PyPI's wheel works, ~5 GB with CUDA libs
# smoke (2 deals = 4 rounds), then the match
python -m arena.opponents.match luegl --deals 2 --workers 2
python -m arena.opponents.match luegl --deals 100 --seed 1        # then --deals 400 if cheap
python -m arena.opponents.match --diagnose .runs/opp-luegl-1-shipped.jsonl
```

`KJ_EXT` moves the `/home/user/ext` root. Each worker process starts one server; calls never
interleave inside a server, so no lock is needed. Errors and illegal cards are logged to
`.runs/opponents/luegl-{errors,illegal}.log` and counted in the result line. The opponent costs
about a millisecond a move, so the cost of the run is our bot: ~1–2 s a move and 36 of our moves a
deal (two seats × 9 tricks × 2 rounds). 100 deals is about 20–30 minutes on 4 cores.

## Numbers

Not yet measured (see Status). The result line goes to `arena/opponents/results.jsonl`.
