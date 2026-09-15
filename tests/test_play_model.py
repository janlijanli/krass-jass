"""The play model and what uses it: belief weighting, policy rollouts, the tree policy.

The model itself is in `rust/src/playmodel.rs` and its unit tests are there. These pin the
Python side of the contract: that the history handed to the search is the public play order,
that everything is off unless asked for, and that each mode still returns a legal move.
"""

from __future__ import annotations

import math
import random

import pytest

from arena.arena import deal_hands
from krass_jass import native
from krass_jass.agent import DmctsAgent
from krass_jass.cards import card_list
from krass_jass.observation import build_observation
from krass_jass.rules import HOUSE, Contract
from krass_jass.state import RoundState

pytestmark = pytest.mark.skipif(not native.AVAILABLE, reason="Rust core not built")
core = native._core


def _mid_round(seed: int, cards: int):
    rng = random.Random(seed)
    hands = deal_hands(rng)
    st = RoundState(contract=Contract.HEARTS, hands=hands, cfg=HOUSE, leader=1)
    played = []
    for _ in range(cards):
        seat = st.to_play
        card = rng.choice(card_list(st.legal_moves(seat)))
        played.append((seat, card))
        st.play(card)
    return st, played


@pytest.mark.parametrize("cards", [0, 3, 4, 13, 22])
def test_history_is_the_public_play_order(cards):
    st, played = _mid_round(11 + cards, cards)
    obs = build_observation(st, st.to_play, declarer_seat=1)
    assert DmctsAgent()._play(obs)["history"] == played


def test_beliefs_are_on_and_the_rest_of_the_play_model_is_off_by_default():
    """Beliefs from play and bid shipped on two replicated matches (measurements.md §5o); the
    tree policy and policy rollouts have only equal-iteration results so far (§5p)."""
    st, _ = _mid_round(3, 6)
    play = DmctsAgent()._play(build_observation(st, st.to_play, declarer_seat=1))
    assert play["belief_alpha"] == 1.0 and play["bid_alpha"] == 1.0
    assert play["belief_pool"] == 4096
    assert play["rollout_temperature"] == 0.0
    assert play["tree_policy"] is False


def test_shipped_model_is_a_distribution():
    st, _ = _mid_round(5, 9)
    obs = build_observation(st, st.to_play, declarer_seat=1)
    live = obs.hand | obs.unseen
    out = core.rs_play_log_probs(
        obs.hand, live, list(obs.trick), obs.trick_leader, obs.seat, int(obs.contract), 1,
        obs.legal_moves,
    )
    assert [c for c, _ in out] == card_list(obs.legal_moves)
    assert math.isclose(sum(math.exp(lp) for _, lp in out), 1.0, rel_tol=1e-4)


@pytest.mark.parametrize(
    "settings",
    [
        {"belief_alpha": 1.0, "belief_pool": 256},
        {"bid_alpha": 1.0, "belief_pool": 256},
        {"rollout_temperature": 1.0},
        {"tree_policy": True},
        {"belief_gamma": 0.5, "belief_pool": 256},
        {"belief_alpha": 0.0, "bid_alpha": 0.0, "belief_gamma": 1.0, "belief_pool": 256},
    ],
)
def test_every_mode_returns_a_legal_move(settings):
    agent = DmctsAgent(determinizations=4, iterations=30, cfg=HOUSE, **settings)
    for seed in range(3):
        st, _ = _mid_round(seed, 5 + 4 * seed)
        obs = build_observation(st, st.to_play, declarer_seat=1, decision_seed=seed)
        assert obs.legal_moves >> agent.decide(obs) & 1

