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
import os
import random
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from fastapi.templating import Jinja2Templates

from krass_jass.agent import Agent, DmctsAgent
from krass_jass.awareness import trick_points, trick_taker, trump_read
from krass_jass.cards import card_list, card_rank, card_suit, format_card, parse_card
from krass_jass.game import Game, Phase
from krass_jass.rules import DEFAULT_MULTIPLIERS, HOUSE, Contract
from krass_jass.state import IllegalMove
from krass_jass.trick import NUM_SEATS
from web import session as sessions
from web.botclient import RemoteAgent

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))


class RevalidatingStatic(StaticFiles):
    """Static files that must be revalidated rather than reused blindly.

    The default is a long cache lifetime, which means a browser can run new HTML against old
    CSS and JavaScript after a change. That fails in ways that look exactly like bugs in the
    code — it cost real time here twice before it was diagnosed. `no-cache` still allows a
    304, so the cost is a conditional request rather than a download.

    The static site solves the same problem differently, by hashing asset URLs, because a
    CDN is not going to revalidate on every request.
    """

    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response

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
    #: Tricks the player has acknowledged. A completed trick stays on the table until they
    #: tap, and the bots must not race ahead in the meantime — otherwise the board jumps
    #: forward the moment they do.
    acked_tricks: int = 0

    def is_bot(self, seat: int) -> bool:
        return seat != self.human_seat

    def completed_tricks(self) -> int:
        return len(self.game.round.tricks_played) if self.game.round else 0

    def awaiting_ack(self) -> bool:
        return self.completed_tricks() > self.acked_tricks


tables: dict[str, Table] = {}


#: What the settings panel may set. Everything else stays as `docs/rules-config.md` has it.
TARGET_SCORES = (1000, 2000, 2500)
MULTIPLIER_RANGE = (1, 2, 3, 4)


def build_config(settings: dict | None = None):
    """Turn settings from the panel into a RulesConfig.

    Values are clamped to the offered choices rather than trusted: this arrives from a form,
    and a rules engine driven by unvalidated client input is a rules engine with no rules.
    """
    settings = settings or {}
    target = settings.get("target")
    target = target if target in TARGET_SCORES else 1000

    multipliers = dict(DEFAULT_MULTIPLIERS)
    for contract in Contract:
        value = settings.get(f"mult_{contract.name.lower()}")
        if value in MULTIPLIER_RANGE:
            multipliers[contract] = value

    return HOUSE.variant(
        target_score=target,
        weis_enabled=bool(settings.get("weis", True)),
        # Manual Weis: declining is a real tactical choice, since announcing tells the table
        # what you hold. Stöck is never optional — it is announced when the second honour is
        # played, which gives nothing away that the card itself did not.
        weis_manual=True,
        multipliers=multipliers,
    )


#: Comma-separated bot service URLs. Unset means run the agents in-process, which is what
#: development and the tests do — the compose stack sets it.
BOT_URLS = [u.strip() for u in os.environ.get("KRASS_JASS_BOTS", "").split(",") if u.strip()]


def build_bots(human_seat: int, cfg) -> dict[int, Agent]:
    """Remote bots when configured, in-process otherwise.

    Both sides implement the same `Agent` interface, so nothing downstream changes.
    """
    seats = [s for s in range(NUM_SEATS) if s != human_seat]
    if BOT_URLS:
        return {
            seat: RemoteAgent(url=BOT_URLS[i % len(BOT_URLS)], seat=seat, label=f"bot-{seat}")
            for i, seat in enumerate(seats)
        }
    return {
        seat: DmctsAgent(
            determinizations=BOT_DETERMINIZATIONS,
            iterations=BOT_ITERATIONS,
            cfg=cfg,
            label=f"bot-{seat}",
        )
        for seat in seats
    }


def new_table(human_seat: int = 0, settings: dict | None = None) -> Table:
    game_id = secrets.token_urlsafe(9)
    game = Game(
        cfg=build_config(settings),
        seed=secrets.randbits(48),
        game_id=game_id,
    )
    bots = build_bots(human_seat, game.cfg)
    table = Table(game=game, human_seat=human_seat, bots=bots)
    tables[game_id] = table
    return table


def create_app() -> FastAPI:
    app = FastAPI(title="krass-jass")
    # docs/measurements.json is the single source for every number the app shows a reader.
    # Copied in at startup rather than duplicated, so the two cannot drift.
    source = HERE.parent / "docs/measurements.json"
    if source.exists():
        (HERE / "static/measurements.json").write_bytes(source.read_bytes())
    app.mount("/static", RevalidatingStatic(directory=str(HERE / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        data = sessions.decode(request.cookies.get(sessions.COOKIE_NAME))
        table = tables.get(data["game_id"]) if data else None
        if table is None:
            table = new_table()
            data = {"game_id": table.game.game_id, "seat": table.human_seat}

        cfg = table.game.cfg
        response = templates.TemplateResponse(
            request,
            "table.html",
            {
                "seat": data["seat"],
                "game_id": data["game_id"],
                "settings": {
                    "target": cfg.target_score,
                    "weis": cfg.weis_enabled,
                    "multipliers": {c.name.lower(): cfg.multiplier(c) for c in Contract},
                },
                "targets": TARGET_SCORES,
                "multiplier_range": MULTIPLIER_RANGE,
                "contracts": [(c.name, c.name.lower()) for c in Contract],
            },
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
    async def new_game(
        request: Request,
        target: int = Form(1000),
        weis: str = Form("on"),
        mult_diamonds: int = Form(1),
        mult_hearts: int = Form(2),
        mult_spades: int = Form(1),
        mult_clubs: int = Form(2),
        mult_obenabe: int = Form(3),
        mult_undenufe: int = Form(4),
    ):
        table = new_table(
            settings={
                "target": target,
                "weis": weis not in ("off", "false", "0", ""),
                "mult_diamonds": mult_diamonds,
                "mult_hearts": mult_hearts,
                "mult_spades": mult_spades,
                "mult_clubs": mult_clubs,
                "mult_obenabe": mult_obenabe,
                "mult_undenufe": mult_undenufe,
            }
        )
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


def in_weis_window(table: Table) -> bool:
    """Weis is on the table during the first trick, and during the pause after it."""
    game = table.game
    if game.round is None:
        return False
    played = len(game.round.tricks_played)
    return played == 0 or (played == 1 and table.awaiting_ack())


def visible_stoeck(table: Table) -> list[dict]:
    """Stöck announcements belonging to the trick currently on the table.

    Unlike Weis, this can happen in any trick — it fires when the second of King/Queen of
    trumps is played — so it gets its own window rather than riding on the first-trick one.
    """
    game = table.game
    if game.round is None:
        return []
    played = len(game.round.tricks_played)
    current = played - 1 if table.awaiting_ack() else played
    return [entry for entry in game.stoeck_seats if entry["trick"] == current]


def visible_weis(table: Table, seat: int) -> list[dict]:
    """What may be seen right now.

    Mirrors how it goes at the table. Each player calls the *value* of their Weis when their
    turn comes round in the first trick — not all at once when the contract is settled. Once
    everyone has called, the single best one is shown to prove it, and nobody else's cards
    are ever exposed.
    """
    game = table.game
    if not in_weis_window(table):
        return []

    if len(game.round.tricks_played) == 0:
        # Mid-first-trick: only the seats that have already played have spoken, and they
        # gave a number, not cards.
        spoken = {
            (game.round.leader + i) % NUM_SEATS for i in range(len(game.round.trick))
        }
        return [
            {**entry, "cards": None} for entry in game.weis_summary if entry["seat"] in spoken
        ]

    # First trick complete: everyone has called, so the best Weis shows its cards.
    return [
        entry if entry.get("best") else {**entry, "cards": None}
        for entry in game.weis_summary
    ]


def sorted_hand(hand: int) -> list[int]:
    """Grouped by suit, ascending in rank left to right — 6 lowest, ace highest.

    The internal rank index runs the other way (0 = ace), which is right for the engine and
    backwards for a player looking at their cards.
    """
    return sorted(card_list(hand), key=lambda c: (card_suit(c), -card_rank(c)))


def view(table: Table, seat: int) -> dict:
    """Derived state the client would otherwise have to recompute — including legal moves,
    so the UI never decides legality itself, it only displays what the engine decided."""
    game = table.game
    hand = game.hand_of(seat)
    legal = 0
    if (
        game.phase is Phase.PLAYING
        and game.round is not None
        and game.round.to_play == seat
        and not table.awaiting_ack()
    ):
        legal = game.round.legal_moves(seat)

    # While a finished trick is unacknowledged, keep showing *that* rather than the empty
    # new one. The client stays dumb: it renders whatever is in `trick`.
    trick = []
    winner = None
    shown: list[int] = []
    shown_leader = 0
    complete = table.awaiting_ack()
    if game.round is not None and complete:
        leader, cards = game.round.tricks_played[-1]
        for i, card in enumerate(cards):
            trick.append({"seat": (leader + i) % NUM_SEATS, "card": format_card(card)})
        winner = game.round.last_trick_winner
        shown, shown_leader = list(cards), leader
    elif game.round is not None:
        for i, card in enumerate(game.round.trick):
            trick.append({"seat": (game.round.leader + i) % NUM_SEATS, "card": format_card(card)})
        shown, shown_leader = list(game.round.trick), game.round.leader

    # Which way the cards on the table are going, and what the other three still hold in
    # trump. Public both ways — see krass_jass/awareness.py.
    taker = None
    at_stake = 0
    read = {"out": None, "voids": [None] * NUM_SEATS}
    if game.round is not None and game.contract is not None:
        taker = trick_taker(shown, shown_leader, game.contract)
        at_stake = trick_points(shown, game.contract)
        read = trump_read(
            game.round.tricks_played,
            game.round.trick,
            game.round.leader,
            seat,
            game.round.hands[seat],
            game.contract,
            game.cfg,
        )

    return {
        "type": "view",
        "phase": game.phase.value,
        "seat": seat,
        "to_act": game.to_act,
        "hand": [format_card(c) for c in sorted_hand(hand)],
        "legal": [format_card(c) for c in card_list(legal)],
        "trick": trick,
        "trick_complete": complete,
        "trick_winner": winner,
        # Who the cards on the table go to as it stands, and what they are worth.
        "trick_taker": taker,
        "trick_points": at_stake,
        "trumps_out": read["out"],
        "trump_voids": read["voids"],
        # `is not None`: Contract.DIAMONDS == 0 is falsy
        "contract": game.contract.name if game.contract is not None else None,
        "multiplier": game.cfg.multiplier(game.contract) if game.contract is not None else None,
        "declarer": game.declarer,
        "scores": list(game.scores),
        "round": game.round_index,
        "can_shove": game.phase is Phase.BIDDING and seat == game.forehand and not game.shoved,
        # The trump Jack decides most tricks it appears in; the engine names it so the client
        # does not have to work out what trump means.
        "puur": format_card(game.contract.trump_suit * 9 + 3)
        if game.contract is not None and game.contract.is_trump
        else None,
        "tricks_won": list(game.round.tricks_won) if game.round else [0, 0],
        # Card points taken so far. Public — every played card is face up, so anyone at the
        # table can count them, and a Jass player does.
        "round_points": list(game.round.trick_points) if game.round else [0, 0],
        "points_in_play": 157,
        "target": game.cfg.target_score,
        # Weis is public information the moment it is announced, so it belongs in the view
        # rather than being reconstructed by the client from the event stream. The losing
        # team's `cards` are already None by the time they get here.
        # Announced in turn order through the first trick, then the best one is shown and
        # the whole lot comes off the table. See `visible_weis`.
        "weis": visible_weis(table, seat),
        "stoeck": visible_stoeck(table),
        "weis_offer": game.weis_offers.get(seat) if game.phase is Phase.WEIS else None,
        "weis_pending": game.phase is Phase.WEIS,
        "scorecard": game.last_score if game.phase in (Phase.ROUND_OVER, Phase.GAME_OVER) else None,
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
        elif kind == "weis":
            game.choose_weis(seat, bool(message.get("announce")))
        elif kind == "ack_trick":
            table.acked_tricks = table.completed_tricks()
        elif kind == "next_round":
            if game.phase is Phase.ROUND_OVER:
                table.acked_tricks = 0
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
        while game.phase in (Phase.BIDDING, Phase.WEIS, Phase.PLAYING):
            if table.awaiting_ack():
                return  # the player is still looking at the last trick
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

    if game.phase is Phase.WEIS:
        # Bots always announce. Declining is a bluff, and a bot that cannot read the table
        # has no basis for one.
        await asyncio.sleep(random.uniform(0.2, 0.45))
        game.choose_weis(actor, True)
        return

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
