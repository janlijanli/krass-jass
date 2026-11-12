# kurtoid (skiapoden): "Trumpruler", modelled on an Entlebuch grand master

- **Source:** github.com/skiapoden/kurtoid @ d366278 (2019-12-18). Authors Pascal Kiser and Patrick
  Bucher (HSLU).
- **Licence:** **none**: all rights reserved. It runs locally as an opponent only.
- **Runnable:** yes, through a shim. It has no weights. It was written against the **2019 jass-kit
  API** (`jass.base.player_round.PlayerRound`, `jass.player.player.Player`, `select_trump` /
  `play_card`). That kit was on a private HSLU GitLab (`gitlab.enterpriselab.ch`), and its Dockerfile
  needs GitLab credentials. `jasskit_bridge.py --bot kurtoid` maps the few names Trumpruler
  touches onto the current kit: `hand`, `tricks`, `current_trick`, `trick_first_player`,
  `nr_tricks`, `trump`, `player`, `forehand` (None until declared), `rule`, `get_valid_cards()`.
  Venv: `venvs/kit` (numpy only) plus the jass-kit-py checkout.
- **Status: measured, 2026-11-12.** Our bot wins clearly: **65.6% ± 12.1%, n = 100, p < 1e-15**.
  The shim held: 0 errors, 0 illegal cards.

## What it plays

The man page (`doc/kurtoid.txt`) names **Trumpruler** (`app/trumpruloid.py`) as the strongest. It
played the tournaments as "Kurtoid", so it is the one wired up.

- **Trump:** the "Bockchain". For each of the six contracts it adds the number of cards in the trump
  suit and the length of the unbroken run of top cards (for a suit trump: J, 9, A, K, Q, 10, ...; for
  Obe and Une: from the top or the bottom, summed over suits). It pushes from forehand below 5.
- **Cards:** for each legal card, **one** random completion of the current trick from the unseen
  cards (voids ignored), scored by that trick's points for or against. It takes the best. That is a
  single noisy sample, close to greedy with noise. The man page says permutations and minimax did
  not help them.

Expect it to be near our GreedyAgent rung, so a very large win for us. It is a floor, not a test.

## Running it

```sh
python -m arena.opponents.jasskit --bot kurtoid --deals 400 --seed 1 --start 2 --workers 4
python -m arena.opponents.jasskit --report .runs/opp-kurtoid-1-shipped.jsonl
```

## Numbers

`--deals 100 --start 2 --workers 4`, our shipped bot (40 x 3,840), `EVAL` rules, double rounds on the
same seed:

| | |
|---|---|
| our share of points (multiplied) | **65.61% ± 12.14%**, n = 100, paired p < 1e-15 |
| our share of raw card points | 62.52% |
| our share when we declare / they declare | 77.2% / 48.6% |
| their declarations under 79 raw | 43 of 100 |
| their shoves from forehand | 65 of 100 (ours: 61) |
| opponent errors / fallbacks, illegal cards | 0, 0 |
| time | 15 min |

**Diagnosis.** A floor, as expected: a single random completion per card is close to greedy. Its
Bockchain trump rule is not bad: it shoves about as often as we do, and its Spades/Hearts/Obenabe calls
make 80-92 raw. Its Clubs and Diamonds fail most (13 of 19, 15 of 26). Defending, it lets us take 117
raw, so the card play is where it loses. Our worst deal is again a shoved Undenufe at x4 (deal 58, the
same hand as in `jass-bot.md`).
