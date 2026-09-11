"""Reading the table: what a seat's discards suggest about the suits it holds.

`voids.py` is the *proof* side of the same question — a player who failed to follow suit
provably holds none of it, and that hard fact constrains which worlds the search may imagine
at all. This is the **soft** side, and the distinction matters more than it looks:

- A void is a fact. It removes worlds.
- A signal is a suggestion. It may only make worlds *likelier*, never impossible.

That is not fastidiousness. The convention here is the one `convention.py` plays: when a seat
cannot follow and is not trumping, the card it throws is the sister of the suit it wants led
(``♦/♥`` and ``♠/♣`` are the colour pairs). Our own bots always play it, so reading it back at
them is exact. A human at the table may play it, may play the plainer "throw your weakest
suit", or may have thrown the only card they could spare. Turning any of those into a hard
constraint would have the bot searching worlds that cannot exist — the precise failure
`voids.py` exists to prevent — so the output of this module is a *weight*, bounded away from
zero at both ends, and the sampler stays able to deal any legal world.

The output is per seat, per suit: positive means "likelier to be long here", negative means
"likelier to be short". Suit-level rather than card-level on purpose — length is what the
signal is about, and a rank-level prior is a second question with a second measurement
attached to it.

`determinize.rs` turns these into sampling weights. `docs/measurements.md` carries what it
is worth.
"""

from __future__ import annotations

from .cards import card_suit
from .rules import Contract, RulesConfig
from .trick import NUM_SEATS

#: How far the reading may push a suit, in either direction. The sampler turns `n` into a
#: weight of `2**n`, so this is a factor of four each way and never a zero: a seat that
#: "asked" for a suit can still turn up with none of it, which is what keeps a human who
#: ignores the convention from breaking the search.
LIMIT = 2

#: A discard is one step. Repeating it is evidence, and two is where it stops counting —
#: a player throwing a third card of the same suit has usually just run out of anything else.
STEP = 1


def sister(suit: int) -> int:
    """The other suit of the same colour: ``♦0 ↔ ♥1``, ``♠2 ↔ ♣3``."""
    return suit ^ 1


def _fold(affinity, leader: int, cards, trump: int) -> None:
    """Fold one trick's discards into `affinity`, in place."""
    if not cards:
        return
    led = card_suit(cards[0])
    for i, card in enumerate(cards):
        if i == 0:
            continue  # a lead is a choice, not a discard
        seat = (leader + i) % NUM_SEATS
        suit = card_suit(card)
        if suit == led or suit == trump:
            continue  # followed, or trumped — neither is a discard
        # Thrown: short here, and under the convention asking for the sister suit.
        row = affinity[seat]
        row[suit] = max(-LIMIT, row[suit] - STEP)
        row[sister(suit)] = min(LIMIT, row[sister(suit)] + STEP)


def infer_affinity(
    tricks_played,
    current_trick,
    current_leader: int,
    contract: Contract,
    cfg: RulesConfig | None = None,
) -> list[list[int]]:
    """Per-seat, per-suit weighting of what the discards suggest.

    Reads every seat's discards, not only the partner's. The convention is played in the
    open — an opponent throwing Ecken tells the whole table the same thing it tells their
    partner, and there is no reason to be the only player who did not notice.
    """
    # `is_trump`, not truthiness: Contract.DIAMONDS is 0 and therefore falsy, and reading
    # every diamonds contract as a no-trump one would score trumped tricks as discards.
    trump = contract.trump_suit if contract.is_trump else -1
    affinity = [[0] * 4 for _ in range(NUM_SEATS)]
    for leader, cards in tricks_played:
        _fold(affinity, leader, cards, trump)
    _fold(affinity, current_leader, current_trick, trump)
    return affinity
