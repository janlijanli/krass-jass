# DonaldTrumpf (edualc/DonaldTrumpf)

**Result: our shipped bot wins clearly, 66.95% ± 12.48% of the points, n = 400 double rounds,
p < 1e-300.** Measured 2026-11-11; no illegal cards, no bridge errors, no fallbacks.

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

`python -m arena.opponents.donald_trumpf --deals 400 --seed 1`: shipped bot (`build([], 153_600, EVAL)`,
40 × 3,840) against DonaldTrumpf, `EVAL` rules, double rounds on one seed, paired test. 64.5 minutes on
4 cores (~10 s a deal).

| | |
|---|---|
| Our share | **66.95%** ± 12.48% (std over deals), se 0.62% |
| n | 400 deals (800 rounds) |
| p | < 1e-300 (paired, against 50%) |
| Opponent errors / illegal cards / fallbacks | 0 / 0 / 0 |
| Deals we lost (< 50%) | 32 of 400; 16 below 45% |

Smoke round first: 2 deals, no illegal cards in ~70 of its card decisions, which a wrong seat or hand
reconstruction would not survive.

## Where the points came from

From `--report .runs/donald_trumpf-1-eval-shipped.jsonl` (points are per half, after multipliers):

| who chose | contract | n | our pts | their pts | our share |
|---|---|---:|---:|---:|---:|
| we | all | 400 | 322.4 | 82.3 | 79.7% |
| we | Clubs | 48 | 261.8 | 52.2 | 83.4% |
| we | Diamonds | 47 | 116.9 | 40.1 | 74.5% |
| we | Hearts | 62 | 258.4 | 55.6 | 82.3% |
| we | Obenabe | 79 | 401.7 | 69.3 | 85.3% |
| we | Spades | 43 | 120.6 | 36.4 | 76.8% |
| we | Undenufe | 121 | 479.0 | 149.0 | 76.3% |
| it | all | 400 | 163.6 | 154.4 | 51.4% |
| it | Clubs | 84 | 157.1 | 156.9 | 50.0% |
| it | Diamonds | 73 | 78.8 | 78.2 | 50.2% |
| it | Hearts | 81 | 144.8 | 169.2 | 46.1% |
| it | Obenabe | 19 | 302.5 | 168.5 | 64.2% |
| it | Spades | 74 | 80.0 | 77.0 | 51.0% |
| it | Undenufe | 69 | 334.6 | 293.4 | 53.3% |

Shove rate: ours 54.5% as forehand; its 0% (it has no shove path).

Reading it:
- **Nearly all of the margin is in the rounds we declare** (79.7%). Defending its contracts we still
  take 51.4%: it declares, never shoves, and still does not out-score us on its own trump. Its
  contract choice is the weak part; its card play holds its own in suit contracts it chose (50.0%
  / 50.2% / 51.0%, 46.1% in Hearts).
- **Our Undenufe is our weakest contract against it** (76.3%, 121 of our 400 calls, 30%), and
  it is where our worst deals come from: in #301, #93 and #28 (26–30% share) our shoved-to partner
  called Undenufe (×4) and lost it 132–496, 192–436, 196–432. CLAUDE.md already flags that the fitted
  selector calls Obenabe/Undenufe about half the time and should be checked against human play;
  these deals are concrete cases to look at (`deal_spec(1, i, None)`, seed 1).

Nothing here suggests a change to our card play: we win by 17 points of share against a bot
built for the challenge.
