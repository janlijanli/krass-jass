"""Cheating MCTS — the top of the baseline ladder and the honest upper bound.

It sees every hand. `PLAN.md` §4 keeps it in the ladder forever because it measures the one
thing no other baseline can: **how much the hidden information is costing you**. The gap
between your real agent and this one is the part of the problem that better search cannot
solve, and closing it is what team play and inference are for.

It lives in `arena/` rather than `krass_jass/agent.py` on purpose. It takes the true deal,
so it violates the information boundary by construction and must never be reachable from
anything that serves a game. Nothing in `krass_jass/` imports this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from krass_jass import native
from krass_jass.agent import Agent
from krass_jass.cards import FULL_DECK, card_list
from krass_jass.observation import Observation
from krass_jass.rules import EVAL, RulesConfig


@dataclass
class CheatingAgent(Agent):
    """Perfect-information UCT on the real deal.

    Implemented by pinning the determinization instead of adding a second search: forbid
    every seat from holding any card it does not actually hold, and the sampler can only
    produce the true world. One determinization is then enough, because there is only one.
    """

    iterations: int = 8000
    exploration: float = 1.5
    endgame_cards: int = 5
    cfg: RulesConfig = EVAL
    label: str = "cheating"
    #: Set by the arena before each decision. Not derived from any observation.
    true_hands: list[int] = field(default_factory=lambda: [0, 0, 0, 0])

    @property
    def name(self) -> str:
        return self.label

    def decide(self, obs: Observation) -> int:
        legal = card_list(obs.legal_moves)
        if len(legal) == 1:
            return legal[0]

        forbidden = [FULL_DECK & ~h for h in self.true_hands]
        forbidden[obs.seat] = 0  # own hand is passed directly

        candidates = native.dmcts(
            seat=obs.seat,
            hand=obs.hand,
            unseen=obs.unseen,
            trick=list(obs.trick),
            trick_leader=obs.trick_leader,
            contract=obs.contract,
            cfg=self.cfg,
            forbidden=forbidden,
            determinizations=1,
            iterations=self.iterations,
            exploration=self.exploration,
            seed=obs.decision_seed,
            endgame_cards=self.endgame_cards,
        )
        return candidates[0][0]
