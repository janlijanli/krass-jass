# DonaldTrumpf (edualc/DonaldTrumpf)

**Status: adapter written and our side tested; not yet measured** — executing the cloned bot was
refused by the session's auto-mode classifier (see `README.md`). Everything below the "Numbers" line
is to be filled in by the run.

## What it is

4th place in the Zühlke Jass Challenge 2017 (repository edualc/DonaldTrumpf); MIT. A hand-written
rule-based bot for the webplatformz/challenge server, JavaScript (Node 6 era, Babel build), ~1,400
lines of decision code in `client/logic/brain.js` and `client/logic/ChanceCalc.js`. No randomness in
its decisions.

- **Trump choice** (`chooseTrumpf`): for each of the six contracts, weights its own cards by
  contract-specific tables (`TrumpfWeights`, `ObeabeWeights`, ...) and subtracts the expected weight
  of a partner's hand from a uniform card-probability table; takes the best. **It never shoves**: the
  code has no path that returns `SCHIEBE`, so as forehand it always declares and the shove flag it
  records is overwritten by the next broadcast.
- **Card play** (`chooseCard`): per mode (TRUMPF / OBEABE / UNDEUFE) and per seat in the trick: is the
  trick already ours (partner's card beats the others), play the Buur/Nell, draw trumps while the
  opponents still hold some, smear points onto a partner's trick, discard low otherwise. Legal
  moves from its copy of the challenge validators (follow suit, undertrump rule, Buur exemption).
- **Card counting** (`ChanceCalc`): per-player void tracking and card probabilities, used inside
  some of the rules.
- Rules variant: the challenge's Schieber, with no Weis and no Stöck in its decisions, so our `EVAL`
  table (Weis, Stöck and match bonus off) is the closest fit. Its trump choice ignores the contract
  multipliers.

## How it is run

Its own Node process, `arena/opponents/bridges/challenge_brain.js`, sandboxed (`unshare -n`, no
network; `node --permission` with read access to the bridge, its checkout and lodash only). For each
decision Python sends the full list of challenge messages that seat would have received
(`DEAL_CARDS`, `BROADCAST_TRUMPF`, `PLAYED_CARDS` after every card, `BROADCAST_STICH` with the winner's
team name after every trick, then `REQUEST_TRUMPF` or `REQUEST_CARD`); the bridge reloads the bot's
modules and dispatches them exactly as its `client/bot.js` does (that file imports ES-module protocol
code that only runs after a Babel build, and its switch is transcribed instead). Stateless per
decision, so no lock is needed and every worker gets its own process.

    git clone --depth 1 https://github.com/edualc/DonaldTrumpf /home/user/ext/edualc_DonaldTrumpf
    mkdir -p /home/user/ext/_deps && (cd /home/user/ext/_deps && npm init -y && npm install --ignore-scripts lodash@4.17.21)
    python -m arena.opponents.donald_trumpf --deals 100 --seed 1        # smoke: then check .runs/donald_trumpf-events.jsonl
    python -m arena.opponents.donald_trumpf --deals 400 --seed 1        # resumes
    python -m arena.opponents.donald_trumpf --report .runs/donald_trumpf-1-eval-shipped.jsonl

Seats: the protocol names no seats, so the only mapping is play order (partner = two cards back in
the trick) and the team name in `BROADCAST_STICH`, which must be `"DonaldTrumpf 3000"` for its own
team because its card counter tests for that literal name. Illegal or missing cards are logged to
`.runs/donald_trumpf-events.jsonl` and replaced by our lowest legal card; a failed trump call falls
back to our rule-based selector and is logged as `trump_error`.

Checked without the bot (`tests/test_opponents_common.py`): card and contract conversions round-trip,
every replayed history holds the nine dealt cards, 4 `PLAYED_CARDS` per finished trick plus one per
card on the table, one `BROADCAST_STICH` per finished trick and ends in `REQUEST_CARD` with the table;
the logged double round gives the same share as `arena.arena.double_round` deal for deal.

## Numbers

Not measured. Expected on reading the code: a clear win for us. It never shoves, it calls trump from
fixed weights, and its play is a decision list — the rung our `rule-based` agent already stands on.
Run it and check that; if we do *not* clear 52%, `--report` breaks the result down by who chose,
contract, and shove rate.
