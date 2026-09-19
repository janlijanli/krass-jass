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
from krass_jass.awareness import trick_taker
from krass_jass.cards import card_list, card_rank, card_suit, format_card, parse_card
from krass_jass.game import Game, Phase
from krass_jass.rules import DEFAULT_MULTIPLIERS, HOUSE, SIDI, Contract
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

#: 153,600 iterations, the budget the browser build ships. `docs/measurements.md` §3 put the
#: saturation point at 2,400, but that was measured on the voting search; on the shared tree
#: the budget keeps paying to 64x (§3b, +0.56 of a round's share). ~150 ms a move natively,
#: which `pace` absorbs rather than adds to.
BOT_DETERMINIZATIONS = 40
BOT_ITERATIONS = 3840

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
    #: Sidi: the last knock the player let pass, as (round, calls so far), so the question is
    #: asked once per opposing bid.
    knock_declined: tuple | None = None

    def is_bot(self, seat: int) -> bool:
        return seat != self.human_seat

    def knock_offer(self) -> dict | None:
        """Sidi: an opponent has just bid and the player may knock before anyone else speaks.

        A double may come at any time (`auction.py`), and at a table you knock the moment you
        hear the bid — not after your partner in between has spoken. So the bots wait while the
        player is asked. Not on the player's own turn: the bidding panel offers the double then.
        """
        game = self.game
        auction = game.auction
        if not game.cfg.sidi or game.phase is not Phase.BIDDING or auction is None or not auction.calls:
            return None
        seat, call = auction.calls[-1]
        key = (game.round_index, len(auction.calls))
        if (
            call.kind != "bid"
            or auction.to_act == self.human_seat
            or not auction.may_double(self.human_seat)
            or self.knock_declined == key
        ):
            return None
        return {"seat": seat, "call": str(call)}

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
    # Sidi Barrani is the default game (owner, 2026-09-19), played to 2000.
    sidi = settings.get("mode", "sidi") == "sidi"
    target = settings.get("target")
    target = target if target in TARGET_SCORES else (2000 if sidi else 1000)

    if sidi:
        # Sidi Barrani: its own scoring (every contract x1, no Weis, no Stöck) — the panel's
        # multipliers and Weis switch are Schieber settings and do not apply.
        return SIDI.variant(target_score=target)

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
                    "mode": cfg.mode,
                    "target": cfg.target_score,
                    # A Sidi game has no Weis and no multipliers; the form still offers the
                    # Schieber's, so it shows the Schieber's defaults rather than the Sidi's x1.
                    "weis": cfg.weis_enabled or cfg.sidi,
                    "multipliers": {
                        c.name.lower(): (DEFAULT_MULTIPLIERS[c] if cfg.sidi else cfg.multiplier(c))
                        for c in Contract
                    },
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
        target: int = Form(2000),
        mode: str = Form("sidi"),
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
                "mode": "sidi" if mode == "sidi" else "schieber",
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
    """Weis is available for the whole round; the client decides how long to show it.

    This used to close as soon as the first trick was acknowledged, which meant the winning
    Weis was only ever on screen during a pause the player taps straight through — so in
    practice it never appeared. What may be *seen* is unchanged: a losing hand's cards are
    still never exposed, only its called value.
    """
    return table.game.round is not None


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


#: Kreuz, Ecken, Schaufel, Herz, left to right: black and red alternate, so no two suits of one
#: colour sit side by side in the fan (the owner's order). Indexed by suit: D H S C.
HAND_SUIT_ORDER = (1, 3, 2, 0)


def sorted_hand(hand: int) -> list[int]:
    """Grouped by suit in `HAND_SUIT_ORDER`, ascending in rank left to right — 6 lowest, ace
    highest. Mirrored by `sorted_hand` in `rust/src/wasm_api.rs`.

    The internal rank index runs the other way (0 = ace), which is right for the engine and
    backwards for a player looking at their cards.
    """
    return sorted(card_list(hand), key=lambda c: (HAND_SUIT_ORDER[card_suit(c)], -card_rank(c)))


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

    # Which way the cards on the table are going, and how much trump is left to come. Both
    # public — see krass_jass/awareness.py.
    taker = None
    if game.round is not None and game.contract is not None:
        taker = trick_taker(shown, shown_leader, game.contract)

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
        # Who the cards on the table go to as it stands, and nothing else about the cards:
        # counting the points and the trump is the player's own work.
        "trick_taker": taker,
        # `is not None`: Contract.DIAMONDS == 0 is falsy
        "contract": game.contract.name if game.contract is not None else None,
        "multiplier": game.cfg.multiplier(game.contract) if game.contract is not None else None,
        # How many cards each seat still holds. Public — everyone at a real table watches a
        # fan shrink — and a count, never a hand. The information boundary is unmoved.
        "hand_sizes": (
            [bin(game.round.hands[s]).count("1") for s in range(4)]
            if game.round is not None
            else None
        ),
        "declarer": game.declarer,
        "scores": list(game.scores),
        "round": game.round_index,
        "can_shove": (
            game.phase is Phase.BIDDING
            and not game.cfg.sidi
            and seat == game.forehand
            and not game.shoved
        ),
        # Sidi Barrani. The auction is public — every call was said aloud — and the calls this
        # seat may make now are the engine's, as legal cards are: the client never decides.
        "mode": game.cfg.mode,
        "auction": [{"seat": s, "call": c} for s, c in game.public_auction()],
        "legal_calls": (
            [str(c) for c in game.auction.legal_calls(seat)]
            if game.auction is not None and game.phase is Phase.BIDDING and game.to_act == seat
            else []
        ),
        "bid": game.bid_value or None,
        "doubled": game.doubled,
        "double_pending": game.phase is Phase.DOUBLING and game.to_act == seat,
        "knock": table.knock_offer(),
        # The trump Jack decides most tricks it appears in; the engine names it so the client
        # does not have to work out what trump means.
        "puur": format_card(game.contract.trump_suit * 9 + 3)
        if game.contract is not None and game.contract.is_trump
        else None,
        "tricks_won": list(game.round.tricks_won) if game.round else [0, 0],
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
        # Not until the last trick has been acknowledged. The ninth trick is a trick like any
        # other and is worth seeing — who took it decides the five for the last one, and
        # often the round — so it stays on the table and the scorecard waits for the tap.
        "scorecard": game.last_score
        if game.phase in (Phase.ROUND_OVER, Phase.GAME_OVER) and not table.awaiting_ack()
        else None,
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
        elif kind == "double":
            if game.phase is Phase.DOUBLING:
                game.double(seat, bool(message.get("double")))
            elif table.knock_offer() is not None:
                if message.get("double"):
                    game.bid(seat, "DOUBLE")        # out of turn: allowed for a double
                else:
                    table.knock_declined = (game.round_index, len(game.auction.calls))
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
        while game.phase in (Phase.BIDDING, Phase.DOUBLING, Phase.WEIS, Phase.PLAYING):
            if table.awaiting_ack():
                return  # the player is still looking at the last trick
            if table.knock_offer() is not None:
                return  # the player is being asked whether to knock
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

    if game.phase is Phase.BIDDING and game.cfg.sidi:
        hand, auction = game.hand_of(actor), game.public_auction()
        started = loop.time()
        call = await loop.run_in_executor(None, bot.sidi_call, hand, auction, actor)
        await pace(2, loop.time() - started)
        try:
            game.bid(actor, call)
        except IllegalMove:
            game.bid(actor, "PASS")   # a bot's call is re-validated like its cards
        return

    if game.phase is Phase.DOUBLING:
        observation = game.observation(actor)
        answer = await loop.run_in_executor(None, bot.sidi_double, observation)
        await pace(2)
        game.double(actor, bool(answer))
        return

    if game.phase is Phase.BIDDING:
        hand = game.hand_of(actor)
        started = loop.time()
        action = await loop.run_in_executor(
            None, bot.select_trump, hand, actor == game.forehand
        )
        await pace(1, loop.time() - started)
        game.bid(actor, action)
        return

    observation = game.observation(actor)
    choices = len(observation.cards()) and observation.legal_moves.bit_count()
    started = loop.time()
    card = await loop.run_in_executor(None, bot.decide, observation)
    await pace(choices, loop.time() - started)
    game.play(actor, card)


async def pace(choices: int, spent: float = 0.0) -> None:
    """A forced card comes back fast; a real decision takes a moment.

    `spent` is the time the bot already took to answer. The pause absorbs it rather than
    being added to it, so a bigger search budget makes the bot stronger without making it
    feel slower.
    """
    if choices <= 1:
        delay = random.uniform(0.15, 0.3)
    else:
        span = min(1.0, (choices - 1) / 6)
        base = THINK_MIN_S + span * (THINK_MAX_S - THINK_MIN_S)
        delay = random.uniform(base * 0.75, base)
    await asyncio.sleep(max(0.0, delay - spent))


app = create_app()
