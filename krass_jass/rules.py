"""Rule variants as configuration.

Every disputed point in Schieber is a field here with a written-down default. Nothing in
the engine hardcodes a variant — if a rule constant appears inline anywhere else, it
belongs in this file. ``docs/rules-config.md`` is the prose version, including the sources
and where they disagree.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import IntEnum

from .cards import CLUBS, DIAMONDS, HEARTS, SPADES


class Contract(IntEnum):
    """The six playable contracts.

    **Never test a contract for truthiness.** ``Contract.DIAMONDS`` is 0, so
    ``if contract:`` is False for a perfectly valid diamonds contract. Use
    ``if contract is not None``. This has already caused one scoring bug where every
    diamonds round was treated as no-trump — no Stöck, wrong Weis tie-break.
 The four suit contracts share the suit indices from
    :mod:`krass_jass.cards`, so ``Contract.HEARTS == HEARTS`` and the trump suit of a suit
    contract is just ``int(contract)``."""

    DIAMONDS = DIAMONDS
    HEARTS = HEARTS
    SPADES = SPADES
    CLUBS = CLUBS
    OBENABE = 4
    UNDENUFE = 5

    @property
    def is_trump(self) -> bool:
        return self < 4

    @property
    def trump_suit(self) -> int:
        """Trump suit index, or -1 for the no-trump contracts."""
        return int(self) if self < 4 else -1


#: Shove. Not a contract — a bid action, so it lives outside the enum.
SHOVE = "SHOVE"

#: Schilten + Schellen (spades + diamonds) are the cheap pair, Eichel + Rosen
#: (clubs + hearts) the dear pair. Getting this mapping backwards is the single easiest
#: mistake in the ruleset.
DEFAULT_MULTIPLIERS: dict[Contract, int] = {
    Contract.DIAMONDS: 1,
    Contract.SPADES: 1,
    Contract.HEARTS: 2,
    Contract.CLUBS: 2,
    Contract.OBENABE: 3,
    Contract.UNDENUFE: 4,
}


@dataclass(frozen=True)
class RulesConfig:
    """Immutable. Use :func:`dataclasses.replace` or :meth:`variant` to derive."""

    # -- bidding
    multipliers: dict[Contract, int] = field(default_factory=lambda: dict(DEFAULT_MULTIPLIERS))
    allow_zurueckschieben: bool = False

    # -- trick-taking
    strict_undertrump: bool = True
    puur_exempt_trump_lead: bool = True

    # -- scoring
    last_trick_bonus: int = 5
    match_bonus: int = 100

    # -- weis
    weis_enabled: bool = True
    weis_large: bool = False
    weis_four_nines: bool = True
    #: Disputed: does a four of a kind beat a sequence worth the same 100 points? Sources
    #: differ; default follows the common "any four of a kind beats a sequence" reading.
    weis_four_beats_sequence: bool = True
    #: Ask the holder whether to announce, instead of announcing for them. Declining is a
    #: real tactical choice — announcing tells the table what you hold — so it is offered
    #: rather than assumed.
    weis_manual: bool = False
    stoeck_enabled: bool = True

    # -- game length
    target_score: int | None = 3000
    schneider_enabled: bool = True
    bergpreis_enabled: bool = False
    claim_order: tuple[str, ...] = ("stoeck", "weis", "stich")

    # -- game mode (docs/rules-config.md, "Sidi Barrani")
    #: "schieber" or "sidi". Sidi replaces the bidding, the scoring and the game end; the
    #: trick-taking is the Schieber's.
    mode: str = "schieber"
    #: The bid ladder, lowest first. 157 is every card point, 257 is Match.
    sidi_bids: tuple[int, ...] = (40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 157, 257)
    #: The opponents may still double after the declarer has led, until the second card is down.
    sidi_double_after_lead: bool = True
    #: A double during the auction ends it.
    sidi_double_ends_auction: bool = True

    @property
    def sidi(self) -> bool:
        return self.mode == "sidi"

    def variant(self, **changes) -> "RulesConfig":
        return replace(self, **changes)

    def multiplier(self, contract: Contract) -> int:
        return self.multipliers[contract]


#: What a human plays against the bots.
HOUSE = RulesConfig()

#: Bot-vs-bot measurement. Weis, Stöck and the match bonus are off because they dominate
#: scoring variance and would drown any real difference between two agents (PLAN.md §4).
EVAL = HOUSE.variant(
    weis_enabled=False,
    stoeck_enabled=False,
    match_bonus=0,
    target_score=None,
)

#: Sidi Barrani as the owner plays it (2026-09-18): every contract x1, no Weis, no Stöck, to 2000.
#: The match bonus stays — a bid of 257 is a bid for Match.
SIDI = HOUSE.variant(
    mode="sidi",
    multipliers={c: 1 for c in Contract},
    weis_enabled=False,
    stoeck_enabled=False,
    target_score=2000,
)

#: One Sidi hand at a time, for measurement. Weis and Stöck are already off.
SIDI_EVAL = SIDI.variant(target_score=None)
