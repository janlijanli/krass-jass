"""Rule-based Coiffeur choice: which row to fill with this hand, or shove.

The Schieber's selector asks "which contract is this hand best at?". In the Coiffeur every
row has to be played once, so the question is "which row does this hand fill *better than a
later hand would*?" — a row kept open is not worth nothing, it is worth whatever an average
future hand fetches in it. So each choice is valued as

    multiplier[row] x (edge(hand, contract) - reserve[row])

where `edge` is the Schieber's trump score (`krass_jass/trump.py`, its weights unchanged) and
`reserve` is the edge a random hand has in that contract — or, for a Joker, the edge of a
random hand's *best* contract, since a Joker can wait for the hand that suits anything.
A large multiplier magnifies both directions: a strong hand belongs in the dear row, a weak
hand must not be spent there.

**Untrained.** The reserves are measured averages and the shove threshold is a guess
(`krass_jass/data/coiffeur_weights.json`). What a row is worth to keep also shrinks as the
sheet fills — with two rows left there is little left to wait for — and that is not modelled.
Fitting both is the training run in `docs/coiffeur-plan.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

from .coiffeur import JOKER_ROWS, Choice
from .rules import SHOVE, Contract, RulesConfig
from .trump import load_weights, score_all

WEIGHTS_PATH = Path(__file__).parent / "data" / "coiffeur_weights.json"


def load_coiffeur_weights(path: str | Path | None = None) -> dict:
    return json.loads(Path(path or WEIGHTS_PATH).read_text())


def value_choices(
    hand: int,
    choices: list[Choice],
    multipliers: tuple[int, ...],
    cfg: RulesConfig,
    weights: dict | None = None,
    trump_weights: dict | None = None,
) -> dict[Choice, float]:
    """`multiplier x (edge - reserve)` for every open choice."""
    w = weights or load_coiffeur_weights()
    # Contract multipliers are ones in the Coiffeur, so this is the bare edge per contract.
    edge = score_all(hand, cfg.variant(multipliers={c: 1 for c in Contract}), trump_weights or load_weights())
    reserve = w["reserve"]["value"]
    joker = w["joker_reserve"]["value"]
    out = {}
    for choice in choices:
        keep = joker if choice.row in JOKER_ROWS else reserve[int(choice.contract)]
        out[choice] = multipliers[choice.row] * (edge[choice.contract] - keep)
    return out


def choose(
    hand: int,
    legal: list,
    multipliers: tuple[int, ...],
    cfg: RulesConfig,
    weights: dict | None = None,
) -> Choice | str:
    """The best choice, or `SHOVE` when it is allowed and nothing is worth the row."""
    w = weights or load_coiffeur_weights()
    choices = [c for c in legal if c != SHOVE]
    values = value_choices(hand, choices, multipliers, cfg, w)
    # Ties go to the lower row, then the lower contract: deterministic, as everything is.
    best = max(choices, key=lambda c: (values[c], -c.row, -int(c.contract)))
    if SHOVE in legal and len(choices) > 1 and values[best] < w["shove_threshold"]["value"]:
        return SHOVE
    return best
