"""Coiffeur: the sheet, its multipliers, and who chooses. Mirror of `rust/src/coiffeur.rs`.

The trick-taking is the Schieber's. What changes is everything around it
(`docs/rules-config.md`, "Coiffeur"):

* Each team has a column of rows — the four suits, Obenabe, Undenufe and the Chance, plus the
  extra rows the game is played with (Tutti, Slalom, Guschti, 3×3, Misère;
  `krass_jass/schedule.py`) — and must play every row exactly once. The Chance takes any game:
  any of the six contracts or any extra row's (owner, 2026-11-01).
* Each row has a multiplier. The Chance's is fixed, ×13 (`coiffeur_chance_multiplier`); the
  others are by default dealt out at random, a permutation of 1..n over the n other rows, drawn
  from the game seed, so the same seed gives the same sheet in both implementations.
* Forehand chooses or shoves — to the *next seat*, an opponent, not to the partner. After four
  shoves the choice is back with forehand, who must choose ("im Loch"). Once one team has
  filled its column only the other team chooses: it may shove to the partner and back, once.
* Whoever chooses leads. Only the choosing team's card points are written — in tens, rounded
  half up — times the row's multiplier. The game ends when both columns are full.

**Rows have fixed slots**, whichever are played: 0–5 the contracts, 6 the Chance, 7–11 Tutti,
Slalom, Guschti, 3×3 and Misère. A row not in the game is never open and never written, so both implementations
index the sheet the same way whatever the configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .deal import Rng
from .rules import SHOVE, Contract, RulesConfig
from .schedule import EXTRA_ROWS, Schedule, for_row, is_schedule_name
from .schedule import parse as parse_schedule
from .scoring import team_of
from .trick import NUM_SEATS

CHANCE_ROW = 6
ROW_NAMES = (
    "DIAMONDS", "HEARTS", "SPADES", "CLUBS", "OBENABE", "UNDENUFE", "CHANCE",
    *EXTRA_ROWS,
)
#: The extra rows' slots, after the Chance.
EXTRA_SLOTS = tuple(range(CHANCE_ROW + 1, CHANCE_ROW + 1 + len(EXTRA_ROWS)))
#: Every slot on the sheet, played or not.
ALL_ROWS = len(ROW_NAMES)

#: The `Rng.split` index the multipliers are drawn from. Rounds use small indices; this one
#: never collides with a round's deal.
MULTIPLIER_STREAM = 0xC0FFE00000000001


def active_rows(cfg: RulesConfig) -> tuple[int, ...]:
    """The slots this game plays, in sheet order."""
    extra = tuple(ROW_NAMES.index(r) for r in EXTRA_ROWS if r in cfg.coiffeur_extra_rows)
    return tuple(range(CHANCE_ROW + 1)) + extra


def row_value(points: int, cfg: RulesConfig) -> int:
    """What a round's card points write into a row: tens, rounded half up, or in full."""
    return (points + 5) // 10 if cfg.coiffeur_tens else points


def multipliers(seed: int, cfg: RulesConfig) -> tuple[int, ...]:
    """The row multipliers for a game, one per slot; 0 for a row the game does not play.

    The Chance is always `coiffeur_chance_multiplier`. The other rows are random by default:
    Fisher-Yates over 1..n for the n of them played, descending, index by Lemire multiply-shift —
    the deal's algorithm on its own stream, so Rust reproduces it exactly.
    """
    rows = tuple(r for r in active_rows(cfg) if r != CHANCE_ROW)
    out = [0] * ALL_ROWS
    out[CHANCE_ROW] = cfg.coiffeur_chance_multiplier
    if not cfg.coiffeur_random_multipliers:
        for row in rows:
            out[row] = cfg.coiffeur_multipliers[row]
        return tuple(out)
    rng = Rng.split(seed, MULTIPLIER_STREAM)
    perm = list(range(1, len(rows) + 1))
    for i in range(len(rows) - 1, 0, -1):
        j = rng.below(i + 1)
        perm[i], perm[j] = perm[j], perm[i]
    for row, mult in zip(rows, perm):
        out[row] = mult
    return tuple(out)


@dataclass(frozen=True)
class Choice:
    """What is written where: a contract into its own row or the Chance, or an extra row's game
    (a `Schedule`) into that row — or, with `coiffeur_chance_takes_extra`, into the Chance.

    `contract` is the contract the round is *counted* in: for a schedule, its first trick's (a
    Tutti's is a placeholder until the first card, `schedule.TUTTI_PLACEHOLDER`).
    """

    contract: Contract
    row: int
    schedule: Schedule | None = None

    def __str__(self) -> str:
        own = self.schedule.name if self.schedule is not None else self.contract.name
        if self.row == CHANCE_ROW:
            return f"{own}/{ROW_NAMES[self.row]}"
        return own

    @staticmethod
    def parse(text: "Choice | str") -> "Choice":
        if isinstance(text, Choice):
            return text
        name, _, row = str(text).strip().upper().partition("/")
        if row and row != ROW_NAMES[CHANCE_ROW]:
            raise ValueError(f"{row!r} is not the Chance row")
        joker = CHANCE_ROW if row else None
        if is_schedule_name(name):
            schedule = parse_schedule(name)
            own = ROW_NAMES.index(schedule.row)
            return Choice(schedule.count, own if joker is None else joker, schedule)
        try:
            contract = Contract[name]
        except KeyError:
            raise ValueError(f"unknown contract {name!r}") from None
        return Choice(contract, int(contract) if joker is None else joker)


@dataclass
class Sheet:
    """Points written per team and row slot; `None` while the row is open. Only the slots in
    `rows` are played."""

    rows: tuple[int, ...] = tuple(range(CHANCE_ROW + 1))
    written: list[list[int | None]] = field(
        default_factory=lambda: [[None] * ALL_ROWS for _ in range(2)]
    )
    #: Match strokes per team, the sheet's own category (`coiffeur_match_stroke`).
    strokes: list[int] = field(default_factory=lambda: [0, 0])

    @staticmethod
    def for_game(cfg: RulesConfig) -> "Sheet":
        return Sheet(rows=active_rows(cfg))

    def open_rows(self, team: int) -> list[int]:
        return [row for row in self.rows if self.written[team][row] is None]

    def finished(self, team: int) -> bool:
        return not self.open_rows(team)

    @property
    def complete(self) -> bool:
        return self.finished(0) and self.finished(1)

    def choices(self, team: int, cfg: RulesConfig | None = None) -> list[Choice]:
        """Every legal choice for the team, in a fixed order: own rows first (the contracts,
        then each extra row's games), then the Chance — per contract, then per extra game when
        the Chance may take one."""
        cfg = _cfg(cfg)
        open_rows = self.open_rows(team)
        out = [Choice(Contract(row), row) for row in open_rows if row < 6]
        for row in open_rows:
            if row in EXTRA_SLOTS:
                out.extend(Choice(s.count, row, s) for s in for_row(ROW_NAMES[row], cfg))
        if CHANCE_ROW in open_rows:
            out.extend(Choice(c, CHANCE_ROW) for c in Contract)
            if cfg.coiffeur_chance_takes_extra:
                for extra in self.rows:
                    if extra in EXTRA_SLOTS:
                        out.extend(
                            Choice(s.count, CHANCE_ROW, s) for s in for_row(ROW_NAMES[extra], cfg)
                        )
        return out


def _cfg(cfg: RulesConfig | None) -> RulesConfig:
    if cfg is None:
        from .rules import COIFFEUR

        return COIFFEUR
    return cfg


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
    cfg: RulesConfig | None = None
    chooser: int = -1
    shoves: int = 0
    #: The game's first round under `ecken_ten_muss`: the Ecken 10 must choose.
    muss: bool = False

    def __post_init__(self) -> None:
        self.chooser = first_chooser(self.forehand, self.sheet)

    @property
    def may_shove(self) -> bool:
        return not self.muss and self.shoves < max_shoves(self.sheet)

    def legal(self) -> list:
        out: list = list(self.sheet.choices(team_of(self.chooser), self.cfg))
        if self.may_shove:
            out.append(SHOVE)
        return out

    def act(self, seat: int, action) -> Choice | str:
        """Validate and apply. Returns the choice, or `SHOVE`."""
        if seat != self.chooser:
            raise ValueError(f"seat {seat} is not on turn to choose")
        if str(action).strip().upper() == SHOVE:
            if self.muss:
                raise ValueError("Müessi: the Ecken 10 must choose in the first round")
            if not self.may_shove:
                raise ValueError("must choose: shoving is exhausted")
            self.shoves += 1
            self.chooser = (seat + shove_step(self.sheet)) % NUM_SEATS
            return SHOVE
        choice = Choice.parse(action)
        if choice not in self.sheet.choices(team_of(seat), self.cfg):
            raise ValueError(f"{choice} is not open for team {team_of(seat)}")
        return choice
