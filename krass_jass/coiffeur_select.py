"""Rule-based Coiffeur choice: which row to fill with this hand, or shove.

The Schieber's selector asks "which contract is this hand best at?". In the Coiffeur every
row has to be played once, so the question is "which row does this hand fill *better than a
later hand would*?" — a row kept open is not worth nothing, it is worth whatever an average
future hand fetches in it. So each choice is valued as

    multiplier[row] x (edge(hand, contract) - reserve[row])

where `edge` is the Schieber's trump score (`krass_jass/trump.py`, its weights unchanged) and
`reserve` is the edge a random hand has in that contract — or, for the Chance, the edge of a
random hand's *best* game, since the Chance can wait for the hand that suits anything.
A large multiplier magnifies both directions: a strong hand belongs in the dear row, a weak
hand must not be spent there.

The extra rows play their tricks in more than one order. A Slalom or Guschti is valued at the
mean edge of the contracts its nine tricks are played in; a 3×3 at its first block's, the only one
known when it is chosen; a Misère at minus the edge — a hand that is bad at Obenabe is good at
Misère Obenabe; a Tutti at its best trump suit's, which the chooser makes the counting suit with
the first card and can lead again whenever it has the lead. A Mitte is played in an order the
trump weights know nothing of, so it has an edge of its own: each card weighted by how far it sits
from the ten (`mitte_edge`), fitted on simulated Mitte rounds. Keeping the row is worth a random
hand's best game in it.

The 3×3's later blocks are named by whoever leads tricks 4 and 7 (`choose_block`): the contract
their remaining cards are best at, whichever team they are on — a defender who takes tricks takes
them from the declarers.

**Fitted.** Each game's value is a line in points on the edge, and a row's reserve is what a
random hand writes there (`arena/fit_coiffeur.py`). Keeping a row is worth more while the column is
still full — more hands are still to come — and the shove threshold rises with it; both were fitted
by simulating whole sheets (`arena/coiffeur_sheet_sim.py`). Results in `docs/coiffeur-plan.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

from .cards import RANK_T, card_list, card_rank
from .coiffeur import ALL_ROWS, CHANCE_ROW, ROW_NAMES, Choice
from .schedule import EXTRA_ROWS
from .rules import SHOVE, Contract, RulesConfig
from .trump import load_weights, score_all

WEIGHTS_PATH = Path(__file__).parent / "data" / "coiffeur_weights.json"


def load_coiffeur_weights(path: str | Path | None = None) -> dict:
    return json.loads(Path(path or WEIGHTS_PATH).read_text())


def game_edge(edge: dict, contract: Contract, schedule=None) -> float:
    """The hand's edge in one game, from its edge per contract: a Slalom or Guschti the mean
    over its tricks, a 3×3 its first block (the only one known), a Misère turned round, a Tutti
    its best trump suit (the chooser leads, and the led suit is trump)."""
    if schedule is not None and schedule.misere:
        return -edge[contract]
    if schedule is not None and schedule.led:
        return max(edge[c] for c in Contract if c.is_trump)
    if schedule is not None:
        named = [c for c in schedule.tricks if c is not None]
        return sum(edge[c] for c in named) / len(named)
    return edge[contract]


#: `mitte_edge` keys, by a card's distance from the ten: the ten, 9/Under, 8/Ober, 7/King, 6/Ace.
MITTE_CLASSES = ("T", "9J", "8Q", "7K", "6A")


def mitte_edge(hand: int, w: dict) -> float:
    """A hand's edge in a Mitte: its cards weighted by how far each sits from the ten."""
    weight = w["mitte_edge"]["value"]
    return sum(weight[MITTE_CLASSES[abs(card_rank(c) - RANK_T)]] for c in card_list(hand))


def _game_name(choice: Choice) -> str:
    return choice.schedule.name if choice.schedule is not None else choice.contract.name


def value_choices(
    hand: int,
    choices: list[Choice],
    multipliers: tuple[int, ...],
    cfg: RulesConfig,
    weights: dict | None = None,
    trump_weights: dict | None = None,
) -> dict[Choice, float]:
    """`multiplier x (own - reserve)` for every open choice.

    With a fitted `value_map` (`arena/fit_coiffeur.py`) both are in points written: the game's
    expected points for this hand, and what the row is expected to fetch from a random hand.
    Without one, both are the selector's edge, as first written.
    """
    w = weights or load_coiffeur_weights()
    # Contract multipliers are ones in the Coiffeur, so this is the bare edge per contract.
    edge = score_all(hand, cfg.variant(multipliers={c: 1 for c in Contract}), trump_weights or load_weights())
    fitted = "value_map" in w
    lift = _option_lift(choices, w)
    out = {}
    for choice in choices:
        if choice.schedule is not None and choice.schedule.mitte:
            e = mitte_edge(hand, w)
        else:
            e = game_edge(edge, choice.contract, choice.schedule)
        if fitted:
            # A 4/5 Guschti is priced as the 5/4 one: only that was simulated.
            a, b = w["value_map"]["value"][_game_name(choice).replace("GUSCHTI4_", "GUSCHTI_")]
            own = a + b * e
            keep = w["points_reserve"]["value"][ROW_NAMES[choice.row]]
            if lift:
                keep += lift * w["option_value"]["value"]["spread"][ROW_NAMES[choice.row]]
        else:
            own = e
            if choice.row == CHANCE_ROW:
                keep = w["joker_reserve"]["value"]
            elif choice.schedule is not None:
                keep = w["extra_reserve"]["value"][EXTRA_ROWS.index(ROW_NAMES[choice.row])]
            else:
                keep = w["reserve"]["value"][int(choice.contract)]
        out[choice] = multipliers[choice.row] * (own - keep)
    return out


def _open_share(choices: list[Choice]) -> float:
    """How full the team's column still is, from its own choices: 0 with one row open, 1 with
    every row. Each open row offers at least one choice, so the legal list is enough."""
    n = len({c.row for c in choices})
    return (n - 1) / (ALL_ROWS - 1)


def _option_lift(choices: list[Choice], w: dict) -> float:
    """What keeping a row open adds to its reserve, in units of the row's spread: a later hand
    may fill it better, and the more rows are still open, the more hands are still to come
    (`arena/coiffeur_sheet_sim.py`). Nothing without a fitted `option_value`."""
    ov = w.get("option_value", {}).get("value")
    if not ov:
        return 0.0
    share = _open_share(choices)
    return ov["a"] * share ** ov["b"] if share > 0 else 0.0


def _shove_threshold(choices: list[Choice], w: dict) -> float:
    ov = w.get("option_value", {}).get("value")
    tau = w["shove_threshold"]["value"]
    return tau + (ov["tau_n"] * _open_share(choices) if ov else 0.0)


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
    if SHOVE in legal and len(choices) > 1 and values[best] < _shove_threshold(choices, w):
        return SHOVE
    return best


def choose_block(
    hand: int, options: list[Contract], cfg: RulesConfig, trump_weights: dict | None = None
) -> Contract:
    """3×3: the block to name — the contract the remaining cards are best at."""
    edge = score_all(hand, cfg.variant(multipliers={c: 1 for c in Contract}), trump_weights or load_weights())
    return max(options, key=lambda c: (edge[c], -int(c)))
