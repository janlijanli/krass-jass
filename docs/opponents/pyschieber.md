# pyschieber ChallengePlayer (Murthy10/pyschieber)

**Result: our shipped bot wins clearly, 62.39% ± 11.35% of the points, n = 400 double rounds,
p < 1e-300.** Measured 2026-11-12; no illegal cards, no bridge errors, no fallbacks. It is the
stronger of the two challenge-era rule bots measured so far (DonaldTrumpf: 66.95%).

## What it is

`pyschieber` (Samuel Kurath et al., MIT) is a Python Schieber engine with built-in players: random,
greedy, and `ChallengePlayer`, a rule-based bot (`player/challenge_player/`, ~1,100 lines):

- **Trump** (`JassStrategy.chose_trumpf`): scores Obenabe, Undenufe and each suit with a per-mode
  evaluator and takes the best; **shoves** as forehand when nothing scores above 54. It shoved 54.2%
  of the time as forehand here, the same rate as ours (54.5%).
- **Card play**: a strategy per mode (`trumpf_color_mode`, `top_down_mode`, `bottom_up_mode`) and per
  role (declarer, partner, defender), on top of a card counter (`card_counter.py`) that tracks played
  cards, the current Bock (highest remaining card) per suit, and flags such as "partner cannot beat
  this" and "failed to follow suit". It falls back to a random legal card when no rule applies; seeded
  from our decision seed, so runs replay. Over 85 decisions with a choice, 96% gave the same card under
  another seed, so the rules, not the fallback, make its decisions.
- `GreedyPlayer` (highest card, trump first) is runnable with `--player GreedyPlayer`; a floor rung,
  not measured.

## How it is run

Its own interpreter (`python -I`, in its own network namespace with no network) running
`arena/opponents/bridges/pyschieber_bridge.py`. For every decision the bridge builds a fresh
player and replays what `pyschieber/game.py` calls, in its order: `id`, nine `set_card`s, then for each
card played so far its own `choose_card` generator on its turns (its first-trick role is set there),
the card leaving its hand, and `move_made(player_id, card, state)` with the state before that card
reached the table. Nothing of pyschieber is imported into our process.

    git clone --depth 1 https://github.com/Murthy10/pyschieber /home/user/ext/Murthy10_pyschieber
    python -m arena.opponents.pyschieber --deals 400 --seed 1
    python -m arena.opponents.pyschieber --report .runs/pyschieber-1-eval-shipped.jsonl

Seats: pyschieber numbers players 0..3 in play order, partner id + 2, as we do, so seat s is id s.
Suits D/H/S/C map to ROSE/BELL/ACORN/SHIELD (suits are symmetric). Smoke round (2 deals) first: no
illegal cards in ~100 of its card decisions.

## Numbers

Shipped bot (`build([], 153_600, EVAL)`, 40 × 3,840), `EVAL` rules, double rounds on one seed, paired
test. 57.2 minutes on 4 cores.

| | |
|---|---|
| Our share | **62.39%** ± 11.35% (std over deals), se 0.57% |
| n | 400 deals (800 rounds) |
| p | < 1e-300 (paired, against 50%) |
| Opponent errors / illegal cards / fallbacks | 0 / 0 / 0 |
| Deals we lost (< 50%) | 41 of 400; 22 below 45% |

| who chose | contract | n | our pts | their pts | our share |
|---|---|---:|---:|---:|---:|
| we | all | 400 | 304.8 | 99.9 | 75.3% |
| we | Clubs | 48 | 257.7 | 56.3 | 82.1% |
| we | Diamonds | 47 | 117.0 | 40.0 | 74.5% |
| we | Hearts | 62 | 254.3 | 59.7 | 81.0% |
| we | Obenabe | 79 | 337.0 | 134.0 | 71.5% |
| we | Spades | 43 | 126.0 | 31.0 | 80.3% |
| we | Undenufe | 121 | 464.8 | 163.2 | 74.0% |
| it | all | 400 | 114.8 | 150.9 | 43.2% |
| it | Clubs | 85 | 140.3 | 173.7 | 44.7% |
| it | Diamonds | 98 | 71.2 | 85.8 | 45.4% |
| it | Hearts | 97 | 132.5 | 181.5 | 42.2% |
| it | Obenabe | 16 | 188.4 | 282.6 | 40.0% |
| it | Spades | 83 | 64.9 | 92.1 | 41.3% |
| it | Undenufe | 21 | 274.5 | 353.5 | 43.7% |

## Reading it

- **It wins its own contracts** (we take 43.2% defending), unlike DonaldTrumpf (51.4%). It shoves
  as often as we do and calls a suit 91% of the time; its contracts are sound. The margin is again in
  the rounds we declare (75.3%).
- **Our no-trump contracts are where we are weakest**: Obenabe 71.5% and Undenufe 74.0% against
  80–82% in Clubs, Hearts and Spades. They are half of our calls (200 of 400); it calls them 9% of the
  time. Against DonaldTrumpf our Obenabe was our best contract (85.3%), so this is a stronger defence,
  not only our choice.
- **The worst deals are our no-trump calls lost at ×3/×4**: #256 (Undenufe, 172–456), #399
  (Obenabe 165–306, and its shoved Undenufe 160–468 against us), #96 (Undenufe, 184–444), #179
  (Obenabe after a shove, 150–321). The same pattern as against DonaldTrumpf. Two opponents now point
  at the selector's Obenabe/Undenufe rate (50% of our calls here) as the first thing to check, ahead
  of card play: it was fitted against our own bot's play, and these bots defend no-trump better than
  that fit assumed. Deals are `deal_spec(1, i, None)`.
