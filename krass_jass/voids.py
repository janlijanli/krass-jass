"""Void inference — what the play history *proves* about the other hands.

`PLAN.md` §3.3 calls this the highest value-per-line feature in the search, and it is exact
inference, not a model: if a player fails to follow suit, they are provably void in it.
Constraining determinization to consistent worlds costs almost nothing and removes a large
class of impossible deals from the search.

Two Jass-specific traps live here, and both are the kind that silently produce a *stronger*
looking bot that is quietly reasoning about impossible worlds:

1. **Trumping proves nothing.** In most trick-taking games, playing a trump on a non-trump
   lead means you could not follow. In Jass you may always trump, so a trump tells you
   nothing about the led suit.
2. **A discard on a trump lead does not prove no trumps.** Under the Puur exemption, a
   player whose only trump is the trump Jack may play anything. So the proof is the weaker
   "their trump holding is a subset of {Puur}" — a statement about eight specific cards,
   not about a suit. This is why constraints are card masks rather than suit voids.
"""

from __future__ import annotations

from .cards import SUIT_MASK, card_suit
from .trick import NUM_SEATS
from .rules import Contract, RulesConfig
from .tables import PUUR_MASK


def _apply_trick(
    forbidden: list[int],
    leader: int,
    cards: tuple[int, ...] | list[int],
    trump: int,
    cfg: RulesConfig,
) -> None:
    """Fold one trick's worth of evidence into `forbidden`, in place."""
    if not cards:
        return
    led = card_suit(cards[0])

    for i, card in enumerate(cards):
        if i == 0:
            continue  # the lead proves nothing
        seat = (leader + i) % NUM_SEATS
        suit = card_suit(card)
        if suit == led:
            continue  # followed suit — no information

        if trump < 0:
            # Obenabe / Undenufe: plain follow-suit, so an off-suit card is proof
            forbidden[seat] |= SUIT_MASK[led]
            continue

        if led == trump:
            # Trump was led and they did not follow. They hold no trump — except that under
            # the Puur exemption they may hold exactly the Puur and nothing else in trump.
            if cfg.puur_exempt_trump_lead:
                forbidden[seat] |= SUIT_MASK[trump] & ~PUUR_MASK[trump]
            else:
                forbidden[seat] |= SUIT_MASK[trump]
            continue

        if suit == trump:
            # They trumped. Legal whether or not they could follow, so this proves nothing.
            continue

        # Neither followed nor trumped: provably void in the led suit.
        forbidden[seat] |= SUIT_MASK[led]


def infer_forbidden(
    tricks_played: list[tuple[int, tuple[int, ...]]],
    current_trick: list[int],
    current_leader: int,
    contract: Contract,
    cfg: RulesConfig,
) -> list[int]:
    """Per-seat mask of cards each seat provably cannot hold.

    A constraint proven at any point stays true: a player who held none of a suit then
    cannot have acquired one since.
    """
    trump = contract.trump_suit
    forbidden = [0] * NUM_SEATS
    for leader, cards in tricks_played:
        _apply_trick(forbidden, leader, cards, trump, cfg)
    _apply_trick(forbidden, current_leader, current_trick, trump, cfg)
    return forbidden


def infer_from_state(state, cfg: RulesConfig | None = None) -> list[int]:
    """Convenience wrapper over a :class:`krass_jass.state.RoundState`.

    Uses only public information — the played tricks — so it is safe to call from anywhere
    that builds an observation.
    """
    return infer_forbidden(
        state.tricks_played,
        state.trick,
        state.leader,
        state.contract,
        cfg or state.cfg,
    )
