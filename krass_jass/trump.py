"""Rule-based trump selection.

`PLAN.md` §3.1 makes this the highest-value cheap component in the project: trump choice is
worth ~16 points of win rate over choosing at random, and a ranked rule-based selector comes
within ~0.7 points of a learned one. Search-based selection measured *worse*, largely
because it rarely learns to shove.

The scoring is deliberately transparent — weights live in `data/trump_weights.json` so they
can be tuned and reviewed without touching code.

**One thing here is easy to get backwards.** The contract multiplier scales the round's
points for *both* teams, so it multiplies your **edge**, not your score. Undenufe at ×4 with
a mediocre hand is a bad idea, not a good one worth four times as much. Contracts are
therefore compared on `(score - baseline) * multiplier`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .cards import (
    NUM_RANKS,
    RANK_CHARS,
    SUIT_MASK,
    card_rank,
    count,
)
from .rules import SHOVE, Contract, RulesConfig

WEIGHTS_PATH = Path(__file__).parent / "data" / "trump_weights.json"


@lru_cache(maxsize=4)
def load_weights(path: str | None = None) -> dict:
    with open(path or WEIGHTS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _rank_char(card: int) -> str:
    return RANK_CHARS[card_rank(card)]


def _suit_cards(hand: int, suit: int) -> list[int]:
    mask = hand & SUIT_MASK[suit]
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def score_suit_as_trump(hand: int, suit: int, w: dict) -> float:
    """How good this hand is with `suit` as trump."""
    trumps = _suit_cards(hand, suit)
    score = sum(w["trump_rank_weights"][_rank_char(c)] for c in trumps)
    score += w["trump_length_bonus"][str(len(trumps))]

    for other in range(4):
        if other == suit:
            continue
        cards = _suit_cards(hand, other)
        score += sum(w["side_suit_weights"][_rank_char(c)] for c in cards)
        # Short side suits are ruffing chances, but only worth something with trumps
        # to ruff with — a void with two trumps is not the same as a void with six.
        if len(trumps) >= 3:
            if not cards:
                score += w["side_void_bonus"]["void"]
            elif len(cards) == 1:
                score += w["side_void_bonus"]["singleton"]
    return score


def _top_run_bonus(hand: int, w: dict, reverse: bool) -> float:
    """Consecutive top cards in a suit cash immediately in a no-trump contract.

    `reverse` walks from the 6 upward for Undenufe instead of from the ace down.
    """
    per_card = w["no_trump_top_run_bonus"]["per_card"]
    bonus = 0.0
    for suit in range(4):
        ranks = {card_rank(c) for c in _suit_cards(hand, suit)}
        order = range(NUM_RANKS - 1, -1, -1) if reverse else range(NUM_RANKS)
        for r in order:
            if r in ranks:
                bonus += per_card
            else:
                break
    return bonus


def score_obenabe(hand: int, w: dict) -> float:
    score = sum(
        w["obenabe_weights"][_rank_char(c)] for suit in range(4) for c in _suit_cards(hand, suit)
    )
    return score + _top_run_bonus(hand, w, reverse=False)


def score_undenufe(hand: int, w: dict) -> float:
    score = sum(
        w["undenufe_weights"][_rank_char(c)] for suit in range(4) for c in _suit_cards(hand, suit)
    )
    return score + _top_run_bonus(hand, w, reverse=True)


def score_all(hand: int, cfg: RulesConfig, weights: dict | None = None) -> dict[Contract, float]:
    """Edge-times-stakes score for every contract. Higher is better."""
    w = weights or load_weights()
    baseline = w["baseline"]["value"]

    raw = {Contract(s): score_suit_as_trump(hand, s, w) for s in range(4)}
    raw[Contract.OBENABE] = score_obenabe(hand, w)
    raw[Contract.UNDENUFE] = score_undenufe(hand, w)

    return {c: (score - baseline) * cfg.multiplier(c) for c, score in raw.items()}


def select_trump(
    hand: int,
    is_forehand: bool,
    cfg: RulesConfig,
    weights: dict | None = None,
) -> Contract | str:
    """Pick a contract, or `SHOVE`.

    Only forehand may shove, and only to a partner who must then choose — so this never
    returns `SHOVE` when `is_forehand` is false, or the bidding would not terminate.
    """
    w = weights or load_weights()
    scores = score_all(hand, cfg, w)
    best = max(scores, key=lambda c: (scores[c], -int(c)))

    if is_forehand and scores[best] < w["shove_threshold"]["value"]:
        return SHOVE
    return best


def describe(hand: int, cfg: RulesConfig) -> list[tuple[Contract, float]]:
    """Scores best-first, for tracing and for the `/how-it-works` documentation."""
    scores = score_all(hand, cfg)
    return sorted(scores.items(), key=lambda kv: -kv[1])
