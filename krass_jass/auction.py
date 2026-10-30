"""The Sidi Barrani auction. Rules in `docs/rules-config.md`, "Sidi Barrani".

A pure state machine over calls, owned by `Game` in Sidi mode and mirrored in
`rust/src/auction.rs`. It knows nothing about cards: the hands never enter it, which is what
makes the whole auction public.

A call on the wire is a string: ``"PASS"``, ``"DOUBLE"``, or a contract name and a value,
``"HEARTS 100"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .rules import Contract, RulesConfig
from .state import IllegalMove

NUM_SEATS = 4
PASS = "PASS"
DOUBLE = "DOUBLE"


@dataclass(frozen=True)
class Call:
    kind: str                       #: "bid", "pass" or "double"
    contract: Contract | None = None
    value: int = 0

    def __str__(self) -> str:
        if self.kind == "bid":
            return f"{self.contract.name} {self.value}"
        return self.kind.upper()

    @staticmethod
    def parse(text: "Call | str") -> "Call":
        if isinstance(text, Call):
            return text
        words = str(text).strip().upper().split()
        if words == [PASS]:
            return Call("pass")
        if words == [DOUBLE]:
            return Call("double")
        if len(words) == 2 and words[1].isdigit():
            try:
                return Call("bid", Contract[words[0]], int(words[1]))
            except KeyError:
                pass
        raise IllegalMove(f"unknown call {text!r}")


def bid(contract: Contract, value: int) -> Call:
    return Call("bid", Contract(contract), value)


@dataclass
class Auction:
    opener: int
    cfg: RulesConfig
    calls: list[tuple[int, Call]] = field(default_factory=list)
    #: (seat, contract, value) of the standing bid
    high: tuple[int, Contract, int] | None = None
    doubled: bool = False
    #: passes in a row since the last bid (or since the start)
    passes: int = 0
    #: calls made in turn. A double may come out of turn (below), so the turn is counted apart
    #: from the list of calls.
    in_turn: int = 0

    @property
    def to_act(self) -> int | None:
        if self.done:
            return None
        return (self.opener + self.in_turn) % NUM_SEATS

    @property
    def done(self) -> bool:
        if self.doubled and self.cfg.sidi_double_ends_auction:
            return True
        if self.high is None:
            return self.passes >= NUM_SEATS
        return self.passes >= NUM_SEATS - 1 or self.high[2] >= self.cfg.sidi_bids[-1]

    @property
    def thrown_in(self) -> bool:
        """All four passed before anyone bid."""
        return self.done and self.high is None

    def may_double(self, seat: int) -> bool:
        return self.high is not None and not self.doubled and (seat - self.high[0]) % 2 == 1

    def legal_calls(self, seat: int) -> list[Call]:
        """Every call the seat may make now, lowest bid first."""
        if seat != self.to_act:
            return []
        floor = self.high[2] if self.high is not None else 0
        calls = [Call("pass")]
        if self.may_double(seat):
            calls.append(Call("double"))
        for value in self.cfg.sidi_bids:
            if value > floor:
                calls.extend(Call("bid", c, value) for c in Contract)
        return calls

    def call(self, seat: int, call: Call | str) -> Call:
        call = Call.parse(call)
        if self.done:
            raise IllegalMove("the auction is over")
        if seat != self.to_act:
            # A double may be called at any time (owner, 2026-09-19: "jederzeit, bis die zweite
            # Karte auf dem Tisch liegt") — at a table you knock the moment you hear the bid,
            # without waiting for the partner in between to speak. Nothing else is out of turn.
            if call.kind != "double":
                raise IllegalMove(f"seat {seat} is not on turn to call")
            if not self.may_double(seat):
                raise IllegalMove("only an opponent of the standing bid may double")
            self.doubled = True
            self.calls.append((seat, call))
            return call
        if call.kind == "pass":
            self.passes += 1
        elif call.kind == "double":
            if not self.may_double(seat):
                raise IllegalMove("only an opponent of the standing bid may double")
            self.doubled = True
        else:
            if call.value not in self.cfg.sidi_bids:
                raise IllegalMove(f"{call.value} is not on the bid ladder")
            if self.high is not None and call.value <= self.high[2]:
                raise IllegalMove(f"a bid must beat {self.high[2]}")
            self.high = (seat, call.contract, call.value)
            self.passes = 0
            # A double that did not end the auction was a double of the bid it named.
            self.doubled = False
        self.calls.append((seat, call))
        self.in_turn += 1
        return call


def bonus(value: int, doubled: bool) -> int:
    """What the bid is worth to whichever team it goes to."""
    return value * (2 if doubled else 1)
