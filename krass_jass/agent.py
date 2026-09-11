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

from . import bidding, convention, native, reading
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
    #: "rules" or "random". A field rather than a subclass so agents stay picklable and
    #: can cross a process pool — the arena runs deals in parallel.
    trump_policy: str = "rules"

    def decide(self, obs: Observation) -> int:
        """Card play."""
        raise NotImplementedError

    def select_trump(self, hand: int, is_forehand: bool) -> Contract | str:
        """Bidding. Defaults to the rule-based selector for every agent.

        Trump choice and card play are separate problems (`PLAN.md` §3.2) and stay
        separable here so either can be swapped and A/B'd without touching the other —
        which is exactly how trump selection gets measured in isolation.
        """
        if self.trump_policy == "random":
            return Contract(random.Random(hand ^ 0x5DEECE66D).randrange(6))
        return select_trump(hand, is_forehand, self.cfg)


class RandomAgent(Agent):
    """The floor of the ladder. Anything that cannot beat this is broken."""

    name = "random"

    def decide(self, obs: Observation) -> int:
        cards = card_list(obs.legal_moves)
        rng = random.Random(obs.decision_seed)
        return cards[rng.randrange(len(cards))]

    trump_policy: str = "random"


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
    trump_policy: str = "rules"
    label: str | None = None
    #: Order moves the search rated the same by table convention. A flag rather than a
    #: subclass so the arena can A/B it — a convention that costs points is not one worth
    #: having, and that is a claim somebody has to be able to check.
    conventions: bool = True
    #: Read the other seats' discards as signals and tilt the determinization towards the
    #: worlds they suggest. **Off**, and the flag exists because that is a measured decision
    #: rather than an opinion: it is worth nothing at this budget even against a partner who
    #: signals deliberately (`docs/measurements.md` §5c). Kept switchable so the next person
    #: to have the idea can re-run the match instead of rebuilding it.
    signal_reading: bool = False
    #: Model the other team as playing against you. False reproduces the original search,
    #: which maximised the root team's value at every node in the tree — including the
    #: opponents' — and so valued lines by what happens when they cooperate.
    adversarial: bool = True
    #: Read the bidding into the imagined hands: Obenabe means aces, a shove means neither,
    #: choosing a suit means length in it. Unlike a discard convention this is forced — every
    #: seat has to bid — so the signal is always there. See `krass_jass/bidding.py`.
    read_bidding: bool = True
    #: Risk aversion in the reward, offsetting the over-optimism determinized search has by
    #: construction. 0 is off; see `krass_jass/objective.py` for why it must be non-linear.
    risk_lambda: float = 0.0
    #: Linear leaf evaluator in place of the random playout — `docs/value-net-plan.md`
    #: Phase 0. `None` keeps the playout, which is the baseline every figure was measured
    #: against. Fitted to the playout's own *mean*, so this is variance reduction and not a
    #: change of target.
    leaf_weights: tuple | None = None

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
        # What the play proves, and separately what it suggests. The first removes worlds
        # from the search; the second only changes how often it visits them.
        candidates = native.dmcts(
            seat=obs.seat,
            hand=obs.hand,
            unseen=obs.unseen,
            trick=list(obs.trick),
            trick_leader=obs.trick_leader,
            contract=obs.contract,
            cfg=self.cfg,
            forbidden=forbidden,
            **self._priors(obs),
            determinizations=self.determinizations,
            iterations=self.iterations,
            exploration=self.exploration,
            seed=obs.decision_seed,
            threads=self.threads,
            endgame_cards=self.endgame_cards,
            **self._stakes(obs),
        )
        if not self.conventions:
            return candidates[0][0]
        # The search has spoken; this only orders the moves it rated the same. See
        # krass_jass/convention.py for why that restriction is the whole design.
        return convention.choose(candidates, obs, forbidden)

    def _stakes(self, obs: Observation) -> dict:
        """What this round is for: the game score, the Weis already banked, the line.

        `target_score` of `None` — which is what `EVAL` uses — leaves the search maximising
        this round's share, the objective every figure before `docs/measurements.md` §5d was
        measured with.
        """
        target = self.cfg.target_score or 0
        return {
            "scores": tuple(obs.scores),
            "weis": tuple(obs.weis_points),
            "target": target,
            "multiplier": self.cfg.multiplier(obs.contract) if target else 1,
            "adversarial": self.adversarial,
            "risk_lambda": self.risk_lambda,
            "leaf_weights": list(self.leaf_weights) if self.leaf_weights else None,
        }

    def _priors(self, obs: Observation) -> dict:
        """Everything that tilts which worlds get imagined, and nothing that forbids one.

        Two sources, both soft and both bounded: what the discards suggest (off by default,
        measured at nothing) and what the bidding said (on).
        """
        suits = [[0] * 4 for _ in range(4)]
        ranks = [0] * 4
        if self.signal_reading:
            suits = reading.infer_affinity(
                list(obs.tricks_played), list(obs.trick), obs.trick_leader, obs.contract,
                self.cfg,
            )
        if self.read_bidding:
            bid_suits, ranks = bidding.infer_from_bid(
                obs.forehand, obs.declarer_seat, obs.contract, obs.seat, self.cfg
            )
            suits = bidding.merge(suits, bid_suits)
        if not any(any(r) for r in suits) and not any(ranks):
            return {"affinity": None, "rank_bias": None}
        return {"affinity": suits, "rank_bias": ranks}

    def trace(self, obs: Observation) -> list[tuple[int, int, float, int]]:
        """Per-candidate statistics for the decision record in `PLAN.md` §6."""
        forbidden = infer_forbidden(
            list(obs.tricks_played), list(obs.trick), obs.trick_leader, obs.contract, self.cfg
        )
        return native.dmcts(
            seat=obs.seat, hand=obs.hand, unseen=obs.unseen, trick=list(obs.trick),
            trick_leader=obs.trick_leader, contract=obs.contract, cfg=self.cfg,
            forbidden=forbidden, **self._priors(obs),
            determinizations=self.determinizations,
            iterations=self.iterations, exploration=self.exploration,
            seed=obs.decision_seed, threads=self.threads, endgame_cards=self.endgame_cards,
            **self._stakes(obs),
        )
