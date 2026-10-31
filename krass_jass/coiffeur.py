"""Coiffeur: the sheet, its multipliers, and who chooses. Mirror of `rust/src/coiffeur.rs`.

The trick-taking is the Schieber's. What changes is everything around it
(`docs/rules-config.md`, "Coiffeur"):

* Each team has a column of eight rows — the four suits, Obenabe, Undenufe and two Jokers —
  and must play every row exactly once. A Joker row takes any of the six contracts.
* Each row has a multiplier. By default they are dealt out at random, a permutation of 1..8
  drawn from the game seed, so the same seed gives the same sheet in both implementations.
* Forehand chooses or shoves — to the *next seat*, an opponent, not to the partner. After four
  shoves the choice is back with forehand, who must choose ("im Loch"). Once one team has
  filled its column only the other team chooses: it may shove to the partner and back, once.
* Whoever chooses leads. Only the choosing team's card points are written — in tens, rounded
  half up — times the row's multiplier. The game ends when both columns are full.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .deal import Rng
from .rules import SHOVE, Contract, RulesConfig
from .scoring import team_of
from .trick import NUM_SEATS

ROWS = 8
JOKER_ROWS = (6, 7)
ROW_NAMES = ("DIAMONDS", "HEARTS", "SPADES", "CLUBS", "OBENABE", "UNDENUFE", "JOKER1", "JOKER2")

#: The `Rng.split` index the multipliers are drawn from. Rounds use small indices; this one
#: never collides with a round's deal.
MULTIPLIER_STREAM = 0xC0FFE00000000001


def row_value(points: int, cfg: RulesConfig) -> int:
    """What a round's card points write into a row: tens, rounded half up, or in full."""
    return (points + 5) // 10 if cfg.coiffeur_tens else points


def multipliers(seed: int, cfg: RulesConfig) -> tuple[int, ...]:
    """The row multipliers for a game, in row order.

    Random by default: Fisher-Yates over 1..8, descending, index by Lemire multiply-shift — the
    deal's algorithm on its own stream, so Rust reproduces it exactly.
    """
    if not cfg.coiffeur_random_multipliers:
        return tuple(cfg.coiffeur_multipliers)
    rng = Rng.split(seed, MULTIPLIER_STREAM)
    out = list(range(1, ROWS + 1))
    for i in range(ROWS - 1, 0, -1):
        j = rng.below(i + 1)
        out[i], out[j] = out[j], out[i]
    return tuple(out)


@dataclass(frozen=True)
class Choice:
    """A contract, written into a row: its own, or a Joker."""

    contract: Contract
    row: int

    def __str__(self) -> str:
        if self.row == int(self.contract):
            return self.contract.name
        return f"{self.contract.name}/{ROW_NAMES[self.row]}"

    @staticmethod
    def parse(text: "Choice | str") -> "Choice":
        if isinstance(text, Choice):
            return text
        name, _, row = str(text).strip().upper().partition("/")
        try:
            contract = Contract[name]
        except KeyError:
            raise ValueError(f"unknown contract {name!r}") from None
        if not row:
            return Choice(contract, int(contract))
        if row not in ROW_NAMES[JOKER_ROWS[0]:]:
            raise ValueError(f"{row!r} is not a Joker row")
        return Choice(contract, ROW_NAMES.index(row))


@dataclass
class Sheet:
    """Card points written per team and row; `None` while the row is open."""

    written: list[list[int | None]] = field(
        default_factory=lambda: [[None] * ROWS for _ in range(2)]
    )

    def open_rows(self, team: int) -> list[int]:
        return [row for row in range(ROWS) if self.written[team][row] is None]

    def finished(self, team: int) -> bool:
        return not self.open_rows(team)

    @property
    def complete(self) -> bool:
        return self.finished(0) and self.finished(1)

    def choices(self, team: int) -> list[Choice]:
        """Every legal choice for the team, own rows first, then each Joker per contract."""
        open_rows = self.open_rows(team)
        out = [Choice(Contract(row), row) for row in open_rows if row < 6]
        for row in open_rows:
            if row in JOKER_ROWS:
                out.extend(Choice(c, row) for c in Contract)
        return out


def first_chooser(forehand: int, sheet: Sheet) -> int:
    """Forehand, unless its team is done: then the next seat of the team still choosing."""
    seat = forehand
    while sheet.finished(team_of(seat)):
        seat = (seat + 1) % NUM_SEATS
    return seat


def shove_step(sheet: Sheet) -> int:
    """To the next seat while both teams choose; to the partner once one team is done."""
    return 2 if sheet.finished(0) or sheet.finished(1) else 1


def max_shoves(sheet: Sheet) -> int:
    """Round the table and back to forehand; or to the partner and back."""
    return 2 if shove_step(sheet) == 2 else NUM_SEATS


@dataclass
class Choosing:
    """One round's choosing: who is on turn, and how often it has been shoved."""

    forehand: int
    sheet: Sheet
    chooser: int = -1
    shoves: int = 0

    def __post_init__(self) -> None:
        self.chooser = first_chooser(self.forehand, self.sheet)

    @property
    def may_shove(self) -> bool:
        return self.shoves < max_shoves(self.sheet)

    def legal(self) -> list:
        out: list = list(self.sheet.choices(team_of(self.chooser)))
        if self.may_shove:
            out.append(SHOVE)
        return out

    def act(self, seat: int, action) -> Choice | str:
        """Validate and apply. Returns the choice, or `SHOVE`."""
        if seat != self.chooser:
            raise ValueError(f"seat {seat} is not on turn to choose")
        if str(action).strip().upper() == SHOVE:
            if not self.may_shove:
                raise ValueError("must choose: shoving is exhausted")
            self.shoves += 1
            self.chooser = (seat + shove_step(self.sheet)) % NUM_SEATS
            return SHOVE
        choice = Choice.parse(action)
        if choice not in self.sheet.choices(team_of(seat)):
            raise ValueError(f"{choice} is not open for team {team_of(seat)}")
        return choice
