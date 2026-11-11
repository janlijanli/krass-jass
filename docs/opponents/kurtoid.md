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
- **Status: not measured.** The session's permission classifier refused to execute the opponent
  code (see `README.md`).

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

None yet.
