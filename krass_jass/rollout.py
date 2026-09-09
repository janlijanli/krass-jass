"""The rollout kernel — the seam.

**This module is the one that gets replaced.** ``docs/plan-review.md`` §1 shows that M5
needs a teacher roughly 100× the serve budget, which pure Python cannot deliver; the
escalation path is Numba/Cython here, then a Rust core via PyO3. That swap is only cheap if
this file stays narrow, so the rules are:

* ints and tuples only — no dataclasses, no enums, no allocation in the loop;
* everything it needs arrives in a ``kernel`` tuple built once, outside the loop;
* it depends on :mod:`krass_jass.legal` and nothing else in the package.

It deliberately does *not* re-implement legal-move generation. One rule implementation,
one place to be wrong.
"""

from __future__ import annotations

from random import Random

from .cards import NUM_RANKS, card_suit
from .legal import legal_moves
from .rules import Contract, RulesConfig
from .scoring import TRICKS_PER_ROUND
from .tables import CARD_VALUES, STRENGTH
from .trick import NUM_SEATS

#: ``(trump, values, strength, strict_undertrump, puur_exempt, last_trick_bonus, match_bonus)``
Kernel = tuple


def make_kernel(contract: Contract, cfg: RulesConfig) -> Kernel:
    """Flatten a contract and config into the plain tuple the kernel reads.

    Build once per search, not once per rollout.
    """
    return (
        contract.trump_suit,
        CARD_VALUES[contract],
        STRENGTH[contract],
        cfg.strict_undertrump,
        cfg.puur_exempt_trump_lead,
        cfg.last_trick_bonus,
        cfg.match_bonus,
    )


def play_out(hands: list[int], leader: int, kernel: Kernel, rng: Random) -> tuple[int, int]:
    """Play out at random from ``leader`` until the hands are empty. Returns team points.

    Works from a partial position as well as from the deal — which is the whole point,
    since DMCTS rolls out from wherever the search currently is. **Precondition:** the
    position is at a trick boundary, so every hand holds the same number of cards. (Rolling
    out from mid-trick needs the cards already on the table; that arrives with the search
    in M4.)

    ``hands`` is consumed (the caller passes a copy). Points include the last-trick bonus,
    and the match bonus only when the playout covered a whole round — from a partial
    position the kernel cannot know who took the earlier tricks, so the caller owns it.
    Multiplier, Weis and Stöck are applied outside; here they would only scale the
    comparison.
    """
    trump, values, strength_by_led, strict, puur, last_bonus, match_bonus = kernel
    pts = [0, 0]
    tricks = [0, 0]
    randrange = rng.randrange
    tricks_to_play = hands[leader].bit_count()

    for _ in range(tricks_to_play):
        led = -1
        best_trump = -1
        strength = None
        trick_pts = 0
        best_seat = leader
        best_str = -1

        for i in range(NUM_SEATS):
            seat = (leader + i) & 3
            hand = hands[seat]
            legal = legal_moves(
                hand, trump, led, best_trump, strict_undertrump=strict, puur_exempt=puur
            )

            # Uniform pick over set bits, without materialising a list.
            n = legal.bit_count()
            m = legal
            for _ in range(randrange(n)):
                m &= m - 1
            low = m & -m
            c = low.bit_length() - 1

            hands[seat] = hand ^ low
            trick_pts += values[c]

            if i == 0:
                led = card_suit(c)
                strength = strength_by_led[led]
                best_str = strength[c]
            else:
                s = strength[c]
                if s > best_str:
                    best_str, best_seat = s, seat
            if trump >= 0 and c // NUM_RANKS == trump:
                ts = strength[c] - 100
                if ts > best_trump:
                    best_trump = ts

        team = best_seat & 1
        pts[team] += trick_pts
        tricks[team] += 1
        leader = best_seat

    if not tricks_to_play:
        return 0, 0
    pts[leader & 1] += last_bonus
    if match_bonus and tricks_to_play == TRICKS_PER_ROUND:
        for t in (0, 1):
            if tricks[t] == TRICKS_PER_ROUND:
                pts[t] += match_bonus
    return pts[0], pts[1]
