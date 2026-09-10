"""Tournament harness.

`PLAN.md` §4 is blunt about this: get evaluation right early or every later decision is
noise. Two things do the heavy lifting.

**Double rounds.** Every deal is played twice with the agents swapped between teams, so
each pair cancels the luck of the deal. Without it, comparing two bots over any affordable
number of rounds is a coin flip — the deal dominates.

**A paired test.** Double rounds produce a paired design, so the per-deal differences are
what carry the signal. Running an unpaired test on them throws away most of the variance
reduction the pairing just bought.

Weis, Stöck and the match bonus are off here (`EVAL`), because they dominate scoring
variance and would drown any real difference between two agents.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass

from krass_jass.agent import Agent
from krass_jass.cards import card_list
from krass_jass.observation import build_observation, derive_decision_seed
from krass_jass.rules import EVAL, Contract, RulesConfig
from krass_jass.state import RoundState

POINTS_PER_ROUND = 157


def deal_hands(rng: random.Random) -> list[int]:
    deck = list(range(36))
    rng.shuffle(deck)
    return [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]


def play_round(
    hands: list[int],
    contract: Contract,
    leader: int,
    seats: dict[int, Agent],
    cfg: RulesConfig,
    game_seed: int,
    game_id: str = "arena",
) -> tuple[int, int]:
    """One round. Returns team points.

    Every agent decision is seeded from a value derived from `game_seed`, so a round replays
    bit-for-bit — including the search — which is what turns a surprising move into a test
    case rather than an anecdote.
    """
    state = RoundState(contract=contract, hands=list(hands), cfg=cfg, leader=leader)
    trick_no = 0
    while not state.done:
        seat = state.to_play
        agent = seats[seat]
        # The cheating baseline needs the real deal. Only the arena may hand it over, and
        # only to an agent that declares it wants it — never through an observation.
        if hasattr(agent, "true_hands"):
            agent.true_hands = list(state.hands)
        obs = build_observation(
            state,
            seat,
            decision_seed=derive_decision_seed(game_seed, game_id, seat, 0, trick_no),
        )
        card = agent.decide(obs)
        # The engine is authoritative — an agent's move is re-validated, never trusted.
        state.play(card)
        trick_no = len(state.tricks_played)
    score = state.score()
    return score.total


def double_round(
    hands: list[int],
    contract: Contract,
    leader: int,
    a: Agent,
    b: Agent,
    cfg: RulesConfig,
    game_seed: int,
) -> tuple[float, float]:
    """Play one deal twice with the agents swapped. Returns each side's share of the points
    across the pair, which is the unit the paired test consumes.

    Both halves use the **same** `game_seed` — common random numbers. Decision seeds already
    vary by seat and trick, so the halves are not duplicates; reusing the seed just removes
    a source of variance the pairing exists to cancel. Giving the second half a different
    seed leaks noise straight back in, and `test_double_round_swaps_the_agents` catches it:
    an agent playing itself must score exactly half, with no variance at all.
    """
    first = play_round(hands, contract, leader, {0: a, 2: a, 1: b, 3: b}, cfg, game_seed)
    second = play_round(hands, contract, leader, {0: b, 2: b, 1: a, 3: a}, cfg, game_seed)

    a_points = first[0] + second[1]
    b_points = first[1] + second[0]
    total = a_points + b_points
    if total == 0:
        return 0.5, 0.5
    return a_points / total, b_points / total


@dataclass
class MatchResult:
    a: str
    b: str
    deals: int
    a_share: float          #: mean fraction of points taken by A
    std: float
    t_statistic: float
    p_value: float

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05

    def __str__(self) -> str:
        pct = self.a_share * 100
        mark = "" if self.significant else "  (not significant)"
        return (
            f"{self.a:>26} vs {self.b:<26} "
            f"{pct:6.2f}% ± {self.std * 100:4.2f}  "
            f"n={self.deals:<5} p={self.p_value:.2e}{mark}"
        )


def paired_test(differences: list[float]) -> tuple[float, float]:
    """Paired t on the per-deal differences, with a normal approximation to the t
    distribution — at the sample sizes used here (hundreds of deals) the difference from
    exact Student's t is far below the noise floor.
    """
    n = len(differences)
    if n < 2:
        return 0.0, 1.0
    mean = statistics.fmean(differences)
    sd = statistics.stdev(differences)
    if sd == 0:
        return math.inf if mean else 0.0, 0.0 if mean else 1.0
    t = mean / (sd / math.sqrt(n))
    p = 2 * (1 - statistics.NormalDist().cdf(abs(t)))
    return t, p


def match(
    a: Agent,
    b: Agent,
    deals: int = 100,
    seed: int = 0,
    cfg: RulesConfig = EVAL,
    contract: Contract | None = None,
) -> MatchResult:
    """Run `deals` double rounds of A against B.

    `contract` fixes the trump for every deal; leaving it `None` picks one at random per
    deal. Trump *selection* is M3 and not built yet, so this is a placeholder that at least
    exercises all six contracts rather than silently benchmarking only one.
    """
    rng = random.Random(seed)
    shares: list[float] = []
    for i in range(deals):
        hands = deal_hands(rng)
        c = contract if contract is not None else Contract(rng.randrange(6))
        leader = rng.randrange(4)
        a_share, _ = double_round(hands, c, leader, a, b, cfg, game_seed=seed * 1_000_003 + i * 2)
        shares.append(a_share)

    # Under the null hypothesis each side takes half the points, so the per-deal difference
    # from 0.5 is what the paired test looks at.
    t, p = paired_test([s - 0.5 for s in shares])
    return MatchResult(
        a=a.name,
        b=b.name,
        deals=deals,
        a_share=statistics.fmean(shares),
        std=statistics.stdev(shares) if len(shares) > 1 else 0.0,
        t_statistic=t,
        p_value=p,
    )
