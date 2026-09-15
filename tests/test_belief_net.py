"""The belief network's contract from the Python side: what it is fed, and what comes back.

The network itself and its feature layout are unit-tested in `rust/src/beliefnet.rs`. These pin
that the recorder builds its inputs from an observation alone, and that the probabilities the
search would use are a distribution over exactly the seats the rules still allow.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

from arena.arena import deal_hands
from arena.belief_data import public_inputs
from krass_jass import native
from krass_jass.agent import DmctsAgent
from krass_jass.cards import card_list
from krass_jass.observation import build_observation
from krass_jass.rules import HOUSE, Contract
from krass_jass.state import RoundState

pytestmark = pytest.mark.skipif(not native.AVAILABLE, reason="Rust core not built")
core = native._core
UNTRAINED = '{"h1": 0}'


def _obs(seed: int, cards: int, hands=None):
    rng = random.Random(seed)
    hands = hands or deal_hands(rng)
    st = RoundState(contract=Contract.SPADES, hands=list(hands), cfg=HOUSE, leader=2)
    for _ in range(cards):
        st.play(rng.choice(card_list(st.legal_moves(st.to_play))))
    return st, build_observation(st, st.to_play, declarer_seat=2, weis_announced=((0, 0), (1, 20), (2, 0), (3, 0)))


KEYS = ("seat", "hand", "history", "contract", "declarer", "forehand", "forbidden", "known",
        "weis_called")


@pytest.mark.parametrize("cards", [0, 5, 14, 27])
def test_inputs_do_not_change_when_the_hidden_cards_do(cards):
    """Swap hidden cards between the other seats. Nothing the network is fed may move."""
    st, obs = _obs(3 + cards, cards)
    x = public_inputs(obs, DmctsAgent(cfg=HOUSE))
    before = core.rs_belief_features(*(x[k] for k in KEYS))
    assert len(np.frombuffer(before, dtype=np.float32)) == 865
    assert set(x) == set(KEYS), "the recorder's inputs grew a field nobody reviewed"

    others = [s for s in range(4) if s != obs.seat]
    a, b = others[0], others[1]
    ca, cb = card_list(st.hands[a]), card_list(st.hands[b])
    if not ca or not cb:
        pytest.skip("nothing hidden to swap")
    st.hands[a] = st.hands[a] ^ (1 << ca[0]) | (1 << cb[0])
    st.hands[b] = st.hands[b] ^ (1 << cb[0]) | (1 << ca[0])
    moved = build_observation(st, obs.seat, declarer_seat=2,
                              weis_announced=((0, 0), (1, 20), (2, 0), (3, 0)))
    y = public_inputs(moved, DmctsAgent(cfg=HOUSE))
    assert y == x
    assert core.rs_belief_features(*(y[k] for k in KEYS)) == before


def test_probabilities_cover_exactly_the_allowed_seats():
    _, obs = _obs(21, 10)
    x = public_inputs(obs, DmctsAgent(cfg=HOUSE))
    args = [x[k] for k in ("seat", "hand", "history", "contract", "declarer", "forehand",
                           "forbidden", "known", "weis_called")]
    lp = core.rs_belief_log_probs(*args, UNTRAINED)
    for card in range(36):
        hidden = obs.unseen >> card & 1
        probs = [math.exp(v) for v in lp[card]]
        if not hidden:
            assert sum(probs) == 0.0
            continue
        allowed = [not (x["forbidden"][(obs.seat + r) % 4] >> card & 1) for r in (1, 2, 3)]
        assert math.isclose(sum(probs), 1.0, rel_tol=1e-5)
        for ok, p in zip(allowed, probs):
            assert (p > 0) == ok
