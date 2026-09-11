"""Table conventions: how the bot plays among moves the search cannot separate.

The search decides what to play. This decides *which* of the moves it rates the same, and
only those — it never overrides a preference the search actually expressed. That restriction
is the whole design: a convention that can talk the bot out of a better card is worse than no
convention, and the measurement in `docs/measurements.md` would have to catch it afterwards
rather than the code preventing it.

Why bother at all. Determinized search plays its own cards well and plays as a *partner*
badly: `docs/measurements.md` says so, and more thinking does not fix it. What a human at the
table complains about is not the bot's card strength, it is that the bot is unreadable — it
neither sends the signals a partner expects nor plays in the shape that lets a partner plan.
Two conventions cover most of that, and both are about being legible rather than about
winning the trick in front of you:

**The discard.** When you cannot follow and are not trumping, the card you throw is a
message. The convention here is the colour-pair one: to ask for a suit, throw its sister —
the other suit of the same colour. Hearts and Ecken are the red pair, Schaufel and Kreuz the
black one, and in this deck's indexing the sister is simply ``suit ^ 1``. So a bot wanting
hearts led throws a low Ecken, and one wanting Schaufel throws a low Kreuz. It throws cheap
and it never throws a card that is still the best of its suit, which is the part that makes
the convention safe to follow rather than a way of donating tricks.

**Cashing when the trumps are one-sided.** Once the opposing pair is provably out of trump,
a top card in a side suit is no longer a card that might win — it is a trick. Leading those
out is both stronger and clearer to a partner, who can then count what is left.

What is *not* here: reading the convention back. The bots do not infer a partner's intent
from a discard, and a human playing the convention at them will not be understood. That is
the same partner-modelling gap the search has, and closing it is a different piece of work
than this one.
"""

from __future__ import annotations

from .cards import SUIT_MASK, card_list, card_suit
from .rules import Contract
from .tables import CARD_VALUES, STRENGTH
from .trick import NUM_SEATS

#: A candidate is a tie if the search picked it in nearly as many determinizations as the
#: best move *and* scored it the same. Both, because either alone is noisy: votes swing on a
#: handful of deals, and two moves can share a mean while one of them wins far more often.
VOTE_SLACK = 0.05     #: of the determinizations run
SCORE_SLACK = 0.01    #: of a share of the round's points


def sister(suit: int) -> int:
    """The other suit of the same colour — the one you throw to ask for this one.

    ``♦0 ↔ ♥1`` and ``♠2 ↔ ♣3`` in this deck's indexing, which is what makes it one xor.
    """
    return suit ^ 1


def _top_live(live: int, suit: int, contract: Contract) -> int:
    """The strongest card of `suit` that has not been played yet, as a single-bit mask.

    Strength, not rank: Undenufe runs the other way, and reading the table backwards there
    would have the bot throwing its winners away.
    """
    cards = live & SUIT_MASK[suit]
    if not cards:
        return 0
    strength = STRENGTH[contract][suit]
    return 1 << max(card_list(cards), key=lambda c: strength[c])


def tied(candidates, determinizations: int):
    """The moves the search could not separate, best first.

    `candidates` is `native.dmcts` output: `(card, visits, mean_score, determinizations)`.
    """
    if not candidates:
        return []
    best = candidates[0]
    slack = max(1, round(VOTE_SLACK * max(1, determinizations)))
    return [
        c for c in candidates
        if c[3] >= best[3] - slack and c[2] >= best[2] - SCORE_SLACK
    ]


def wanted_suit(hand: int, unseen: int, contract: Contract) -> int:
    """The side suit this hand would like led to it.

    Where the tricks are: holding the best card left in a suit is worth far more than being
    long in one, so it dominates, and length breaks the tie between two such suits.
    """
    trump = contract.trump_suit if contract.is_trump else -1
    live = hand | unseen
    best, best_score = -1, -1.0
    for suit in range(4):
        if suit == trump:
            continue
        mine = hand & SUIT_MASK[suit]
        if not mine:
            continue
        score = 0.1 * bin(mine).count("1")
        if _top_live(live, suit, contract) & hand:
            score += 2.0
        if score > best_score:
            best, best_score = suit, score
    return best


def opponents_out_of_trump(forbidden, seen: int, seat: int, contract: Contract) -> bool:
    """Whether both opponents are *proven* to hold no trump.

    `forbidden` is `voids.infer_forbidden`; `seen` is every card face up plus this seat's
    own hand. Proven, not guessed: a trump the play has not ruled out is a trump they may
    have, and cashing into it is exactly the mistake this is meant to avoid.
    """
    if not contract.is_trump:
        return False
    unseen_trumps = SUIT_MASK[contract.trump_suit] & ~seen
    return all(
        unseen_trumps & ~forbidden[other] == 0
        for other in range(NUM_SEATS)
        if (other - seat) % 2 == 1
    )


def choose(candidates, obs, forbidden) -> int:
    """The card to play, given what the search returned.

    Returns the search's own first choice unless a convention applies to a move it rated the
    same.
    """
    if not candidates:
        raise ValueError("no candidates")
    fallback = candidates[0][0]
    # Every determinization votes for exactly one move, so the votes sum to the budget.
    options = tied(candidates, sum(c[3] for c in candidates))
    if len(options) < 2:
        return fallback

    cards = [c[0] for c in options]
    values = CARD_VALUES[obs.contract]
    live = obs.hand | obs.unseen

    # Leading with the opponents out of trump: a top card is a trick, so take it.
    if not obs.trick and opponents_out_of_trump(forbidden, obs.hand | obs.played, obs.seat, obs.contract):
        winners = [c for c in cards if _top_live(live, card_suit(c), obs.contract) == 1 << c]
        if winners:
            return max(winners, key=lambda c: (values[c], -c))

    # Discarding: neither following the led suit nor trumping, so the card is a message.
    if obs.trick:
        led = card_suit(obs.trick[0])
        trump = obs.contract.trump_suit if obs.contract.is_trump else -1
        throws = [c for c in cards if card_suit(c) != led and card_suit(c) != trump]
        # Never throw a card that is still the best of its suit — the convention is about
        # what you can spare, and spending a winner to send a message is not a convention,
        # it is a gift.
        throws = [c for c in throws if _top_live(live, card_suit(c), obs.contract) != 1 << c]
        if throws:
            want = wanted_suit(obs.hand, obs.unseen, obs.contract)
            ask = sister(want) if want >= 0 else -1
            # `-c` is the *lowest rank*: card indices run ace-first inside a suit, so the
            # bigger index is the smaller card. Sorting the other way throws the seven and
            # keeps the six, which is backwards and looks like a bug to anyone watching.
            return min(throws, key=lambda c: (card_suit(c) != ask, values[c], -c))

    return fallback
