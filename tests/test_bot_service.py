"""The bot service and its client.

The service itself is thin, so most of what is worth testing is the *failure* behaviour:
threat T4 says a hung or slow bot must not stall a game, and that promise is only real if
every failure path falls back rather than raising.
"""

import random
import threading
import time
from contextlib import contextmanager

import pytest

from krass_jass.agent import GreedyAgent
from krass_jass.cards import card_list, format_card, parse_card, parse_hand
from krass_jass.game import Game, Phase
from krass_jass.observation import build_observation
from krass_jass.rules import HOUSE, SHOVE, Contract
from krass_jass.state import RoundState
from web.botclient import RemoteAgent

pytest.importorskip("krass_jass_core", reason="Rust core not built")


def bot_app(**env):
    import os

    from bot.service import create_app

    old = {k: os.environ.get(k) for k in env}
    os.environ.update({k: str(v) for k, v in env.items()})
    try:
        return create_app()
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def serving(app):
    """Run an app on a real port.

    `RemoteAgent` uses a synchronous httpx client, which cannot drive an ASGI app in-process
    — and a socket is what production uses anyway, so this exercises the real path including
    connection handling and timeouts.
    """
    import socket

    import uvicorn

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.perf_counter() + 10
    while not server.started and time.perf_counter() < deadline:
        time.sleep(0.02)
    if not server.started:
        raise RuntimeError("bot service did not start")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@contextmanager
def agent_against(app, **kwargs):
    with serving(app) as url:
        agent = RemoteAgent(url=url, **kwargs)
        try:
            yield agent
        finally:
            agent.close()


def deal(rng):
    deck = list(range(36))
    rng.shuffle(deck)
    return [sum(1 << c for c in deck[i * 9 : (i + 1) * 9]) for i in range(4)]


# --- the happy path ---------------------------------------------------------


def test_health_reports_its_configuration():
    with agent_against(bot_app(AGENT_KIND="greedy", SEAT=2, MODEL_VERSION="policy-x")) as agent:
        body = agent.client().get("/health").json()
    assert body["status"] == "ok"
    assert body["agent_kind"] == "greedy"
    assert body["seat"] == 2
    assert body["model_version"] == "policy-x"


@pytest.mark.parametrize("kind", ["random", "greedy", "dmcts"])
def test_one_image_serves_every_agent_kind(kind):
    """`CLAUDE.md`: one image, three replicas, configured by env. Not three codebases."""
    rng = random.Random(3)
    state = RoundState(contract=Contract.HEARTS, hands=deal(rng), cfg=HOUSE)
    obs = build_observation(state, state.to_play, decision_seed=99)
    with agent_against(bot_app(AGENT_KIND=kind, DETERMINIZATIONS=4, ITERATIONS=8)) as agent:
        card = agent.decide(obs)
        assert obs.legal_moves & (1 << card)
        assert agent.failures == 0


def test_a_whole_round_plays_over_http():
    human = GreedyAgent()
    app = bot_app(AGENT_KIND="dmcts", DETERMINIZATIONS=6, ITERATIONS=12)

    with serving(app) as url:
        bots = {seat: RemoteAgent(url=url, seat=seat, label=f"bot-{seat}") for seat in (1, 2, 3)}
        game = Game(cfg=HOUSE.variant(weis_manual=False), seed=5)
        while game.phase is Phase.BIDDING:
            seat = game.to_act
            actor = bots.get(seat, human)
            game.bid(seat, actor.select_trump(game.hand_of(seat), seat == game.forehand))
        while game.phase is Phase.PLAYING:
            seat = game.round.to_play
            actor = bots.get(seat, human)
            game.play(seat, actor.decide(game.observation(seat)))
        failures = [b.failures for b in bots.values()]
        for b in bots.values():
            b.close()

    assert game.last_score is not None
    assert sum(game.last_score["trick_points"]) + sum(game.last_score["last_trick"]) == 157
    assert failures == [0, 0, 0]


def test_trump_selection_over_http():
    hand = parse_hand("HJ H9 HA HK H8 H7 SA D6 C6")
    with agent_against(bot_app(AGENT_KIND="greedy")) as agent:
        assert agent.select_trump(hand, is_forehand=True) is Contract.HEARTS


# --- threat T4: a bot must never stall the game -----------------------------


def _observation():
    rng = random.Random(11)
    state = RoundState(contract=Contract.SPADES, hands=deal(rng), cfg=HOUSE)
    return build_observation(state, state.to_play, decision_seed=1234)


def test_a_refused_connection_falls_back_to_a_legal_move():
    agent = RemoteAgent(url="http://127.0.0.1:9")  # discard port: nothing listens
    obs = _observation()
    card = agent.decide(obs)
    assert obs.legal_moves & (1 << card), "fallback must still be legal"
    assert agent.failures == 1


def test_a_timeout_falls_back_rather_than_hanging():
    import time

    from fastapi import FastAPI

    slow = FastAPI()

    @slow.post("/play_card")
    async def hang(payload: dict):
        time.sleep(5)
        return {"card": "DA"}

    obs = _observation()
    object.__setattr__(obs, "time_budget_ms", 50)
    with agent_against(slow) as agent:
        started = time.perf_counter()
        card = agent.decide(obs)
        elapsed = time.perf_counter() - started
    assert elapsed < 4.5, f"the client waited {elapsed:.1f}s on a hung bot"
    assert obs.legal_moves & (1 << card)
    assert agent.failures == 1


def test_an_illegal_card_is_refused_and_replaced():
    """Never trust a bot's move. The engine would reject it, but catching it here keeps the
    game moving instead of raising into the turn loop."""
    from fastapi import FastAPI

    liar = FastAPI()
    obs = _observation()
    illegal = card_list(obs.hand & ~obs.legal_moves) or card_list(~obs.hand & 0xFFFFFFFFF)

    @liar.post("/play_card")
    async def cheat(payload: dict):
        return {"card": format_card(illegal[0])}

    with agent_against(liar) as agent:
        card = agent.decide(obs)
    assert card != illegal[0]
    assert obs.legal_moves & (1 << card)
    assert agent.failures == 1


def test_a_malformed_answer_falls_back():
    from fastapi import FastAPI

    broken = FastAPI()

    @broken.post("/play_card")
    async def nonsense(payload: dict):
        return {"nope": True}

    obs = _observation()
    with agent_against(broken) as agent:
        card = agent.decide(obs)
    assert obs.legal_moves & (1 << card)
    assert agent.failures == 1


def test_fallbacks_are_deterministic_for_a_decision_seed():
    """Replay has to survive a bot failing, or a game that went wrong becomes unreproducible
    exactly when reproducing it matters."""
    obs = _observation()
    a = RemoteAgent(url="http://127.0.0.1:9").decide(obs)
    b = RemoteAgent(url="http://127.0.0.1:9").decide(obs)
    assert a == b


def test_failed_trump_selection_still_returns_a_contract():
    agent = RemoteAgent(url="http://127.0.0.1:9")
    action = agent.select_trump(parse_hand("HJ H9 HA HK H8 H7 SA D6 C6"), is_forehand=False)
    assert isinstance(action, Contract), "a partner who was shoved to must choose"
    assert agent.failures == 1


# --- the boundary -----------------------------------------------------------


def test_the_request_carries_no_hidden_cards():
    """The wire contract is the information boundary made concrete: own hand, engine-computed
    legal moves, public history. Nothing else."""
    from bot.models import PlayCardRequest

    fields = set(PlayCardRequest.model_fields)
    assert fields == {
        "hand", "legal_moves", "contract", "declarer_seat", "current_trick",
        "trick_leader", "tricks_played", "scores", "seat", "time_budget_ms",
        "decision_seed", "trace",
    }, "the bot request shape changed — is the new field public?"


def test_the_service_refuses_an_unknown_contract():
    with agent_against(bot_app(AGENT_KIND="greedy")) as agent:
        response = agent.client().post(
            "/play_card",
            json={
                "hand": ["DA"], "legal_moves": ["DA"], "contract": "TRUMPS",
                "declarer_seat": 0, "seat": 0,
            },
        )
    assert response.status_code == 422
