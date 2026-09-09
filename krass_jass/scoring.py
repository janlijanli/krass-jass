"""Round scoring.

Trick points, the last-trick bonus and the match bonus, all scaled by the contract
multiplier. Weis and Stöck are added by the caller (they are announced during play, not
derived from the tricks) and are scaled by the same multiplier.
"""

from __future__ import annotations

from dataclasses import dataclass

from .rules import Contract, RulesConfig

NUM_TEAMS = 2
TRICKS_PER_ROUND = 9


def team_of(seat: int) -> int:
    """Seats 0/2 are team 0, seats 1/3 are team 1."""
    return seat & 1


@dataclass(frozen=True)
class RoundScore:
    """Everything that went into one round's points, kept separate for the trace."""

    trick_points: tuple[int, int]
    last_trick: tuple[int, int]
    match: tuple[int, int]
    weis: tuple[int, int]
    stoeck: tuple[int, int]
    multiplier: int

    @property
    def total(self) -> tuple[int, int]:
        return tuple(
            (self.trick_points[t] + self.last_trick[t] + self.match[t] + self.weis[t] + self.stoeck[t])
            * self.multiplier
            for t in range(NUM_TEAMS)
        )


def score_round(
    trick_points: tuple[int, int],
    tricks_won: tuple[int, int],
    last_trick_winner: int,
    contract: Contract,
    cfg: RulesConfig,
    weis: tuple[int, int] = (0, 0),
    stoeck: tuple[int, int] = (0, 0),
) -> RoundScore:
    """Assemble one round's score.

    ``trick_points`` and ``tricks_won`` are per *team*; ``last_trick_winner`` is a seat.
    """
    last = [0, 0]
    last[team_of(last_trick_winner)] = cfg.last_trick_bonus

    match = [0, 0]
    if cfg.match_bonus:
        for t in range(NUM_TEAMS):
            if tricks_won[t] == TRICKS_PER_ROUND:
                match[t] = cfg.match_bonus

    return RoundScore(
        trick_points=tuple(trick_points),
        last_trick=tuple(last),
        match=tuple(match),
        weis=tuple(weis) if cfg.weis_enabled else (0, 0),
        stoeck=tuple(stoeck) if cfg.stoeck_enabled else (0, 0),
        multiplier=cfg.multiplier(contract),
    )
