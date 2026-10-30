"""The bot service.

A thin wrapper. All the thinking is in `krass_jass.agent`, which is a library precisely so
that self-play and the arena can import it and run it across a process pool instead of going
through HTTP (`CLAUDE.md`). Three containers exist to serve one game to a human, not millions
to a trainer.

Configured entirely by environment, so one image runs as all three replicas:
`AGENT_KIND`, `SEAT`, `TIME_BUDGET_MS`, `DETERMINIZATIONS`, `ITERATIONS`, `MODEL_VERSION`.

Stateless: observation in, move out, forget. There is no per-game state here to leak, and
nothing persists between requests.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException

from bot.models import (
    Health,
    PlayCardRequest,
    PlayCardResponse,
    SelectTrumpRequest,
    SelectTrumpResponse,
    SidiCallRequest,
    SidiCallResponse,
    SidiKnockResponse,
    SidiDoubleRequest,
    SidiDoubleResponse,
)
from krass_jass.agent import DmctsAgent, GreedyAgent, RandomAgent
from krass_jass.cards import format_card, parse_card, parse_hand
from krass_jass.observation import Observation
import copy

from krass_jass.rules import HOUSE, SIDI_EVAL, Contract

AGENT_VERSION = "0.1.0"

#: 153,600 iterations, matching `web/app.py` and the browser build. §3's saturation at 2,400
#: was measured on the voting search; on the shared tree the budget pays to 64x
#: (`docs/measurements.md` §3b). ~1.3 s a move natively since the tree policy went on (§5p),
#: which is why `TIME_BUDGET_MS` is 6 s rather than the 1.5 s it was when a move cost 150 ms.
DEFAULT_DETERMINIZATIONS = 40
DEFAULT_ITERATIONS = 3840


def build_agent():
    kind = os.environ.get("AGENT_KIND", "dmcts").lower()
    if kind == "random":
        return RandomAgent()
    if kind == "greedy":
        return GreedyAgent()
    if kind == "dmcts":
        return DmctsAgent(
            determinizations=int(os.environ.get("DETERMINIZATIONS", DEFAULT_DETERMINIZATIONS)),
            iterations=int(os.environ.get("ITERATIONS", DEFAULT_ITERATIONS)),
            cfg=HOUSE,
        )
    raise ValueError(f"unknown AGENT_KIND {kind!r}")


def create_app() -> FastAPI:
    app = FastAPI(title="krass-jass bot")
    # Configuration is read once, at startup. A stateless service that re-reads the
    # environment per request can answer differently for reasons nothing recorded.
    agent = build_agent()
    # The same agent with the Sidi's rules: every contract x1, no Weis. The game score is not
    # the bot's business (stateless), so a single hand's rules are all it needs.
    sidi_agent = copy.copy(agent)
    sidi_agent.cfg = SIDI_EVAL

    def for_mode(mode: str):
        return sidi_agent if mode == "sidi" else agent
    kind = os.environ.get("AGENT_KIND", "dmcts").lower()
    seat_env = os.environ.get("SEAT")
    model_version = os.environ.get("MODEL_VERSION") or None
    identity = Health(
        status="ok",
        agent_kind=kind,
        agent_version=AGENT_VERSION,
        model_version=model_version,
        seat=int(seat_env) if seat_env is not None else None,
    )

    @app.get("/health", response_model=Health)
    async def health() -> Health:
        return identity

    @app.post("/select_trump", response_model=SelectTrumpResponse)
    async def select_trump(request: SelectTrumpRequest) -> SelectTrumpResponse:
        hand = parse_hand(request.hand)
        action = agent.select_trump(hand, request.is_forehand)
        name = action.name if isinstance(action, Contract) else str(action)
        return SelectTrumpResponse(action=name)

    @app.post("/sidi_call", response_model=SidiCallResponse)
    async def sidi_call(request: SidiCallRequest) -> SidiCallResponse:
        auction = tuple((c.seat, c.call) for c in request.auction)
        call = sidi_agent.sidi_call(parse_hand(request.hand), auction, request.seat)
        return SidiCallResponse(call=call)

    @app.post("/sidi_knock", response_model=SidiKnockResponse)
    async def sidi_knock(request: SidiCallRequest) -> SidiKnockResponse:
        auction = tuple((c.seat, c.call) for c in request.auction)
        knock = sidi_agent.sidi_knock(parse_hand(request.hand), auction, request.seat)
        return SidiKnockResponse(knock=knock)

    @app.post("/sidi_double", response_model=SidiDoubleResponse)
    async def sidi_double(request: SidiDoubleRequest) -> SidiDoubleResponse:
        try:
            contract = Contract[request.contract.upper()]
        except KeyError:
            raise HTTPException(422, f"unknown contract {request.contract!r}") from None
        from krass_jass.sidi_bidding import double_after_lead

        return SidiDoubleResponse(
            double=double_after_lead(parse_hand(request.hand), contract, request.bid_value)
        )

    @app.post("/play_card", response_model=PlayCardResponse)
    async def play_card(request: PlayCardRequest) -> PlayCardResponse:
        try:
            contract = Contract[request.contract.upper()]
        except KeyError:
            raise HTTPException(422, f"unknown contract {request.contract!r}") from None

        legal = parse_hand(request.legal_moves)
        if not legal:
            raise HTTPException(422, "no legal moves supplied")

        observation = Observation(
            seat=request.seat,
            hand=parse_hand(request.hand),
            legal_moves=legal,
            contract=contract,
            declarer_seat=request.declarer_seat,
            trick=tuple(parse_card(c.card) for c in request.current_trick),
            trick_leader=request.trick_leader,
            tricks_played=tuple(
                (t.leader, tuple(parse_card(c) for c in t.cards)) for t in request.tricks_played
            ),
            scores=request.scores,
            time_budget_ms=request.time_budget_ms,
            decision_seed=request.decision_seed,
            auction=tuple((c.seat, c.call) for c in request.auction),
            bid_value=request.bid_value,
            doubled=request.doubled,
        )

        card = for_mode(request.mode).decide(observation)
        # Defence in depth. The engine re-validates every move regardless, but a bot that
        # returns an illegal card should fail here rather than get that far.
        if not legal & (1 << card):
            raise HTTPException(500, f"agent returned an illegal card {format_card(card)}")

        trace = None
        if request.trace and isinstance(agent, DmctsAgent):
            trace = {
                "candidates": [
                    {
                        "card": format_card(c),
                        "visits": visits,
                        "mean_score": round(score, 4),
                        "determinizations_selecting": selecting,
                    }
                    for c, visits, score, selecting in agent.trace(observation)
                ],
                "agent_version": AGENT_VERSION,
            }
        return PlayCardResponse(card=format_card(card), trace=trace)

    return app


app = create_app()
