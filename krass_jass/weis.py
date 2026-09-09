"""Weis and Stöck.

The plan calls this the complexity bomb and it is right: it is the largest source of rule
bugs and of scoring variance, which is why ``EVAL`` turns it off entirely. Three things
here are genuinely disputed between sources and are therefore flags, not decisions:
``weis_large``, ``weis_four_nines`` and ``weis_four_beats_sequence``.

Sequence order is **always** A K Q J 10 9 8 7 6, regardless of contract — so J-10-9 of
trumps is a sequence and J-9-A is not. That is independent of the trump order used for
trick-taking, and conflating the two is the classic bug.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import product

from .cards import NUM_RANKS, NUM_SUITS, RANK_9, RANK_A, RANK_J, RANK_K, RANK_Q, RANK_T, bit
from .rules import RulesConfig
from .tables import STOECK_MASK

STOECK_POINTS = 20

_SEQUENCE_POINTS_SMALL = {3: 20, 4: 50}
_SEQUENCE_POINTS_LARGE = {3: 20, 4: 50, 5: 100, 6: 150, 7: 200, 8: 250, 9: 300}

#: Four of a kind. 8s, 7s and 6s are not a Weis.
_FOUR_POINTS = {RANK_J: 200, RANK_9: 150, RANK_A: 100, RANK_K: 100, RANK_Q: 100, RANK_T: 100}


class WeisKind(Enum):
    SEQUENCE = "sequence"
    FOUR = "four"


@dataclass(frozen=True)
class Weis:
    kind: WeisKind
    points: int
    cards: int          #: mask of the cards making it up
    length: int
    top_rank: int       #: strongest rank in the meld, in A-high order (0 = ace)
    suit: int           #: sequences only; -1 for four of a kind

    def sort_key(self, trump: int, four_beats_sequence: bool) -> tuple:
        """Ordering used to decide which team scores. Higher wins.

        Points first, then — per the rules text — a longer sequence beats a shorter one, a
        higher top card breaks that tie, and trump breaks it further. Equal-point clashes
        between a four of a kind and a sequence are the disputed case, hence the flag.
        """
        four_rank = (1 if self.kind is WeisKind.FOUR else 0) if four_beats_sequence else 0
        return (
            self.points,
            four_rank,
            self.length,
            NUM_RANKS - 1 - self.top_rank,   # higher top card wins
            1 if self.suit == trump else 0,
        )


def _sequence_points(length: int, cfg: RulesConfig) -> int:
    if cfg.weis_large:
        return _SEQUENCE_POINTS_LARGE[length]
    return _SEQUENCE_POINTS_SMALL.get(length, 100)   # small Weis caps 5+ at 100


def _runs(hand: int) -> list[tuple[int, int, int]]:
    """Maximal runs of 3+ as ``(suit, start_rank, length)``."""
    out = []
    for suit in range(NUM_SUITS):
        start = None
        for r in range(NUM_RANKS + 1):
            held = r < NUM_RANKS and hand & bit(suit * NUM_RANKS + r)
            if held:
                if start is None:
                    start = r
                continue
            if start is not None:
                if r - start >= 3:
                    out.append((suit, start, r - start))
                start = None
    return out


def _sequence(suit: int, start: int, length: int, cfg: RulesConfig) -> Weis:
    mask = sum(bit(suit * NUM_RANKS + k) for k in range(start, start + length))
    return Weis(WeisKind.SEQUENCE, _sequence_points(length, cfg), mask, length, start, suit)


def _sequences(hand: int, cfg: RulesConfig) -> list[Weis]:
    """The maximal run in each suit. What you would actually announce when nothing
    contends for the cards."""
    return [_sequence(s, start, length, cfg) for s, start, length in _runs(hand)]


def _fours(hand: int) -> list[Weis]:
    out: list[Weis] = []
    for rank, pts in _FOUR_POINTS.items():
        mask = sum(bit(s * NUM_RANKS + rank) for s in range(NUM_SUITS))
        if hand & mask == mask:
            out.append(Weis(WeisKind.FOUR, pts, mask, 4, rank, -1))
    return out


def find_weis(hand: int, cfg: RulesConfig, trump: int = -1) -> list[Weis]:
    """Every Weis in a hand, already resolved for card-sharing.

    Under **large** Weis a card may count in both a four of a kind and a sequence, so every
    meld stands. Under **small** Weis each card counts once, so we take the highest-scoring
    set of melds with disjoint cards. A nine-card hand yields a handful of melds at most, so
    brute force is both correct and instant — do not optimise this.
    """
    if not cfg.weis_enabled:
        return []

    melds = _sequences(hand, cfg)
    melds += [m for m in _fours(hand) if m.points and (m.top_rank != RANK_9 or cfg.weis_four_nines)]

    if cfg.weis_large:
        return melds

    # Small Weis: each card counts once, so a four of a kind and a sequence can contend for
    # the same card — and the best answer is sometimes a *shorter* sub-sequence that steps
    # out of the way. (A K Q J of diamonds plus four jacks scores 220 as four jacks + A K Q,
    # not 200 as four jacks alone.) So the candidates for each run are all its sub-runs of
    # 3+, with the constraint that one run yields at most one announced sequence — otherwise
    # a run of nine would "split" into a 4 and a 5 for 150 instead of 100.
    fours = [m for m in melds if m.kind is WeisKind.FOUR]
    groups: list[list[Weis | None]] = []
    for suit, start, length in _runs(hand):
        options: list[Weis | None] = [None]
        for sub_len in range(3, length + 1):
            for offset in range(length - sub_len + 1):
                options.append(_sequence(suit, start + offset, sub_len, cfg))
        groups.append(options)
    for four in fours:
        groups.append([None, four])

    best: list[Weis] = []
    best_key = None
    for combo in product(*groups) if groups else []:
        union = 0
        points = 0
        ok = True
        for m in combo:
            if m is None:
                continue
            if union & m.cards:
                ok = False
                break
            union |= m.cards
            points += m.points
        if not ok:
            continue
        chosen = [m for m in combo if m is not None]
        strengths = sorted(
            (m.sort_key(trump, cfg.weis_four_beats_sequence) for m in chosen), reverse=True
        )
        key = (points, strengths)
        if best_key is None or key > best_key:
            best_key, best = key, chosen
    return best


def best_weis(melds: list[Weis], trump: int, cfg: RulesConfig) -> Weis | None:
    if not melds:
        return None
    return max(melds, key=lambda m: m.sort_key(trump, cfg.weis_four_beats_sequence))


def score_weis(
    hands: list[int],
    trump: int,
    cfg: RulesConfig,
    forehand: int = 0,
) -> tuple[tuple[int, int], int]:
    """Weis points per team, and the seat holding the best Weis (-1 if none).

    **The team holding the single best Weis scores all of its Weis; the other team scores
    nothing.** Ties are broken by who plays first, counting round from ``forehand`` — the
    last tie-break in the rules text.
    """
    if not cfg.weis_enabled:
        return (0, 0), -1

    per_seat = [find_weis(h, cfg, trump) for h in hands]
    winner, winner_key = -1, None
    for i in range(4):
        seat = (forehand + i) % 4          # earlier to play wins ties
        best = best_weis(per_seat[seat], trump, cfg)
        if best is None:
            continue
        key = best.sort_key(trump, cfg.weis_four_beats_sequence)
        if winner_key is None or key > winner_key:
            winner, winner_key = seat, key

    if winner < 0:
        return (0, 0), -1

    team = winner & 1
    points = [0, 0]
    points[team] = sum(m.points for s in (team, team + 2) for m in per_seat[s])
    return (points[0], points[1]), winner


def score_stoeck(hands: list[int], trump: int, cfg: RulesConfig) -> tuple[int, int]:
    """King + Queen of trumps in one hand. Not a Weis, cannot be beaten.

    There is no Stöck in Obenabe or Undenufe — there is no trump suit to hold.
    """
    points = [0, 0]
    if not cfg.stoeck_enabled or trump < 0:
        return (0, 0)
    mask = STOECK_MASK[trump]
    for seat, hand in enumerate(hands):
        if hand & mask == mask:
            points[seat & 1] += STOECK_POINTS
    return (points[0], points[1])
