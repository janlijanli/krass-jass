"""Agents. Observation in, move out, forget.

Per `CLAUDE.md`: the agent is a **library**, and the FastAPI bot service will be a thin
wrapper over `decide`. Self-play and the arena import this and run it across a process
pool; they do not go through HTTP. Three containers exist to serve one game to a human, not
millions to a trainer.

The baseline ladder from `PLAN.md` §4 lives here and stays alive forever — `random` →
`greedy` → (rule-based, M3) → `dmcts(small)` → `dmcts(large)` → `cheating`. Without the
bottom of the ladder you cannot tell whether the top of it works.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from . import native
from .cards import card_list
from .observation import Observation
from .rules import HOUSE, SHOVE, Contract, RulesConfig
from .tables import CARD_VALUES
from .trump import select_trump
from .voids import infer_forbidden


class Agent:
    """Stateless. No memory between turns — the observation is the whole world."""

    name = "agent"
    cfg: RulesConfig = HOUSE

    def decide(self, obs: Observation) -> int:
        """Card play."""
        raise NotImplementedError

    def select_trump(self, hand: int, is_forehand: bool) -> Contract | str:
        """Bidding. Defaults to the rule-based selector for every agent.

        Trump choice and card play are separate problems (`PLAN.md` §3.2) and are kept
        separable here so either can be swapped and A/B'd without touching the other.
        """
        return select_trump(hand, is_forehand, self.cfg)


class RandomAgent(Agent):
    """The floor of the ladder. Anything that cannot beat this is broken."""

    name = "random"

    def decide(self, obs: Observation) -> int:
        cards = card_list(obs.legal_moves)
        rng = random.Random(obs.decision_seed)
        return cards[rng.randrange(len(cards))]

    def select_trump(self, hand: int, is_forehand: bool) -> Contract | str:
        rng = random.Random(hand)
        return Contract(rng.randrange(6))


class RandomTrumpMixin:
    """Rule-based card play, random bidding. Exists only to isolate what trump selection is
    worth — `PLAN.md` §3.1 puts it at ~16 points of win rate, which is a claim worth
    checking rather than inheriting."""

    def select_trump(self, hand: int, is_forehand: bool) -> Contract | str:
        rng = random.Random(hand ^ 0x5DEECE66D)
        return Contract(rng.randrange(6))


class GreedyAgent(Agent):
    """Highest-value legal card. Not good play — it dumps aces into lost tricks — but a
    real step above random, and the cheapest possible sanity check on the arena."""

    name = "greedy"

    def decide(self, obs: Observation) -> int:
        values = CARD_VALUES[obs.contract]
        return max(card_list(obs.legal_moves), key=lambda c: (values[c], -c))


@dataclass
class DmctsAgent(Agent):
    """Determinized MCTS, via the Rust core.

    `determinizations` x `iterations` is the search budget. `PLAN.md` §3.1 puts the sweet
    spot near 1000 x 800 with exploration ~1.5; beyond ~1000 determinizations the returns
    flatten. `endgame_cards` switches the search off entirely in favour of an exact solve
    once the round is small enough.
    """

    determinizations: int = 1000
    iterations: int = 800
    exploration: float = 1.5
    endgame_cards: int = 5
    threads: int = 1
    cfg: RulesConfig = HOUSE
    label: str | None = None

    @property
    def name(self) -> str:
        return self.label or f"dmcts({self.determinizations}x{self.iterations})"

    def decide(self, obs: Observation) -> int:
        legal = card_list(obs.legal_moves)
        if len(legal) == 1:
            return legal[0]  # no decision to make; do not burn the budget

        forbidden = infer_forbidden(
            list(obs.tricks_played),
            list(obs.trick),
            obs.trick_leader,
            obs.contract,
            self.cfg,
        )
        candidates = native.dmcts(
            seat=obs.seat,
            hand=obs.hand,
            unseen=obs.unseen,
            trick=list(obs.trick),
            trick_leader=obs.trick_leader,
            contract=obs.contract,
            cfg=self.cfg,
            forbidden=forbidden,
            determinizations=self.determinizations,
            iterations=self.iterations,
            exploration=self.exploration,
            seed=obs.decision_seed,
            threads=self.threads,
            endgame_cards=self.endgame_cards,
        )
        return candidates[0][0]

    def trace(self, obs: Observation) -> list[tuple[int, int, float, int]]:
        """Per-candidate statistics for the decision record in `PLAN.md` §6."""
        forbidden = infer_forbidden(
            list(obs.tricks_played), list(obs.trick), obs.trick_leader, obs.contract, self.cfg
        )
        return native.dmcts(
            seat=obs.seat, hand=obs.hand, unseen=obs.unseen, trick=list(obs.trick),
            trick_leader=obs.trick_leader, contract=obs.contract, cfg=self.cfg,
            forbidden=forbidden, determinizations=self.determinizations,
            iterations=self.iterations, exploration=self.exploration,
            seed=obs.decision_seed, threads=self.threads, endgame_cards=self.endgame_cards,
        )
