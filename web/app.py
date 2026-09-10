"""The web service.

`docs/webapp-plan.md` is the design; the parts that matter most here:

* **The engine is the only authority.** This module holds no game state of its own — it
  projects the engine's event log to clients and forwards their intents back. The browser
  gets a view, never a source of truth.
* **Clients send intents, not mutations.** Every action is re-validated against the engine's
  own `legal_moves`, and bound to the seat in the session cookie (threat T3).
* **Per-seat filtering goes through the event log's own `for_seat`.** There is no second
  filter here, because a second filter is a second place to be wrong and only one of them
  would be tested.

Games live in memory in a single process. That is fine for v1 and is the reason
`docs/webapp-plan.md` §2 suggests keeping web and engine together for now; moving to a store
is a deployment change, not a redesign.
"""

from __future__ import annotations

import asyncio
import random
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from krass_jass.agent import Agent, DmctsAgent
from krass_jass.cards import parse_card
from krass_jass.game import Game, Phase
from krass_jass.rules import HOUSE
from krass_jass.state import IllegalMove
from krass_jass.trick import NUM_SEATS
from web import session as sessions

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

#: The measured saturation point. `docs/measurements.md` §3: indistinguishable from 800,000
#: iterations, and single-digit milliseconds in the Rust core.
BOT_DETERMINIZATIONS = 40
BOT_ITERATIONS = 60

#: The search is now fast enough to answer instantly, which reads as a spreadsheet rather
#: than an opponent (`docs/webapp-plan.md` §5). Pace deliberately, and take longer over hard
#: decisions than easy ones — a human plays a forced card quickly too.
THINK_MIN_S = 0.55
THINK_MAX_S = 1.5


@dataclass
class Table:
    """One game plus the bots sitting at it."""

    game: Game
    human_seat: int = 0
    bots: dict[int, Agent] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def is_bot(self, seat: int) -> bool:
        return seat != self.human_seat


tables: dict[str, Table] = {}


def new_table(human_seat: int = 0) -> Table:
    game_id = secrets.token_urlsafe(9)
    game = Game(cfg=HOUSE.variant(target_score=1000), seed=secrets.randbits(48), game_id=game_id)
    bots = {
        seat: DmctsAgent(
            determinizations=BOT_DETERMINIZATIONS,
            iterations=BOT_ITERATIONS,
            cfg=game.cfg,
            label=f"bot-{seat}",
        )
        for seat in range(NUM_SEATS)
        if seat != human_seat
    }
    table = Table(game=game, human_seat=human_seat, bots=bots)
    tables[game_id] = table
    return table


def create_app() -> FastAPI:
    app = FastAPI(title="krass-jass")
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        data = sessions.decode(request.cookies.get(sessions.COOKIE_NAME))
        table = tables.get(data["game_id"]) if data else None
        if table is None:
            table = new_table()
            data = {"game_id": table.game.game_id, "seat": table.human_seat}

        response = templates.TemplateResponse(
            request, "table.html", {"seat": data["seat"], "game_id": data["game_id"]}
        )
        response.set_cookie(
            sessions.COOKIE_NAME,
            sessions.encode(data),
            httponly=True,
            samesite="strict",
            max_age=60 * 60 * 8,
        )
        return response

    @app.post("/new")
    async def new_game(request: Request):
        table = new_table()
        data = {"game_id": table.game.game_id, "seat": table.human_seat}
        response = HTMLResponse('<meta http-equiv="refresh" content="0; url=/">')
        response.set_cookie(
            sessions.COOKIE_NAME, sessions.encode(data), httponly=True, samesite="strict"
        )
        return response

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        await socket.accept()
        data = sessions.decode(socket.cookies.get(sessions.COOKIE_NAME))
        table = tables.get(data["game_id"]) if data else None
        if table is None:
            await socket.send_json({"type": "error", "message": "no game; reload"})
            await socket.close()
            return

        seat = data["seat"]
        cursor = 0

        async def flush() -> None:
            """Send this seat's new events. The only path from engine to client."""
            nonlocal cursor
            for event in table.game.log.for_seat(seat, after=cursor):
                await socket.send_json(event.as_dict())
                cursor = event.seq
            await socket.send_json(view(table, seat))

        try:
            await flush()
            await drive(table, seat, socket, flush)
            while True:
                message = await socket.receive_json()
                await handle(table, seat, message, socket)
                await flush()
                await drive(table, seat, socket, flush)
        except WebSocketDisconnect:
            return

    return app


def view(table: Table, seat: int) -> dict:
    """Derived state the client would otherwise have to recompute — including legal moves,
    so the UI never decides legality itself, it only displays what the engine decided."""
    game = table.game
    from krass_jass.cards import card_list, format_card

    hand = game.hand_of(seat)
    legal = 0
    if game.phase is Phase.PLAYING and game.round is not None and game.round.to_play == seat:
        legal = game.round.legal_moves(seat)

    trick = []
    if game.round is not None:
        for i, card in enumerate(game.round.trick):
            trick.append({"seat": (game.round.leader + i) % NUM_SEATS, "card": format_card(card)})

    return {
        "type": "view",
        "phase": game.phase.value,
        "seat": seat,
        "to_act": game.to_act,
        "hand": [format_card(c) for c in card_list(hand)],
        "legal": [format_card(c) for c in card_list(legal)],
        "trick": trick,
        # `is not None`: Contract.DIAMONDS == 0 is falsy
        "contract": game.contract.name if game.contract is not None else None,
        "declarer": game.declarer,
        "scores": list(game.scores),
        "round": game.round_index,
        "can_shove": game.phase is Phase.BIDDING and seat == game.forehand and not game.shoved,
        "tricks_won": list(game.round.tricks_won) if game.round else [0, 0],
    }


async def handle(table: Table, seat: int, message: dict, socket: WebSocket) -> None:
    """Apply one client intent. Everything is re-validated; nothing is trusted."""
    game = table.game
    kind = message.get("type")
    try:
        if kind == "bid":
            game.bid(seat, message.get("action", ""))
        elif kind == "play":
            game.play(seat, parse_card(str(message.get("card", ""))))
        elif kind == "next_round":
            if game.phase is Phase.ROUND_OVER:
                game.next_round()
        else:
            await socket.send_json({"type": "error", "message": f"unknown intent {kind!r}"})
    except (IllegalMove, ValueError) as exc:
        # Expected: a stale click, or a client that got ahead of the server.
        await socket.send_json({"type": "rejected", "message": str(exc)})


async def drive(table: Table, seat: int, socket: WebSocket, flush) -> None:
    """Let the bots act until it is the human's turn again."""
    game = table.game
    async with table.lock:
        while game.phase in (Phase.BIDDING, Phase.PLAYING):
            actor = game.to_act
            if actor is None or actor == seat:
                return
            await think(table, actor)
            await flush()


async def think(table: Table, actor: int) -> None:
    """One bot decision, paced so it reads as a player rather than a spreadsheet."""
    game = table.game
    bot = table.bots[actor]
    loop = asyncio.get_running_loop()

    if game.phase is Phase.BIDDING:
        hand = game.hand_of(actor)
        action = await loop.run_in_executor(
            None, bot.select_trump, hand, actor == game.forehand
        )
        await pace(1)
        game.bid(actor, action)
        return

    observation = game.observation(actor)
    choices = len(observation.cards()) and observation.legal_moves.bit_count()
    card = await loop.run_in_executor(None, bot.decide, observation)
    await pace(choices)
    game.play(actor, card)


async def pace(choices: int) -> None:
    """A forced card comes back fast; a real decision takes a moment."""
    if choices <= 1:
        await asyncio.sleep(random.uniform(0.15, 0.3))
        return
    span = min(1.0, (choices - 1) / 6)
    base = THINK_MIN_S + span * (THINK_MAX_S - THINK_MIN_S)
    await asyncio.sleep(random.uniform(base * 0.75, base))


app = create_app()
