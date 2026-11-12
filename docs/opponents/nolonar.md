# Nolonar/HSLU_JassBot — "CasualTea": casualT (flat MC, 9 s) and specialT (play network)

**casualT: our bot takes 59.7% ± 11.3% of the points (n = 100 deals, p < 1e-15).** No illegal
cards, no fallbacks; two mapping mismatches, both the undertrump rules difference.
**specialT: our bot takes 59.1% ± 10.5% (n = 100, p < 1e-15)**; one undertrump, logged and
replaced by our fallback card.

- Source: github.com/Nolonar/HSLU_JassBot @ `6415b43` (2021-11-18).
- Licence: **none**: all rights reserved. Run locally as an opponent only.
- Weights present: `CasualTea/trained_model/play_deep_neural_network.h5`,
  `trump_deep_neural_network.h5`, `trump_logistic_regression.pkl`, `trump_gradient_boosting.pkl`
  (pickles from a 2021 scikit-learn; may need an old one to load).

## What it plays

- **casualT** (their default): flat UCB1 over the root's legal cards for **9 s** a move, c = sqrt 2
  on raw points (0-157), so after one visit each it is pure exploitation. The rollout is
  **not legal play**: the other seats play cards popped off one shuffled pool of the unseen cards,
  ignoring follow-suit and even whose hand a card is in; only the bot's own seat plays legally.
- **specialT**: a dense network over hand, legal cards, used cards, current trick, led suit,
  trump, trick position — argmax over legal cards. Cheap.
- **Trump** (both): logistic regression on the hand.
- Rules: jass-kit Schieber.

## How it was run

    # venv: $OPPONENTS_DIR/venvs/tf (Python 3.11, tensorflow-cpu 2.15 / Keras 2, numpy 1.26, jass-kit 2.0.5)
    python -m arena.opponents.run --opponent nolonar-casualT --deals 100 --seed 1 --workers 3
    python -m arena.opponents.run --opponent nolonar-specialT --deals 100 --seed 1 --workers 3

Our bot `build([], 153_600, EVAL)`, `EVAL` rules, double rounds, same seed both halves, paired
test. The pickled logistic regression loads in scikit-learn 1.x.

## casualT

152 minutes on 3 workers; it spends 117 s a half, ours 18 s.

| | |
|---|---|
| our share | **59.68%** ± 11.34% (std), se 1.13% |
| deals | 100 |
| p | < 1e-15 |
| fallbacks / illegal cards | 0 / 0 |
| mapping mismatches | 2 — jass-kit allows an undertrump our strict rule forbids |

| | rounds | our share |
|---|---:|---:|
| we declare | 100 | 73.8% |
| they declare | 100 | **42.1%** |
| they declare, shoved | 63 | 44.3% |
| they declare, own choice | 37 | 38.0% |

**The strongest trump choice of the group.** It is the only measured opponent that wins its own
contracts clearly: we take 42% of them, against 47-57% for every other bot. It shoves in 63% of
forehand hands, close to our 61%, and calls Obenabe/Undenufe in 42 of 100 contracts. We lose its
Hearts (37%) and Undenufe (37%) hardest; deal 93, its shoved Undenufe x4, is a match against us
(0:628). Its card play is still the weak side: the rollouts are not legal play.

Why we still win by ~10 points: our contracts (74%), where its card play has to defend.

Worst deal (58, 23.6%): our shoved partner calls Undenufe x4 and loses 124:504. This is the same
hand as our worst deal against Rico and Mcapozzolo (`dl4g-group-b.md`).

## specialT

21 minutes on 3 workers; it spends 1.1 s a half.

| | |
|---|---|
| our share | **59.12%** ± 10.46% (std), se 1.05% |
| deals | 100 |
| p | < 1e-15 |
| fallbacks | 0 |
| illegal cards | 1 — an undertrump (Spades trump, it played the 8 under the King while able to discard); our fallback played |
| mapping mismatches | 1 — the same move |

| | rounds | our share |
|---|---:|---:|
| we declare | 100 | 74.1% |
| they declare | 100 | 41.9% |

**The play network is as strong as the 9 s search** (59.1% against 59.7%, and the trump calls are
identical: same model, same deals). It makes the same point twice: what keeps Nolonar ahead of
the rest of the group is its trump choice, not its card play. Our contracts come out the same
against both (74%).
