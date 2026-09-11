"""What the bidding said about the hands behind it.

The loudest information in a round of Schieber arrives before a card is played, and the
search was throwing all of it away: a partner who announced Obenabe was dealt the same
imagined hand as one who shoved.

Measured over 40,000 hands put through `trump.select_trump`:

===========  =========  ====================  =========================
bid          frequency  aces (average 1.00)   cards in the chosen suit
===========  =========  ====================  =========================
Obenabe      2.8%       **2.66**              —
Undenufe     7.1%       **0.53**              —
Schieben     26.7%      0.72                  — (and a flat hand: 3.22
                                              longest against 3.63)
a suit       63.5%      ~1.10                 **3.7** (a random suit: 2.25)
===========  =========  ====================  =========================

Every one of those is a strong prior and, unlike a discard convention, it is *forced*:
everybody has to bid, so the signal is always there and it is there from the first card
rather than accumulating over tricks.

**Why this biases the deal instead of filtering it.** The exact thing to do is reject any
imagined world whose declarer would not have made that call — `select_trump` is the very
function the bots used, so running it backwards is not a convention, it is the decision rule.
It is also unaffordable: a random hand chooses Obenabe 2.8% of the time, so exactly the most
informative bid costs about thirty-six redraws per world. Measured before building, not
after.

So the bid becomes weights, in the machinery `reading.py` already uses: a per-suit pull and a
per-seat pull towards high or low cards. Bounded four-to-one either way and never zero — a
player who bids unusually costs the search sampling efficiency and nothing else, which is the
same safety property, and it matters more here because a human's bidding is their own.

What is deliberately *not* modelled: how good a hand had to be to shove rather than how bad,
the partner's forced choice after a shove being weaker evidence than a free one, and
Zurückschieben. Each is a refinement on a prior that has to prove itself first.
"""

from __future__ import annotations

from .rules import Contract, RulesConfig
from .trick import NUM_SEATS

#: Bounds, matching `reading.LIMIT` — the sampler reads both through the same weights.
LIMIT = 2

#: Pull towards the suit somebody chose as trump. They hold 3.7 of it against a random 2.25,
#: which is the largest single effect in the table above.
TRUMP_SUIT_PULL = 2

#: Pull towards high cards for Obenabe, away for Undenufe. Obenabe is the stronger read —
#: 2.66 aces against 1.00 — but it is also the rarer bid.
OBENABE_PULL = 2
UNDENUFE_PULL = -2

#: A shove is "nothing here": fewer aces than average, and no long suit. The hand is flat,
#: which is a statement about *ranks* the sampler can use and about *shape* it cannot.
SHOVE_PULL = -1


def infer_from_bid(
    forehand: int,
    declarer: int,
    contract: Contract,
    seat: int,
    cfg: RulesConfig | None = None,
) -> tuple[list[list[int]], list[int]]:
    """`(suit_affinity, rank_bias)` per seat, from who bid what.

    `seat` is the searching seat, whose own hand is known and therefore never guessed at.
    Positive rank bias means "likelier to hold high cards".
    """
    suits = [[0] * 4 for _ in range(NUM_SEATS)]
    ranks = [0] * NUM_SEATS

    # Forehand shoved: they had nothing worth calling, and their partner had to choose
    # whatever was least bad rather than something they liked.
    if declarer != forehand:
        if forehand != seat:
            ranks[forehand] = max(-LIMIT, ranks[forehand] + SHOVE_PULL)

    if declarer == seat:
        return suits, ranks

    # `is_trump`, not truthiness: Contract.DIAMONDS is 0 and therefore falsy, and a diamonds
    # call would otherwise be read as a no-trump one — pulling the declarer towards low cards
    # instead of towards diamonds.
    if contract.is_trump:
        suit = contract.trump_suit
        suits[declarer][suit] = min(LIMIT, suits[declarer][suit] + TRUMP_SUIT_PULL)
    elif contract is Contract.OBENABE:
        ranks[declarer] = min(LIMIT, ranks[declarer] + OBENABE_PULL)
    elif contract is Contract.UNDENUFE:
        ranks[declarer] = max(-LIMIT, ranks[declarer] + UNDENUFE_PULL)

    return suits, ranks


def merge(a: list[list[int]], b: list[list[int]]) -> list[list[int]]:
    """Combine two per-seat, per-suit priors, keeping each inside the sampler's bounds."""
    return [
        [max(-LIMIT, min(LIMIT, x + y)) for x, y in zip(rows_a, rows_b)]
        for rows_a, rows_b in zip(a, b)
    ]
