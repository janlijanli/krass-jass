"""A naive reference implementation, written from the rules text alone.

This exists to disagree with the engine. It is written from ``docs/rules-config.md`` in the
most literal way possible — strings, lists, linear scans, no bit tricks and **no imports
from** :mod:`krass_jass`. If it shared code with the engine it would confirm the engine's
bugs instead of finding them, which is the entire point of property-testing rules code.

Slow on purpose. Only tests call it.
"""

from __future__ import annotations

SUITS = "DHSC"
RANKS = "AKQJT9876"

#: strongest first
PLAIN_ORDER = "AKQJT9876"
TRUMP_ORDER = "J9AKQT876"
UNDENUFE_ORDER = "6789TJQKA"

VALUES_PLAIN = {"A": 11, "K": 4, "Q": 3, "J": 2, "T": 10, "9": 0, "8": 0, "7": 0, "6": 0}
VALUES_TRUMP = {"A": 11, "K": 4, "Q": 3, "J": 20, "T": 10, "9": 14, "8": 0, "7": 0, "6": 0}
VALUES_OBENABE = {"A": 11, "K": 4, "Q": 3, "J": 2, "T": 10, "9": 0, "8": 8, "7": 0, "6": 0}
VALUES_UNDENUFE = {"A": 0, "K": 4, "Q": 3, "J": 2, "T": 10, "9": 0, "8": 8, "7": 0, "6": 11}

DECK = [s + r for s in SUITS for r in RANKS]


def card_value(card: str, contract: str) -> int:
    suit, rank = card[0], card[1]
    if contract == "OBENABE":
        return VALUES_OBENABE[rank]
    if contract == "UNDENUFE":
        return VALUES_UNDENUFE[rank]
    return (VALUES_TRUMP if suit == contract else VALUES_PLAIN)[rank]


def legal(
    hand: list[str],
    contract: str,
    trick: list[str],
    *,
    strict_undertrump: bool = True,
    puur_exempt: bool = True,
) -> set[str]:
    """Legal cards, straight from the prose. ``contract`` is a suit letter, ``"OBENABE"``
    or ``"UNDENUFE"``."""
    if not trick:
        return set(hand)  # any card may be led

    led = trick[0][0]

    if contract in ("OBENABE", "UNDENUFE"):
        # ordinary follow-suit, no trumping
        follow = [c for c in hand if c[0] == led]
        return set(follow) if follow else set(hand)

    trump = contract
    trumps = [c for c in hand if c[0] == trump]

    if led == trump:
        # must follow with a trump, unless the Puur is your only one
        if not trumps:
            return set(hand)
        if puur_exempt and set(trumps) == {trump + "J"}:
            return set(hand)
        return set(trumps)

    # non-trump led: follow, or trump, subject to undertrumping
    allowed_trumps = list(trumps)
    played_trumps = [c for c in trick if c[0] == trump]
    if strict_undertrump and played_trumps and set(trumps) != set(hand):
        # lower index in TRUMP_ORDER == stronger
        best = min(TRUMP_ORDER.index(c[1]) for c in played_trumps)
        allowed_trumps = [c for c in trumps if TRUMP_ORDER.index(c[1]) < best]

    follow = [c for c in hand if c[0] == led]
    if follow:
        return set(follow) | set(allowed_trumps)
    return {c for c in hand if c[0] != trump} | set(allowed_trumps)


def winner_index(trick: list[str], contract: str) -> int:
    """Index within ``trick`` of the winning card."""
    led = trick[0][0]
    order = UNDENUFE_ORDER if contract == "UNDENUFE" else PLAIN_ORDER
    trump = contract if contract not in ("OBENABE", "UNDENUFE") else None

    def key(card: str) -> tuple[int, int]:
        suit, rank = card[0], card[1]
        if trump and suit == trump:
            return (2, -TRUMP_ORDER.index(rank))
        if suit == led:
            return (1, -order.index(rank))
        return (0, 0)

    best = 0
    for i in range(1, len(trick)):
        if key(trick[i]) > key(trick[best]):
            best = i
    return best


# --- Weis ------------------------------------------------------------------

FOUR_POINTS = {"J": 200, "9": 150, "A": 100, "K": 100, "Q": 100, "T": 100}


def all_melds(hand: list[str], *, large: bool, four_nines: bool) -> list[tuple[int, frozenset[str]]]:
    """Every meld that literally exists in the hand, as ``(points, cards)``.

    Under small Weis this includes every *sub*-sequence of 3+, because a shorter sequence
    is a legal announcement when a four of a kind wants one of its cards. Under large Weis
    only the maximal run of each suit is worth announcing.
    """
    melds: list[tuple[int, frozenset[str]]] = []
    for suit in SUITS:
        held = [r for r in RANKS if suit + r in hand]
        idx = sorted(RANKS.index(r) for r in held)
        runs = []
        start = 0
        for i in range(1, len(idx) + 1):
            if i == len(idx) or idx[i] != idx[i - 1] + 1:
                if i - start >= 3:
                    runs.append(idx[start:i])
                start = i
        for run in runs:
            spans = [run] if large else [
                run[o : o + n] for n in range(3, len(run) + 1) for o in range(len(run) - n + 1)
            ]
            for span in spans:
                n = len(span)
                pts = {3: 20, 4: 50}.get(n, 100)
                if large:
                    pts = {3: 20, 4: 50, 5: 100, 6: 150, 7: 200, 8: 250, 9: 300}[n]
                melds.append((pts, frozenset(suit + RANKS[i] for i in span)))

    for rank, pts in FOUR_POINTS.items():
        if rank == "9" and not four_nines:
            continue
        cards = frozenset(s + rank for s in SUITS)
        if cards <= set(hand):
            melds.append((pts, cards))
    return melds


def best_weis_total(hand: list[str], *, large: bool, four_nines: bool) -> int:
    """Highest total a hand can announce. Brute force over subsets — slow, obviously
    correct, and independent of how the engine gets there."""
    melds = all_melds(hand, large=large, four_nines=four_nines)
    if large:
        # cards may be shared between a four of a kind and a sequence, and the maximal runs
        # are already disjoint from each other, so everything counts
        return sum(p for p, _ in melds)

    best = 0

    def search(i: int, used: frozenset[str], total: int) -> None:
        nonlocal best
        if total > best:
            best = total
        if i == len(melds):
            return
        for j in range(i, len(melds)):
            pts, cards = melds[j]
            if not (cards & used):
                search(j + 1, used | cards, total + pts)

    search(0, frozenset(), 0)
    return best
