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
from functools import lru_cache
from pathlib import Path

from . import bidding, convention, native, reading, sidi_bidding
from .cards import card_list
from .observation import Observation
from .rules import HOUSE, SHOVE, Contract, RulesConfig
from .tables import CARD_VALUES
from .trump import select_trump
from .voids import infer_forbidden


@lru_cache(maxsize=8)
def _read_text(path: str) -> str:
    return Path(path).read_text()


def _sidi_standing(auction: tuple, seat: int):
    """`(contract, value)` of a bid this seat may knock on, or None.

    None when nobody has bid, when it is this seat's own side bidding, or when the bid has
    already been doubled — the same test `Auction.may_double` makes.
    """
    from .auction import Call

    high = None
    for other, text in auction:
        call = Call.parse(text)
        if call.kind == "bid":
            high = (other, call.contract, call.value)
        elif call.kind == "double":
            return None            # already doubled; there is nothing left to knock on
    if high is None or (high[0] - seat) % 2 == 0:
        return None
    return high[1], high[2]


def _sidi_bids(auction: tuple) -> list[tuple[int, int, int]]:
    """The auction's bids as `(seat, contract, value)`. Passes and doubles claim nothing."""
    from .auction import Call

    out = []
    for seat, text in auction:
        call = Call.parse(text)
        if call.kind == "bid":
            out.append((seat, int(call.contract), call.value))
    return out


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

    def sidi_call(self, hand: int, auction: tuple, seat: int) -> str:
        """Sidi Barrani: one call in the auction, in its wire form. The auction is public."""
        return sidi_bidding.choose_call(hand, auction, seat, self.cfg)

    def sidi_double(self, obs: Observation) -> bool:
        """Sidi Barrani: the question after the lead — double the declarers' bid?"""
        return sidi_bidding.double_after_lead(obs.hand, obs.contract, obs.bid_value)

    def sidi_knock(self, hand: int, auction: tuple, seat: int) -> bool:
        """Sidi Barrani: double the standing bid without waiting for this seat's turn.

        At a table you knock the moment you hear the bid. The caller asks every opponent of the
        bidder after each bid; `False` simply means "not this one".
        """
        standing = _sidi_standing(auction, seat)
        if standing is None:
            return False
        contract, value = standing
        return sidi_bidding.may_double(hand, contract, value)


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
    flatten. `endgame_cards` switches the search off in favour of an exact solve once the
    round is small enough — **off**, see the field.
    """

    determinizations: int = 1000
    iterations: int = 800
    exploration: float = 1.5
    #: Hand size at which an exact double-dummy solve replaces the search. **0 — off.**
    #:
    #: It was written for the voting search and is a liability against a shared tree:
    #: turning it off is worth **+1.71** of a round's share over 4,000 deals
    #: (`docs/measurements.md` §3e), the largest measured gain in the file. A solve is
    #: perfect information *inside one imagined world*, so voting between several of them
    #: is exactly the strategy fusion §5h built ISMCTS to avoid.
    #:
    #: Kept as a flag rather than deleted so the comparison stays runnable — and because
    #: the solver is still the right answer for a search that votes.
    endgame_cards: int = 0
    threads: int = 1
    cfg: RulesConfig = HOUSE
    trump_policy: str = "rules"
    label: str | None = None
    #: Order moves the search rated the same by table convention. A flag rather than a
    #: subclass so the arena can A/B it — a convention that costs points is not one worth
    #: having, and that is a claim somebody has to be able to check.
    conventions: bool = True
    #: What a convention may cost: `(visit slack, score slack)` — a move is eligible if it drew
    #: within this share of the search's visits and this much of its score (and at least
    #: `convention.MIN_VISIT_SHARE` of the visits). `(1.0, 0.01)` is a pure *price*: a convention
    #: card may be up to 0.01 of a round's share worse by the search's own estimate. Measured
    #: against no conventions at the shipped budget, 1,000 double deals (`docs/measurements.md` §5u):
    #: the old window (0.05, 0.01) 50.15%, p = 0.32; this price 50.03%, p = 0.86 — free, and the
    #: convention's card rises from 65.9% to 73.2% of the decisions a convention speaks to;
    #: a price of 0.02 reached 79.7% but cost 0.5 (49.49%, p = 0.018).
    convention_slack: tuple = (1.0, 0.01)
    #: Sidi Barrani: weight on what the auction says about the other hands (`rust/src/sidi_read.rs`
    #: — parity names the Bauer or the Nell, size the trumps, believed most for a first bid and a
    #: big jump). **On: +32.0 points written a hand**, p ≈ 0, 1,000 double hands at 38,400
    #: (`docs/measurements.md` §5v) — the largest effect measured in this project, and measured bot
    #: against bot, where every seat speaks the language literally.
    sidi_alpha: float = 1.0
    #: Sidi Barrani: play the hand for the bid — the cards and the stake at the bid's threshold
    #: (`rust/src/objective.rs`) — rather than for a share of the cards. **Off: it lost 5.1 points
    #: written a hand**, p = 0.028 (§5v). The share of the cards it replaced is what the search's
    #: exploration and every other setting were tuned on; the stake's cliff, scaled into [0, 1],
    #: leaves the card points too little of the signal.
    sidi_objective: bool = False
    #: Sidi Barrani: double on an estimate rather than a stopper count — deal the unseen cards,
    #: weight each deal by the auction, play it out with the play model, and double when the
    #: declarers make their bid in fewer than `sidi_double_below` of the deals
    #: (`rust/src/sidi_estimate.rs`). Doubling pays for the defenders exactly when that chance is
    #: under a half; the margin is for the estimate's error and for what a double in the auction
    #: gives up (it ends the bidding, the team's own contract with it). **On, and null** against the
    #: stopper count: −0.18 points a hand, p = 0.94 (§5v), while doubling in 36% of auctions
    #: instead of 3%. Kept as the principled rule the owner asked for; its threshold is untuned.
    sidi_double_model: bool = True
    #: Knock out of turn: answer "double?" the moment an opponent bids, as the player may
    #: (`krass_jass/auction.py`). **Off: it lost 7.61 points written a hand**, p = 4.5e-05
    #: (`docs/measurements.md` §5v). A double ends the auction, so knocking early throws away the
    #: seat's own contract and everything its partner still had to say — and asking both opponents
    #: after every bid doubled about half of all hands against a third. With `sidi_knock_holds_bid`
    #: the seat keeps quiet while it still has a bid of its own; that variant is being measured.
    sidi_knock_anytime: bool = False
    #: Only knock out of turn with nothing left to bid — the part of the rule that costs nothing.
    sidi_knock_holds_bid: bool = True
    sidi_double_below: float = 0.35
    #: Deals per estimate. At 400 the estimate's own spread is ±0.03, which flips decisions near
    #: the threshold; 1,200 halves it for ~140 ms a question.
    sidi_double_samples: int = 1200
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
    #: Information Set MCTS: one tree shared across every imagined world, instead of a tree
    #: per world and a vote. The node *is* the information set, so one policy has to serve
    #: every world consistent with it — which is the constraint strategy fusion breaks.
    #:
    #: **On**, and the first thing in `docs/measurements.md` to earn that on strength rather
    #: than on correctness: +1.15 points at equal iterations and +0.53 at equal wall-clock,
    #: both replicated (§5h). The flag stays so the comparison stays runnable.
    #: Use the cards the table was *shown* as hard constraints. A flag only so the A/B can
    #: run: it is exact public information and there is no case for ignoring it.
    use_known_cards: bool = True
    #: Use the Weis values the table was *called*, including the silences. The shown cards
    #: above are a mask; a value is not, so it filters imagined worlds instead of forbidding
    #: cards — `rust/src/announce.rs` has the measurement that decided the shape.
    use_weis_announced: bool = True
    #: Worlds drawn before the search settles for one that contradicts a call. Buys
    #: belief accuracy with time: at 80.4% rejection, 16 still leaves ~3% of worlds
    #: ignoring what the table said.
    weis_draws: int = 16
    ismcts: bool = True
    #: Iterations sharing one imagined world before a new one is drawn. 1 is textbook ISMCTS
    #: and is dominated by the cost of dealing worlds. **4** keeps the full gain at 1.41x the
    #: determinized search rather than 1.95x; at 8 the gain is gone (§5h). The cliff between
    #: 4 and 8 is why this is a measured constant and not a tuning knob.
    resample_every: int = 4
    #: Expand promising moves first, by the hand-written policy prior in `ismcts.rs`.
    order_moves: bool = False
    #: PUCT with that prior instead of plain UCT. 0 is off. The prior steers which moves are
    #: *searched* and never what a position is *worth* — which is why it escapes §5g, where a
    #: fitted evaluator carrying the same knowledge lost nine points.
    prior_weight: float = 0.0
    #: A prior *learned from play* rather than written from prose — §5i measured the latter at
    #: nothing. Row-major 36 x 127. Cached per node, because a prior over the information set
    #: is a function of the node alone.
    policy_weights: tuple | None = None
    #: Beliefs from behaviour: weight each imagined world by how likely the other seats' plays
    #: were holding that world's hands, under the play model in `rust/src/playmodel.rs`. 0 is
    #: off. This is the common-practice form of the belief work §5k says is the largest lever;
    #: the priors that measured nothing were bounded per-suit tilts. See `rust/src/belief.rs`.
    #:
    #: **On.** With `bid_alpha` below: 51.31% and 51.32% of a round's share against the search
    #: without it, on two seeds at 153,600 iterations (`docs/measurements.md` §5o). α = 2 buys
    #: accuracy by collapsing onto too few worlds, which is why this is 1.
    belief_alpha: float = 1.0
    #: Worlds drawn and weighted per decision when either likelihood is on.
    belief_pool: int = 4096
    #: The same for the bid: P(the call | the bidder's hand) under a softmax over the rule
    #: selector's own contract scores.
    bid_alpha: float = 1.0
    bid_temperature: float = 3.0
    #: Finish rollouts with the play model at this temperature instead of at random. 0 is off.
    rollout_temperature: float = 0.0
    #: Move the other three seats inside the tree by the play model, holding their own hand in
    #: the imagined world, instead of by UCT over statistics pooled across worlds.
    #:
    #: **On.** It fixes a real defect: a shared tree pools the other seats' statistics across
    #: worlds, so they are effectively conditioned on the searcher's real hand and blind to their
    #: own. +0.62 and +1.10 of a round's share on two seeds at the shipped 153,600 iterations,
    #: pooled +0.86 ± 0.14 (`docs/measurements.md` §5p). It costs ~11x a move — ~1.5–2 s natively,
    #: which the owner's latency decision allows. The browser build leaves it off (`wasm_api.rs`):
    #: at ~1.4x native that would be ~5 s a move, and nothing has measured it there.
    tree_policy: bool = True
    policy_temperature: float = 1.0
    #: Path to an alternative trump weights file. Empty uses `krass_jass/data/trump_weights.json`.
    #: Measurement only — it lets the arena play two bidders against each other without
    #: editing the file both implementations read.
    trump_weights: str = ""
    #: Weight on the belief network (`rust/src/beliefnet.rs`) in the same world pool. **0 — off.**
    #: Offline it adds ~0.03 oracle-equivalent on top of plays and bid at weight 1; in play that
    #: measured 50.15%, p = 0.24, over 2,000 deals (`docs/measurements.md` §5q).
    belief_gamma: float = 0.0
    #: Path to a play model other than the compiled-in `krass_jass/data/play_policy.json`. Empty is
    #: the shipped model. Measurement only: the compiled model is shared by every agent in a
    #: process, so an arena comparing two models needs each agent to carry its own.
    play_model: str = ""
    #: Score the search's leaves with the value network (`rust/src/valuenet.rs`) instead of a
    #: random playout. **Off** — candidate B of `docs/neural-plan.md`, under measurement. Meant for
    #: a *small* search: at the shipped budget a playout's noise already averages out (§5g).
    value_net: bool = False
    #: Path to a value network other than the compiled-in one. Measurement only.
    value_model: str = ""

    def select_trump(self, hand: int, is_forehand: bool) -> Contract | str:
        if self.trump_weights and self.trump_policy != "random":
            from .trump import load_weights

            return select_trump(hand, is_forehand, self.cfg, load_weights(self.trump_weights))
        return super().select_trump(hand, is_forehand)

    def _declarers_make(self, seat, hand, history, contract, declarer, bid, auction, seed) -> float:
        p, _ = native.sidi_make_probability(
            seat, hand, history, declarer, contract, declarer, bid, _sidi_bids(auction),
            samples=self.sidi_double_samples, alpha=self.sidi_alpha, seed=seed,
        )
        return p

    def sidi_call(self, hand: int, auction: tuple, seat: int) -> str:
        from .auction import Call

        double = None
        high = next(
            ((s, Call.parse(c)) for s, c in reversed(auction) if Call.parse(c).kind == "bid"), None
        )
        if self.sidi_double_model and high is not None and (high[0] - seat) % 2 == 1:
            bidder, call = high
            # Deterministic for the position, as every decision here must be.
            seed = hash((hand, len(auction), seat)) & 0xFFFF_FFFF
            p = self._declarers_make(seat, hand, [], call.contract, bidder, call.value, auction, seed)
            double = p < self.sidi_double_below
        return sidi_bidding.choose_call(hand, auction, seat, self.cfg, double=double)

    def sidi_knock(self, hand: int, auction: tuple, seat: int) -> bool:
        standing = _sidi_standing(auction, seat)
        if standing is None or not self.sidi_knock_anytime:
            return False
        if self.sidi_knock_holds_bid:
            # A double ends the auction. A seat that could still outbid the standing call has a
            # cheaper answer than spending the auction on a knock.
            own = sidi_bidding.opening(hand)
            if own is not None and min(own[1], 150) > standing[1]:
                return False
        if not self.sidi_double_model:
            return super().sidi_knock(hand, auction, seat)
        contract, value = standing
        bidder = next(s for s, text in reversed(auction) if text == f"{contract.name} {value}")
        seed = hash((hand, len(auction), seat, "knock")) & 0xFFFF_FFFF
        return self._declarers_make(seat, hand, [], contract, bidder, value, auction, seed) < (
            self.sidi_double_below
        )

    def sidi_double(self, obs: Observation) -> bool:
        if not self.sidi_double_model:
            return super().sidi_double(obs)
        history = [((obs.trick_leader + i) % 4, c) for i, c in enumerate(obs.trick)]
        p = self._declarers_make(
            obs.seat, obs.hand, history, obs.contract, obs.declarer_seat, obs.bid_value,
            obs.auction, obs.decision_seed,
        )
        return p < self.sidi_double_below

    @property
    def name(self) -> str:
        return self.label or f"dmcts({self.determinizations}x{self.iterations})"

    def decide(self, obs: Observation) -> int:
        legal = card_list(obs.legal_moves)
        if len(legal) == 1:
            return legal[0]  # no decision to make; do not burn the budget

        forbidden, weis = self._beliefs(obs)
        candidates = native.dmcts(
            seat=obs.seat,
            hand=obs.hand,
            unseen=obs.unseen,
            trick=list(obs.trick),
            trick_leader=obs.trick_leader,
            contract=obs.contract,
            cfg=self.cfg,
            forbidden=forbidden,
            **weis,
            **self._priors(obs),
            determinizations=self.determinizations,
            iterations=self.iterations,
            exploration=self.exploration,
            seed=obs.decision_seed,
            threads=self.threads,
            endgame_cards=self.endgame_cards,
            **self._stakes(obs),
            **self._play(obs),
        )
        if not self.conventions:
            return candidates[0][0]
        # The search has spoken; this only orders the moves it rated the same. See
        # krass_jass/convention.py for why that restriction is the whole design.
        return convention.choose(candidates, obs, forbidden, *self.convention_slack)

    def _beliefs(self, obs: Observation) -> tuple[list[int], dict]:
        """What the search is allowed to believe about the other three hands.

        Two kinds of evidence, and they are different shapes. What the play *proves* and
        what the table was *shown* are statements about cards, so they become a per-seat
        mask of cards that seat cannot hold, and a world contradicting one is never dealt.
        What the table was *told* is a statement about a hand — "I have fifty" names no
        card — so it can only be checked once a world exists, and it travels separately.

        A Weis that was shown is proof of the strongest kind: the table saw those cards in
        that hand, so nobody else can be holding them. `docs/measurements.md` §5k measured
        belief accuracy as the largest lever in the file, §5l the shown half of this, §5m
        the called half.
        """
        forbidden = infer_forbidden(
            list(obs.tricks_played),
            list(obs.trick),
            obs.trick_leader,
            obs.contract,
            self.cfg,
        )
        if self.use_known_cards:
            for seat, card in obs.known_cards:
                for other in range(4):
                    if other != seat:
                        forbidden[other] |= 1 << card

        weis: dict = {}
        if self.use_weis_announced and obs.weis_announced:
            called = [-1] * 4
            for seat, points in obs.weis_announced:
                called[seat] = points
            called[obs.seat] = -1          # own hand is known, not guessed at
            weis = {
                "weis_called": called,
                "weis_played": list(obs.played_by),
                "weis_draws": self.weis_draws,
            }
        return forbidden, weis

    def _stakes(self, obs: Observation) -> dict:
        """What this round is for: the game score, the Weis already banked, the line.

        `target_score` of `None` — which is what `EVAL` uses — leaves the search maximising
        this round's share, the objective every figure before `docs/measurements.md` §5d was
        measured with.
        """
        # The Sidi's game score is a different sum (a stake on top of the cards); until the search
        # has an objective for it (docs/sidi-plan.md, step 3) it maximises the round's share.
        target = 0 if self.cfg.sidi else self.cfg.target_score or 0
        return {
            "scores": tuple(obs.scores),
            "weis": tuple(obs.weis_points),
            "target": target,
            "multiplier": self.cfg.multiplier(obs.contract) if target else 1,
            "adversarial": self.adversarial,
            "risk_lambda": self.risk_lambda,
            "leaf_weights": list(self.leaf_weights) if self.leaf_weights else None,
            "ismcts": self.ismcts,
            "resample_every": self.resample_every,
            "order_moves": self.order_moves,
            "prior_weight": self.prior_weight,
            "policy_weights": list(self.policy_weights) if self.policy_weights else None,
            # Sidi: the hand is played for the bid, not for a share of the cards.
            **(
                {
                    "sidi_bid": obs.bid_value,
                    "sidi_declarers": obs.declarer_seat & 1,
                    "sidi_doubled": obs.doubled,
                }
                if self.cfg.sidi and obs.bid_value and self.sidi_objective
                else {}
            ),
        }

    def _play(self, obs: Observation) -> dict:
        """The round's public history, and how the play model is to be used on it."""
        history = []
        for leader, cards in obs.tricks_played:
            history.extend(((leader + i) % 4, c) for i, c in enumerate(cards))
        history.extend(((obs.trick_leader + i) % 4, c) for i, c in enumerate(obs.trick))
        weighting = self.belief_alpha > 0 or self.bid_alpha > 0 or self.belief_gamma > 0
        known = [0, 0, 0, 0]
        for s, c in obs.known_cards:
            known[s] |= 1 << c
        return {
            "declarer": obs.declarer_seat,
            "history": history,
            "belief_alpha": self.belief_alpha,
            "belief_pool": self.belief_pool if weighting else 0,
            # The bid model is the Schieber's choose-or-shove; a Sidi auction is another language.
            "bid_alpha": 0.0 if self.cfg.sidi else self.bid_alpha,
            "bid_temperature": self.bid_temperature,
            "rollout_temperature": self.rollout_temperature,
            "tree_policy": self.tree_policy,
            "policy_temperature": self.policy_temperature,
            "belief_gamma": self.belief_gamma,
            "known": known,
            "play_model_json": _read_text(self.play_model) if self.play_model else None,
            "value_net": self.value_net,
            "value_model_json": _read_text(self.value_model) if self.value_model else None,
            **(
                {"sidi_auction": _sidi_bids(obs.auction), "sidi_alpha": self.sidi_alpha}
                if self.cfg.sidi
                else {}
            ),
        }

    def beliefs(self, obs: Observation) -> dict:
        """What this agent believes about the other three hands, as probabilities per card.

        The app's test mode shows it, so a player can see what the bot is reasoning from. It is
        the search's own pool (`krass_jass/native.py`), not a second opinion.
        """
        cards, ess = native.belief_marginals(obs, self)
        return {
            "cards": [
                {"card": card, "seats": [round(a, 4), round(b, 4), round(c, 4)]}
                for card, a, b, c in cards
            ],
            "ess": round(ess, 1),
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
        if self.read_bidding and not self.cfg.sidi:
            bid_suits, ranks = bidding.infer_from_bid(
                obs.forehand, obs.declarer_seat, obs.contract, obs.seat, self.cfg
            )
            suits = bidding.merge(suits, bid_suits)
        if not any(any(r) for r in suits) and not any(ranks):
            return {"affinity": None, "rank_bias": None}
        return {"affinity": suits, "rank_bias": ranks}

    def trace(self, obs: Observation) -> list[tuple[int, int, float, int]]:
        """Per-candidate statistics for the decision record in `PLAN.md` §6."""
        forbidden, weis = self._beliefs(obs)
        return native.dmcts(
            seat=obs.seat, hand=obs.hand, unseen=obs.unseen, trick=list(obs.trick),
            trick_leader=obs.trick_leader, contract=obs.contract, cfg=self.cfg,
            forbidden=forbidden, **weis, **self._priors(obs),
            determinizations=self.determinizations,
            iterations=self.iterations, exploration=self.exploration,
            seed=obs.decision_seed, threads=self.threads, endgame_cards=self.endgame_cards,
            **self._stakes(obs),
            **self._play(obs),
        )
