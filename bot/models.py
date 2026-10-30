"""The wire contract between engine and bots.

`CLAUDE.md`: Pydantic models are the contract. Everything crosses as card *codes* rather
than bitmasks — the mask encoding is an engine implementation detail, and a third-party bot
should be able to speak this without reimplementing it (`PLAN.md` §5.2 suggests mirroring
the HSLU/Zühlke interface so external bots can be dropped in for benchmarking).

**Note what is absent.** No other player's hand, no deck order, no game seed, no full-state
object. `decision_seed` is derived per decision and reveals nothing hidden; it exists so a
game replays bit-for-bit even though the bots roll their own dice.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TrickCard(BaseModel):
    seat: int = Field(ge=0, le=3)
    card: str


class PlayedTrick(BaseModel):
    leader: int = Field(ge=0, le=3)
    cards: list[str]


class SelectTrumpRequest(BaseModel):
    hand: list[str]
    is_forehand: bool
    seat: int = Field(ge=0, le=3)
    scores: tuple[int, int] = (0, 0)
    decision_seed: int = 0
    trace: bool = False


class SelectTrumpResponse(BaseModel):
    action: str
    trace: dict | None = None


class AuctionCall(BaseModel):
    seat: int = Field(ge=0, le=3)
    #: "PASS", "DOUBLE" or "HEARTS 100" — public, said aloud at the table.
    call: str


class SidiCallRequest(BaseModel):
    """Sidi Barrani: one call in the auction."""

    hand: list[str]
    auction: list[AuctionCall] = []
    seat: int = Field(ge=0, le=3)


class SidiCallResponse(BaseModel):
    call: str


class SidiKnockResponse(BaseModel):
    """Sidi Barrani: double the standing bid without waiting for this seat's turn?"""

    knock: bool


class SidiDoubleRequest(BaseModel):
    """Sidi Barrani: the question after the lead."""

    hand: list[str]
    contract: str
    bid_value: int
    seat: int = Field(ge=0, le=3)


class SidiDoubleResponse(BaseModel):
    double: bool


class PlayCardRequest(BaseModel):
    hand: list[str]
    #: Engine-computed and authoritative. A bot does not decide what is legal.
    legal_moves: list[str]
    contract: str
    declarer_seat: int = Field(ge=0, le=3)
    current_trick: list[TrickCard] = []
    trick_leader: int = Field(default=0, ge=0, le=3)
    tricks_played: list[PlayedTrick] = []
    scores: tuple[int, int] = (0, 0)
    seat: int = Field(ge=0, le=3)
    time_budget_ms: int = 1500
    decision_seed: int = 0
    trace: bool = False
    #: "schieber" or "sidi". The bot is stateless, so the game mode comes with every request.
    mode: str = "schieber"
    auction: list[AuctionCall] = []
    bid_value: int = 0
    doubled: bool = False


class PlayCardResponse(BaseModel):
    card: str
    trace: dict | None = None


class Health(BaseModel):
    status: str
    agent_kind: str
    agent_version: str
    model_version: str | None = None
    seat: int | None = None
