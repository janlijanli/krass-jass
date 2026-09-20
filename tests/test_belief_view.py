"""The test mode: what the bot believes about the other hands, published for a player.

It is the search's own pool (`rust/src/belief.rs`) summarised rather than sampled, so the checks
here are the ones that make it honest: it says nothing about cards the player can see, it never
contradicts what the play has proven, and it is a probability distribution over the three seats.
"""

from __future__ import annotations

import random

import pytest

from krass_jass import native
from krass_jass.agent import DmctsAgent
from krass_jass.cards import card_list, parse_card
from krass_jass.game import Game, Phase
from krass_jass.rules import HOUSE, SIDI

pytestmark = pytest.mark.skipif(not native.AVAILABLE, reason="Rust core not built")
needs_view = pytest.mark.skipif(
    not hasattr(native._core, "rs_belief_marginals"), reason="Rust core predates the test mode"
)


def mid_round(cfg, seed: int, plays: int):
    agent = DmctsAgent(determinizations=4, iterations=40, cfg=cfg)
    game = Game(cfg=cfg, seed=seed)
    while game.phase is Phase.BIDDING:
        seat = game.to_act
        if cfg.sidi:
            game.bid(seat, agent.sidi_call(game.hand_of(seat), game.public_auction(), seat))
        else:
            game.bid(seat, agent.select_trump(game.hand_of(seat), seat == game.forehand))
    rng = random.Random(seed)
    for _ in range(plays):
        if game.phase is Phase.DOUBLING:
            game.double(game.to_act, False)
            continue
        if game.phase is Phase.WEIS:
            game.choose_weis(game.to_act, True)
            continue
        seat = game.round.to_play
        game.play(seat, rng.choice(card_list(game.round.legal_moves(seat))))
    return game, agent


@needs_view
@pytest.mark.parametrize("cfg, seed, plays", [(HOUSE, 5, 7), (HOUSE, 12, 18), (SIDI, 11, 5)])
def test_every_unseen_card_is_somewhere_and_no_seen_card_is_anywhere(cfg, seed, plays):
    game, agent = mid_round(cfg, seed, plays)
    for seat in range(4):
        obs = game.observation(seat)
        view = agent.beliefs(obs)
        listed = {entry["card"] for entry in view["cards"]}
        assert listed == set(card_list(obs.unseen)), "the view is exactly the unseen cards"
        assert not listed & set(card_list(obs.hand | obs.played))
        for entry in view["cards"]:
            assert sum(entry["seats"]) == pytest.approx(1.0, abs=1e-3)
            assert all(0.0 <= p <= 1.0 for p in entry["seats"])
        assert view["ess"] > 1


@needs_view
def test_the_view_never_contradicts_a_proven_void():
    """A seat that discarded on a led suit cannot hold it — the search filters those worlds, so
    the published belief has to be zero there, not merely small."""
    game, agent = mid_round(HOUSE, 12, 18)
    for seat in range(4):
        obs = game.observation(seat)
        forbidden, _ = agent._beliefs(obs)
        view = {e["card"]: e["seats"] for e in agent.beliefs(obs)["cards"]}
        proven = 0
        for rel in (1, 2, 3):
            other = (seat + rel) % 4
            for card in card_list(forbidden[other] & obs.unseen):
                assert view[card][rel - 1] == 0.0, "a world was drawn that the play ruled out"
                proven += 1
        if proven:
            return
    pytest.skip("no void was proven in this round")


@needs_view
def test_the_seats_are_reported_in_play_order_from_the_asking_seat():
    """Column one is the seat that plays next, then the partner, then the seat before — which is
    how the table is drawn. A card only one seat can hold pins that column."""
    game, agent = mid_round(HOUSE, 5, 7)
    obs = game.observation(0)
    view = {e["card"]: e["seats"] for e in agent.beliefs(obs)["cards"]}
    truth = {c: s for s in range(4) for c in card_list(game.round.hands[s])}
    best = {card: max(range(3), key=lambda i: p[i]) for card, p in view.items() if max(p) > 0.9}
    for card, column in best.items():
        assert truth[card] == (obs.seat + column + 1) % 4, "a near-certain card sat elsewhere"
