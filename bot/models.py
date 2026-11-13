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

from typing import Literal

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
    #: The bidding style of each seat ("count" / "feel"), public; empty means everyone counts.
    bid_styles: list[str] = []


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


class CoiffeurChoiceRequest(BaseModel):
    """Coiffeur: a row to fill, or a shove. The sheet is public; `legal` is the engine's."""

    hand: list[str]
    #: Wire form: "HEARTS", "OBENABE/CHANCE", "TUTTI", "SHOVE".
    legal: list[str]
    #: The row multipliers, one per sheet slot (`krass_jass.coiffeur.ROW_NAMES`), 0 for a row
    #: the game does not play.
    multipliers: list[int] = Field(min_length=12, max_length=12)
    seat: int = Field(ge=0, le=3)


class CoiffeurChoiceResponse(BaseModel):
    choice: str


class CoiffeurBlockRequest(BaseModel):
    """Coiffeur 3×3: this seat leads trick 4 or 7 and names the next block from `options`."""

    hand: list[str]
    options: list[str] = Field(min_length=1, max_length=6)
    seat: int = Field(ge=0, le=3)


class CoiffeurBlockResponse(BaseModel):
    contract: str


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
    #: "schieber", "sidi" or "coiffeur". The bot is stateless, so the game mode comes with every
    #: request.
    mode: str = "schieber"
    auction: list[AuctionCall] = []
    bid_styles: list[str] = []
    bid_value: int = 0
    doubled: bool = False
    #: Coiffeur's extra rows: the contract each of the nine tricks is played in, as contract
    #: indices; empty otherwise. `contract` is then the one the round is counted in.
    schedule: list[int] = Field(default_factory=list, max_length=9)
    #: Coiffeur Misère: each team is credited with what the other took.
    misere: bool = False
    #: The table's discard convention (`RulesConfig.discard_signal`), agreed before the first
    #: card and public, so it comes with every request like the mode.
    discard_signal: Literal["weakest", "sister"] = "weakest"


class PlayCardResponse(BaseModel):
    card: str
    trace: dict | None = None


class Health(BaseModel):
    status: str
    agent_kind: str
    agent_version: str
    model_version: str | None = None
    seat: int | None = None
