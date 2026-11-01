"""Rounds whose card order changes from trick to trick. Mirror of `rust/src/schedule.rs`.

The Coiffeur's extra rows (`docs/rules-config.md`, "Coiffeur — the extra rows") play some
tricks Obenabe, some Undenufe and some in a trump suit. A schedule is that, written out: the
contract in force for each of the nine tricks. Every card order in it is one of the six the
engine already has, so legal moves, trick winners and card values are the existing tables,
indexed per trick instead of per round.

**Counted as trick 1.** Every source that says how agrees (swissjass.ch, Fässler): the whole
round's card points are counted in the first trick's order. A Slalom begun Obenabe is counted
as an Obenabe; a 3×3 begun in hearts counts the hearts Puur 20 and Nell 14 wherever they fall.

An ordinary round has no schedule (`None`): one contract, nine times.

Wire names, which are also what a player chooses:

* ``SLALOM_OBENABE`` / ``SLALOM_UNDENUFE`` — alternate trick by trick, starting with that one.
* ``GUSCHTI_OBENABE`` — five tricks Obenabe, then four Undenufe; ``GUSCHTI_UNDENUFE`` the other
  way round. With `coiffeur_guschti_45` also ``GUSCHTI4_OBENABE`` / ``GUSCHTI4_UNDENUFE``: four
  first, then five.
* ``TRIO_HEARTS`` — 3×3: three blocks of three tricks. The chooser names the first block (any of
  the six contracts); whoever **leads trick 4** names the second, whoever **leads trick 7** the
  third. Over the three, at least one block is a trump suit and at least one is Obenabe or
  Undenufe; the suit may change from block to block (owner, 2026-10-31). Until a block is named
  its tricks are `None`.
* ``MISERE_OBENABE`` / ``MISERE_UNDENUFE`` — Misère: nine tricks in that contract, and the aim is
  to take as few points as possible. The choosing team writes the points the *opponents* took
  (owner, 2026-10-31) — so both teams play to avoid points.
"""

from __future__ import annotations

from dataclasses import dataclass

from .rules import Contract, RulesConfig
from .scoring import TRICKS_PER_ROUND

O, U = Contract.OBENABE, Contract.UNDENUFE

#: The extra rows, in sheet order after the eight (`krass_jass/coiffeur.py`).
EXTRA_ROWS = ("SLALOM", "GUSCHTI", "TRIO", "MISERE")
#: A 3×3's blocks start at these tricks; the leader of each names it.
TRIO_BLOCKS = (0, 3, 6)


@dataclass(frozen=True)
class Schedule:
    name: str
    #: The contract of each trick; `None` for a 3×3 block not yet named.
    tricks: tuple[Contract | None, ...]
    misere: bool = False

    @property
    def is_open(self) -> bool:
        return None in self.tricks

    @property
    def count(self) -> Contract:
        """The contract the round's card points are counted in: the first trick's."""
        return self.tricks[0]

    @property
    def row(self) -> str:
        """Which extra row this schedule belongs in."""
        return self.name.split("_")[0].rstrip("4")

    def at(self, trick: int) -> Contract:
        return self.tricks[min(trick, TRICKS_PER_ROUND - 1)]

    def __str__(self) -> str:
        return self.name


def _other(c: Contract) -> Contract:
    return U if c is O else O


def slalom(first: Contract) -> Schedule:
    tricks = tuple(first if i % 2 == 0 else _other(first) for i in range(TRICKS_PER_ROUND))
    return Schedule(f"SLALOM_{first.name}", tricks)


def guschti(first: Contract, n_first: int = 5) -> Schedule:
    tricks = (first,) * n_first + (_other(first),) * (TRICKS_PER_ROUND - n_first)
    prefix = "GUSCHTI" if n_first == 5 else "GUSCHTI4"
    return Schedule(f"{prefix}_{first.name}", tricks)


def trio(first: Contract) -> Schedule:
    return Schedule(f"TRIO_{first.name}", (first,) * 3 + (None,) * 6)


def misere(contract: Contract) -> Schedule:
    return Schedule(f"MISERE_{contract.name}", (contract,) * TRICKS_PER_ROUND, misere=True)


def block_options(tricks, at: int) -> list[Contract]:
    """What the leader of trick `at` may name for a 3×3's block, in contract order.

    Any contract — except that the three blocks must include a trump suit and Obenabe or
    Undenufe, so the third block is forced when the first two left one of them out.
    """
    if at not in TRIO_BLOCKS[1:] or tricks[at] is not None:
        return []
    if at == TRIO_BLOCKS[-1]:
        named = [tricks[b] for b in TRIO_BLOCKS[:-1]]
        if not any(c.is_trump for c in named):
            return [c for c in Contract if c.is_trump]
        if all(c.is_trump for c in named):
            return [O, U]
    return list(Contract)


def for_row(row: str, cfg: RulesConfig) -> list[Schedule]:
    """Every schedule a player may choose for an extra row, in a fixed order."""
    if row == "SLALOM":
        return [slalom(O), slalom(U)]
    if row == "GUSCHTI":
        out = [guschti(O), guschti(U)]
        if cfg.coiffeur_guschti_45:
            out += [guschti(O, 4), guschti(U, 4)]
        return out
    if row == "TRIO":
        return [trio(c) for c in Contract]
    if row == "MISERE":
        return [misere(O), misere(U)]
    raise ValueError(f"unknown row {row!r}")


def parse(name: str) -> Schedule:
    """The schedule a wire name stands for. Raises `ValueError` for anything else."""
    parts = name.strip().upper().split("_")
    try:
        if parts[0] == "SLALOM" and len(parts) == 2:
            first = Contract[parts[1]]
            if first in (O, U):
                return slalom(first)
        elif parts[0] in ("GUSCHTI", "GUSCHTI4") and len(parts) == 2:
            first = Contract[parts[1]]
            if first in (O, U):
                return guschti(first, 5 if parts[0] == "GUSCHTI" else 4)
        elif parts[0] == "TRIO" and len(parts) == 2:
            return trio(Contract[parts[1]])
        elif parts[0] == "MISERE" and len(parts) == 2:
            contract = Contract[parts[1]]
            if contract in (O, U):
                return misere(contract)
    except KeyError:
        pass
    raise ValueError(f"unknown schedule {name!r}")


def is_schedule_name(name: str) -> bool:
    return name.strip().upper().split("_")[0] in ("SLALOM", "GUSCHTI", "GUSCHTI4", "TRIO", "MISERE")
