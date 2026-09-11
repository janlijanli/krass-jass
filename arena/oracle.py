"""How much would *better beliefs* be worth?

The gap to the cheating agent is ~8.4 points after ISMCTS recovered 0.74 of it (§5h), and
strategy fusion turned out to be only about 8% of the hidden-information cost. The usual next
suspect is **non-locality** — the claim that determinization samples the wrong distribution,
because an opponent's earlier choices were *choices*, and the deals that survive them are not
uniformly likely among the deals that merely survive the hard constraints in `voids.py`.

That is a claim about the belief distribution, so measure the belief distribution's worth
directly: with probability `oracle_p`, the search imagines the **true** deal instead of a
sampled one. Sweeping p walks the agent from its own beliefs to perfect ones, and the shape of
the curve is the answer:

- **Steep near p=0** — beliefs are valuable at the margin, so better inference pays, and
  non-locality is worth chasing.
- **Flat near p=0, rising late** — only *nearly perfect* beliefs help. Realistic inference
  improves beliefs slightly, so it would buy nothing, and the gap is mostly irreducible.

The second reading would also retire a hypothesis this file has carried all day without
evidence.

Like `cheating.py`, this takes the true deal and therefore lives in `arena/` and is never
reachable from anything that serves a game. Nothing in `krass_jass/` imports it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from krass_jass import convention, native
from krass_jass.agent import Agent
from krass_jass.cards import card_list
from krass_jass.observation import Observation
from krass_jass.rules import EVAL, RulesConfig
from krass_jass.voids import infer_forbidden


@dataclass
class OracleBeliefAgent(Agent):
    """The shipped search, with a fraction of its imagined worlds replaced by the real one."""

    oracle_p: float = 0.0
    determinizations: int = 40
    iterations: int = 60
    exploration: float = 1.5
    endgame_cards: int = 0
    resample_every: int = 4
    cfg: RulesConfig = EVAL
    label: str = "oracle"
    #: Set by the arena before each decision. Not derived from any observation.
    true_hands: list[int] = field(default_factory=lambda: [0, 0, 0, 0])

    @property
    def name(self) -> str:
        return self.label

    def decide(self, obs: Observation) -> int:
        legal = card_list(obs.legal_moves)
        if len(legal) == 1:
            return legal[0]
        forbidden = infer_forbidden(
            list(obs.tricks_played), list(obs.trick), obs.trick_leader, obs.contract, self.cfg
        )
        candidates = native.dmcts(
            seat=obs.seat, hand=obs.hand, unseen=obs.unseen, trick=list(obs.trick),
            trick_leader=obs.trick_leader, contract=obs.contract, cfg=self.cfg,
            forbidden=forbidden, determinizations=self.determinizations,
            iterations=self.iterations, exploration=self.exploration,
            seed=obs.decision_seed, threads=1, endgame_cards=self.endgame_cards,
            ismcts=True, resample_every=self.resample_every,
            oracle_hands=list(self.true_hands), oracle_p=self.oracle_p,
        )
        return convention.choose(candidates, obs, forbidden)
