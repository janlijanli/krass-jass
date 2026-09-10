"""The game event log.

`docs/webapp-plan.md` §3: the engine emits one ordered, append-only stream per game, and
every client view is a fold over its own filtered slice of it. Reconnection, replay and the
M6 debug viewer all fall out of that rather than needing their own machinery.

**Filtering is per-event and explicit.** Exactly one event type carries hidden cards
(`HAND_DEALT`) and it is addressed to a single seat. Any new event carrying card identifiers
must set `private_to`, and `tests/test_events.py` fails if a public event ever contains a
card the other seats have not seen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    GAME_STARTED = "game_started"
    ROUND_STARTED = "round_started"
    HAND_DEALT = "hand_dealt"          #: private — the only event carrying hidden cards
    BID = "bid"
    CONTRACT_SET = "contract_set"
    WEIS_DECLARED = "weis_declared"
    CARD_PLAYED = "card_played"
    TRICK_WON = "trick_won"
    ROUND_SCORED = "round_scored"
    GAME_OVER = "game_over"


@dataclass(frozen=True)
class Event:
    seq: int
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    #: Seat this event is addressed to, or None for public. Public is the default because
    #: forgetting to mark something private should be loud, not silent — and it is: the
    #: leak test walks every public event looking for unseen cards.
    private_to: int | None = None

    def visible_to(self, seat: int) -> bool:
        return self.private_to is None or self.private_to == seat

    def as_dict(self) -> dict[str, Any]:
        return {"seq": self.seq, "type": self.type.value, **self.payload}


class EventLog:
    """Append-only. Nothing is ever mutated or removed."""

    def __init__(self) -> None:
        self._events: list[Event] = []

    def emit(self, type: EventType, payload: dict | None = None, private_to: int | None = None) -> Event:
        event = Event(len(self._events) + 1, type, payload or {}, private_to)
        self._events.append(event)
        return event

    def __len__(self) -> int:
        return len(self._events)

    def all(self) -> list[Event]:
        return list(self._events)

    def for_seat(self, seat: int, after: int = 0) -> list[Event]:
        """Events this seat may see, from `after` exclusive.

        `after` is what makes reconnection trivial: a client sends the last `seq` it
        received and gets exactly what it missed.
        """
        return [e for e in self._events if e.seq > after and e.visible_to(seat)]
