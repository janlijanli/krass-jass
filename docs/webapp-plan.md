# Web app plan

Status: plan only. Covers M2 (playable loop) and what M6 adds. Written to answer three
questions directly: who owns the state, who talks to whom, and whether the board and cards
are a separate thing.

---

## 1. The short answers

**Is there a separate instance for the board and the cards? No — and there must not be.**

There is exactly **one authority**: the engine. Everything else holds a *projection* of it.
Three representations exist, and only one of them is allowed to be right:

| Where | What it holds | Authoritative? |
|---|---|---|
| **engine** | `RoundState` — all four hands, trick, scores, the event log | **Yes. The only one.** |
| **web** | session ↔ seat binding, per-seat projections, presentation | No |
| **browser** | what this seat can see, plus animation state | No |

A separate "board service" would mean two things believe they know where the cards are, and
they will disagree. Every desync bug and every client-side cheat lives in that gap. The
board is not a service; it is a *view* of the engine, rebuilt from events.

The browser does own one thing outright: **animation state** — which card is mid-flight,
which is lifted under the player's thumb. That is presentation, it never round-trips, and
nothing depends on it.

**How do players communicate? They don't — not directly, by design.**

There is no channel between seats. Everything that looks like communication is a *public
game event* routed through the engine, which is what makes it safe:

- **The shove** (*Schieben*) — forehand passing the choice to their partner. Real
  information transfer, and the plan notes it is valuable precisely because it conveys
  something. It is a bid action, public to all four seats.
- **Weis announcements** — public by the rules.
- **Play itself** — schmieren, leading your strong suit, pulling trumps. This is the actual
  signalling channel in Jass, and it is nothing more than cards on the table.

Bots receive no side channel: no shared memory, no bot-to-bot network, internal-only
Docker network. A bot learns about its partner exactly the way a human does, by watching
what they play.

---

## 2. Topology

```
┌──────────┐  WebSocket   ┌──────────────┐  internal HTTP  ┌──────────────┐
│ browser  │◄────────────►│ web (FastAPI)│◄───────────────►│ engine       │
│ view +   │  events ↓    │ session,     │                 │ AUTHORITATIVE│
│ animation│  intents ↑   │ projection   │                 │ state+events │
└──────────┘              └──────────────┘                 └──────┬───────┘
                                                                  │ per-seat
                                                    observation only, REST
                                              ┌───────────┬───────┴───┐
                                          ┌───▼───┐   ┌───▼───┐   ┌───▼───┐
                                          │ bot-1 │   │ bot-2 │   │ bot-3 │
                                          └───────┘   └───────┘   └───────┘
                                          same image, stateless, no egress
```

Only `web` publishes a port.

**Should `web` and `engine` be one service for v1?** Probably yes. The split earns its keep
when there are multiple front ends or independent scaling, and today there is neither. Keep
them as separate *modules* with the boundary drawn properly so splitting later is a
deployment change, not a rewrite. The security boundary that actually matters is
engine↔bot, and that one is real from day one.

---

## 3. The event log is the design

The engine emits an ordered, append-only event stream per game:

```
seq  type          payload
1    round_started {round, dealer, forehand, seed_commitment}
2    hand_dealt    {seat, cards}          ← per-seat, never broadcast
3    bid           {seat, action: "SHOVE"}
4    bid           {seat, action: "HEARTS"}
5    weis          {seat, kind, points}
6    card_played   {seat, card}
7    trick_won     {seat, points}
...  round_scored  {trick_points, weis, stoeck, match, multiplier, totals}
```

Everything else falls out of this:

- **A client view is a fold over its own filtered stream.** No separate sync protocol.
- **Reconnection**: client sends the last `seq` it saw, server replays from there. This is
  the whole reconnection story, and it costs nothing extra.
- **Replay and the debug viewer** (M6) read the same log a client did.
- **Spectating and multi-human later** are additional filters, not a new architecture.

**Per-seat filtering goes through `build_observation`, not a second filter.** `hand_dealt`
is the only event carrying hidden cards, and it is addressed to one seat. If a new event
type carries card identifiers, it goes through the same boundary and the same fuzz test.
Two filtering paths means two places to be wrong, and only one of them will be tested.

---

## 4. Client → server: intents, never mutations

The client sends what it *wants*, never what happened:

```json
{"type": "play_card", "seq": 12, "card": "DJ"}
{"type": "bid", "action": "SHOVE"}
{"type": "announce_weis", "accept": true}
```

The server validates against `legal_moves`, binds the request to the session's seat, and
either emits an event or returns a rejection. The client cannot advance state, cannot play
for another seat, and cannot play an illegal card — threat T3, and the engine already
re-validates every move.

`seq` on the intent guards against acting on a stale view: a click sent against an old
state is rejected rather than applied to a new one.

---

## 5. Turn loop, and a problem the Rust core created

The web service drives the round:

```
loop:
  seat = engine.to_play
  if seat is human:  await intent (with a timeout → auto-play a legal card)
  else:              observation = engine.build_observation(seat)
                     move = bot[seat].play_card(observation, budget_ms)
  engine.play(move)                      # re-validated, always
  broadcast resulting events
```

Two things to get right:

**A hung bot must not stall the game** (T4). Hard `time_budget_ms`, a client-side timeout
on top, and a fallback to a random legal move. Never an unbounded await.

**Bots are now too fast.** The tuned search takes ~0.13s on this machine. A bot that answers
instantly, three times in a row, reads as a spreadsheet rather than an opponent — and
`PLAN.md` §9 already suspects a visible thinking delay improves perceived humanness. So
pace deliberately: a floor of roughly 0.6–1.2s per bot move, jittered, and *longer for
harder decisions* than easy ones. Note the search itself already returns instantly when
there is only one legal move — pacing should reflect that too, because a human also plays a
forced card quickly. This is a UX decision with no engineering cost, and it is invisible
until you play a round and it feels wrong.

---

## 6. Round state machine

```
DEALING → BIDDING ──shove──► BIDDING(partner) ─┐
             │                                 │
             └──contract chosen────────────────┴──► FIRST_TRICK (Weis window)
                                                          │
                                                          ▼
                                                     PLAYING ×9
                                                          │
                                                          ▼
                                    SCORING → next round, or GAME_OVER
```

Two decisions the UI forces, neither of them purely technical:

- **`allow_zurueckschieben`** is already a config flag, defaulted off. The UI only needs the
  second BIDDING state if it is ever turned on — build the state anyway, it is cheap.
- **Weis announcement: automatic or manual?** The engine can detect every Weis in a hand,
  so it *could* announce for the player. Usually that is what they want. But not always —
  announcing reveals your holding, and an experienced player sometimes declines. Suggest a
  flag, defaulting to automatic with a confirmation, and manual available. Worth deciding
  before building the first-trick UI, because it changes that screen.

---

## 7. The card fan is the hardest part, and it comes first

`PLAN.md` §5.1 is right that this constrains everything: nine cards on a 375px viewport,
overlapping and fanned, with tap-to-lift. Build it before any layout around it.

- **CSS Grid/flex plus transforms**, not a canvas. Cards stay real DOM nodes, so they are
  accessible, selectable and debuggable.
- **Overlap by negative margin**, rotate by index for the fan, lift on tap; the second tap
  plays. On desktop, hover lifts.
- **Illegal cards render dimmed and are not tappable** — `legal_moves` comes from the
  server, so the UI never has to *decide* legality, only display it. This is why the engine
  computing legal moves is a UX feature and not just a security one.
- **Animate with FLIP** (measure, move, invert, play) so card movement stays smooth without
  a framework.
- **`prefers-reduced-motion`** disables flight animations and cuts to end state.

Prototype it standalone against fixture data before the WebSocket exists.

---

## 8. Sessions

- Guest session, signed HTTP-only SameSite cookie, bound to a seat. No accounts.
- No accounts means no password surface and essentially no personal data — a design win the
  plan already identifies. Do not build auth that is not needed.
- Rate limit per session, cap concurrent games, cap message size (T8).

---

## 9. The decision that has to be made now

**Will there ever be more than one human?** `PLAN.md` §1.7 flags it and says decide before
M2, and this is M2.

It changes: session→seat binding (one seat per session vs a lobby), the turn loop (awaiting
several humans, with per-seat timeouts), reconnection semantics, and whether a game can
outlive a single connection.

The event-sourced design above absorbs most of it — additional humans are additional
filtered streams — so the cost of *keeping the door open* is low. The cost of assuming
single-human in the session layer and reversing later is not. Recommendation: build the
session layer seat-agnostic even while only one seat is human.

---

## 10. Sequencing

| | |
|---|---|
| **M2a** | Card fan prototype, fixture data, no server. Mobile first. |
| **M2b** | Engine module + event log + `build_observation` already exist; add the FastAPI shell and the WebSocket. |
| **M2c** | Bot containers, one image three replicas, internal network, timeouts and fallback. |
| **M2d** | Full round playable against random bots. Plumbing proven, nothing smart. |
| **M6** | Replay viewer over the same event log; search traces, post-round only (see `docs/documentation-plan.md` §8). |
