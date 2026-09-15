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
import os
import random
import statistics
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from krass_jass.agent import Agent
from krass_jass.cards import card_list
from krass_jass.observation import build_observation, derive_decision_seed
from krass_jass.rules import EVAL, SHOVE, Contract, RulesConfig
from krass_jass.state import RoundState
from krass_jass.weis import best_weis, find_weis, score_stoeck, score_weis

POINTS_PER_ROUND = 157


def deal_hands(rng: random.Random) -> list[int]:
    deck = list(range(36))
    rng.shuffle(deck)
    return [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]


def choose_contract(
    hands: list[int],
    forehand: int,
    seats: dict[int, Agent],
    cfg: RulesConfig,
) -> tuple[Contract, int]:
    """Run the bidding. Returns the contract and the declaring seat.

    Forehand picks or shoves; a partner who is shoved to must choose, so the bidding always
    terminates. `allow_zurueckschieben` (shoving back) is off by default and the selector
    never returns SHOVE off-forehand, but the guard stays in — a future learned selector
    could, and an infinite bid loop is a nasty way to find out.
    """
    action = seats[forehand].select_trump(hands[forehand], is_forehand=True)
    declarer = forehand
    if action is SHOVE or action == SHOVE:
        partner = (forehand + 2) % 4
        action = seats[partner].select_trump(hands[partner], is_forehand=False)
        declarer = partner
        if action is SHOVE or action == SHOVE:
            raise ValueError("a shoved-to partner must choose a contract")
    return Contract(action), declarer


def resolve_weis(hands: list[int], contract: Contract, leader: int, cfg: RulesConfig):
    """Weis and Stöck for a round, the cards the winner shows, and what every seat called.

    Mirrors the automatic path in `Game._resolve_weis`: everyone announces, the single best
    Weis is turned face up to prove it, and the winning *team* scores all of its Weis.

    It exists here because the round-level arena plays a `RoundState` directly and so never
    had Weis at all — which meant `EVAL` (Weis off) was the only setting it could measure, and
    anything touching Weis was invisible to the cheap instrument. See `docs/measurements.md`
    §5l, where exactly that blind spot hid a piece of exact public information for the whole
    project.
    """
    if not cfg.weis_enabled:
        return (0, 0), (0, 0), (), ()

    # `is_trump`, not truthiness: Contract.DIAMONDS is 0 and therefore falsy.
    trump = contract.trump_suit if contract.is_trump else -1
    points, winner = score_weis(list(hands), trump, cfg, leader)
    stoeck = score_stoeck(list(hands), trump, cfg)

    shown: tuple = ()
    if winner >= 0:
        best = best_weis(find_weis(hands[winner], cfg, trump), trump, cfg)
        if best is not None:
            shown = tuple((winner, c) for c in card_list(best.cards))

    # Stage one, which the shown cards are only the visible end of: everyone calls a value
    # as their turn comes round, and a value nobody ever proves is public all the same. Zero
    # for a seat that called nothing — silence is the common call and the informative one.
    announced = tuple(
        (seat, sum(m.points for m in find_weis(hands[seat], cfg, trump))) for seat in range(4)
    )
    return points, stoeck, shown, announced


def play_round(
    hands: list[int],
    contract: Contract | None,
    leader: int,
    seats: dict[int, Agent],
    cfg: RulesConfig,
    game_seed: int,
    game_id: str = "arena",
) -> tuple[int, int]:
    """One round. Returns team points, already scaled by the contract multiplier.

    Every agent decision is seeded from a value derived from `game_seed`, so a round replays
    bit-for-bit — including the search — which is what turns a surprising move into a test
    case rather than an anecdote.
    """
    declarer = leader
    if contract is None:
        contract, declarer = choose_contract(hands, leader, seats, cfg)

    weis, stoeck, shown, announced = resolve_weis(hands, contract, leader, cfg)
    state = RoundState(contract=contract, hands=list(hands), cfg=cfg, leader=leader)
    trick_no = 0
    while not state.done:
        seat = state.to_play
        agent = seats[seat]
        # The cheating baseline needs the real deal. Only the arena may hand it over, and
        # only to an agent that declares it wants it — never through an observation.
        if hasattr(agent, "true_hands"):
            agent.true_hands = list(state.hands)
        # A shown Weis is public, so the search is entitled to it — and without this the
        # round-level arena could not measure §5l at all. A shown card drops out once it is
        # played, because it is then public through `played` like any other.
        obs = build_observation(
            state,
            seat,
            declarer_seat=declarer,
            decision_seed=derive_decision_seed(game_seed, game_id, seat, 0, trick_no),
            known_cards=tuple((s, c) for s, c in shown if state.hands[s] & (1 << c)),
            weis_announced=announced,
        )
        card = agent.decide(obs)
        # The engine is authoritative — an agent's move is re-validated, never trusted.
        state.play(card)
        trick_no = len(state.tricks_played)
    score = state.score(weis=weis, stoeck=stoeck)
    return score.total


def double_round(
    hands: list[int],
    contract: Contract | None,
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

    With `contract=None` each half bids independently, because a different agent sits in
    forehand — trump selection is part of the skill being compared, not a fixed condition.
    Pass an explicit contract to hold bidding constant and isolate card play.
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


def deal_spec(seed: int, index: int, contract: Contract | None):
    """The whole setup for deal `index`, derived from `(seed, index)` alone.

    Deliberately *not* drawn from one sequential stream: making each deal independent of
    how many came before is what lets the match run across processes and still reproduce
    exactly. Order-dependent seeding and parallelism cannot both be had.
    """
    rng = random.Random(f"deal:{seed}:{index}")
    hands = deal_hands(rng)
    c = contract
    leader = rng.randrange(4)
    game_seed = seed * 1_000_003 + index * 2
    return hands, c, leader, game_seed


def _run_chunk(args) -> list[float]:
    a, b, cfg, seed, contract, indices = args
    out = []
    for i in indices:
        hands, c, leader, game_seed = deal_spec(seed, i, contract)
        a_share, _ = double_round(hands, c, leader, a, b, cfg, game_seed)
        out.append(a_share)
    return out


def match(
    a: Agent,
    b: Agent,
    deals: int = 100,
    seed: int = 0,
    cfg: RulesConfig = EVAL,
    contract: Contract | None = None,
    workers: int | None = None,
) -> MatchResult:
    """Run `deals` double rounds of A against B.

    `contract` fixes the trump for every deal; leaving it `None` means the agents bid for
    it, which is the realistic setting and the default.

    `workers` spreads the deals across processes. Deals are independent, so this scales
    close to linearly, and results are identical to a serial run — each deal's setup and
    seeds come from `(seed, index)`, not from a shared stream. Prefer this over giving the
    agents threads: parallelising across deals keeps every core busy, while parallelising
    inside one move leaves them idle between decisions.
    """
    if workers is None:
        workers = 1
    if workers <= 1:
        shares = _run_chunk((a, b, cfg, seed, contract, range(deals)))
    else:
        workers = min(workers, deals)
        chunks = [list(range(i, deals, workers)) for i in range(workers)]
        payload = [(a, b, cfg, seed, contract, c) for c in chunks if c]
        shares = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for part in pool.map(_run_chunk, payload):
                shares.extend(part)

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
