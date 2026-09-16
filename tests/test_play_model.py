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


def test_the_shipped_play_model_settings():
    """Beliefs (§5o) and the tree policy (§5p) each shipped on two replicated matches; policy
    rollouts measured null at equal time and stay off."""
    st, _ = _mid_round(3, 6)
    play = DmctsAgent()._play(build_observation(st, st.to_play, declarer_seat=1))
    assert play["belief_alpha"] == 1.0 and play["bid_alpha"] == 1.0
    assert play["belief_pool"] == 4096
    assert play["tree_policy"] is True
    assert play["rollout_temperature"] == 0.0


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



def test_rescoring_saved_worlds_reproduces_the_pool_likelihoods():
    """`rs_belief_loglik` is how temperature sweeps avoid replaying rounds; it must give the same
    numbers the pool computed when it drew those worlds."""
    from arena.belief_data import public_inputs

    st, _ = _mid_round(17, 13)
    obs = build_observation(st, st.to_play, declarer_seat=1)
    x = public_inputs(obs, DmctsAgent(cfg=HOUSE))
    worlds, play_ll, bid_ll = core.rs_belief_pool(
        obs.seat, obs.hand, obs.unseen, list(obs.trick), obs.trick_leader, int(obs.contract),
        x["forbidden"], 1, x["history"], 64, 5,
    )
    pl, bl = core.rs_belief_loglik(worlds, obs.seat, x["forehand"], int(obs.contract), 1, x["history"])
    assert pl == pytest.approx(play_ll, rel=1e-5, abs=1e-5)
    assert bl == pytest.approx(bid_ll, rel=1e-5, abs=1e-5)


def test_an_agent_can_read_the_table_through_its_own_play_model():
    from pathlib import Path

    path = str(Path(__file__).resolve().parents[1] / "krass_jass" / "data" / "play_policy.json")
    agent = DmctsAgent(determinizations=4, iterations=30, cfg=HOUSE, belief_pool=128, play_model=path)
    st, _ = _mid_round(2, 9)
    obs = build_observation(st, st.to_play, declarer_seat=1, decision_seed=3)
    assert obs.legal_moves >> agent.decide(obs) & 1
