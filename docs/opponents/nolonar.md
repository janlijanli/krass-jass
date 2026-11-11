# Nolonar/HSLU_JassBot — "CasualTea": casualT (flat MC, 9 s) and specialT (play network)

**Status: set up, not run.** Two adapter entries are in `arena/opponents/registry.py`
(`nolonar-casualT`, `nolonar-specialT`, the `tf` venv), but running new opponent code was refused
by this session's permission classifier.

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

## How to run it

    python -m arena.opponents.run --opponent nolonar-specialT --deals 400 --seed 1 --workers 4
    python -m arena.opponents.run --opponent nolonar-casualT --deals 100 --seed 1 --workers 4

casualT: ~36 moves a deal x 9 s, ~5 min of its time a deal per worker, ~2 h for 100 deals.
