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


class Order(IntEnum):
    """Card orders a trick can be *played* in beyond the six contracts. Never counted in: a round
    played in one is counted as Obenabe or Undenufe (`krass_jass/schedule.py`). Indexed after the
    contracts, so `STRENGTH[order]` and the Rust tables share the numbering."""

    #: Mitte (Coiffeur, owner 2026-11-06): the ten highest, then outwards in pairs — 9 and Under,
    #: 8 and Ober, 7 and King, 6 and Ace. A pair ranks equal, and the one played first takes it.
    MITTE = 6

    @property
    def is_trump(self) -> bool:
        return False

    @property
    def trump_suit(self) -> int:
        return -1


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
    #: "Müessi": whoever was dealt the Ecken 10 opens the first round of a game and must choose
    #: trump (or, in the Coiffeur, a row) without shoving. Later rounds shove as usual. On for the
    #: Schieber and the Coiffeur (owner, 2026-11-06); the Sidi has no shove.
    ecken_ten_muss: bool = True

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
    #: "schieber", "sidi" or "coiffeur". Sidi replaces the bidding, the scoring and the game end; the
    #: trick-taking is the Schieber's.
    mode: str = "schieber"
    #: The bid ladder, lowest first. 157 is every card point, 257 is Match.
    sidi_bids: tuple[int, ...] = (40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 157, 257)
    #: The opponents may still double after the declarer has led, until the second card is down.
    sidi_double_after_lead: bool = True
    #: A double during the auction ends it.
    sidi_double_ends_auction: bool = True

    # -- Coiffeur (docs/rules-config.md, "Coiffeur"). The trick-taking is the Schieber's; the
    # choosing, the scoring and the game end are the sheet's (`krass_jass/coiffeur.py`).
    #: Deal the row multipliers out at random — a permutation of 1..n over the n rows played,
    #: the Chance excepted — instead of the fixed table below. On by default (owner, 2026-10-30).
    coiffeur_random_multipliers: bool = True
    #: The fixed table, in row order: diamonds, hearts, spades, clubs, Obenabe, Undenufe, Chance,
    #: then the extra rows: Tutti, Slalom, Guschti, 3x3, Misère, Mitte. jassverzeichnis.ch's sheet: Eichel
    #: x1, Rosen x2, Schilten x3, Schellen x4, Obenabe x5, Undenufe x6; the extra rows follow on
    #: (Fässler counts on the same way). The Chance's slot is not read — it is always
    #: `coiffeur_chance_multiplier` — and neither is a row not in the game.
    coiffeur_multipliers: tuple[int, ...] = (4, 2, 3, 1, 5, 6, 0, 7, 8, 9, 10, 11, 12)
    #: The Chance row's multiplier, random or not (owner, 2026-11-01).
    coiffeur_chance_multiplier: int = 13
    #: Also credit the defenders with their card points, times the row's multiplier. Off:
    #: Swisslos, jassverzeichnis.ch and pagat write only the choosing team.
    coiffeur_score_opponents: bool = False
    #: Write card points in tens, rounded half up (85 -> 9), and multiply those. On (owner,
    #: 2026-10-31); off writes the points in full.
    coiffeur_tens: bool = True
    #: A match is a stroke in the sheet's own Match category, worth this much as written and never
    #: multiplied; the row gets the 157 card points like any full hand (owner, 2026-11-03). The team
    #: that takes all nine tricks earns it — the choosing team, or its opponents in a counter-match —
    #: except the choosing team in a Misère, which must take a trick: if it takes none it writes 0
    #: and the opponents earn the stroke. Needs `match_bonus` on to see a match. `None` is the rule
    #: before: the match bonus counted into the row (257 -> 26 x the multiplier).
    coiffeur_match_stroke: int | None = 10
    #: The rows played beyond the seven, from `krass_jass.schedule.EXTRA_ROWS`: "TUTTI", "SLALOM",
    #: "GUSCHTI", "TRIO" (3x3), "MISERE" and "MITTE". All six (owner, 2026-10-31, 2026-11-01 and,
    #: Mitte, 2026-11-06); `()` is the six contracts and the Chance.
    coiffeur_extra_rows: tuple[str, ...] = ("TUTTI", "SLALOM", "GUSCHTI", "TRIO", "MISERE", "MITTE")
    #: Guschti also as four tricks then five, not only five then four. Off: Swisslos plays 5/4;
    #: jasswiki, swissjass.ch's Riesenslalom and Fässler allow both.
    coiffeur_guschti_45: bool = False
    #: The Chance may also take an extra row's game (a Tutti, a Slalom, a Guschti, a 3x3, a
    #: Misère), not only one of the six contracts. On: "free of choice" (owner, 2026-11-01); the
    #: Swisslos Joker is the six contracts only.
    coiffeur_chance_takes_extra: bool = True

    # -- table conventions. Not rules — the engine checks none of them — but agreed at the table
    # before the first card, so every seat (and every bot) knows them.
    #: How a discard is read (`krass_jass/convention.py`). "weakest": throw from the weakest suit,
    #: read as "not this suit". "sister" (*Farbpaar*, owner 2026-11-10): throw the other suit of
    #: the same colour as the one wanted, or the wanted suit itself when its sister is trump.
    discard_signal: str = "weakest"

    @property
    def sidi(self) -> bool:
        return self.mode == "sidi"

    @property
    def coiffeur(self) -> bool:
        return self.mode == "coiffeur"

    def variant(self, **changes) -> "RulesConfig":
        return replace(self, **changes)

    def multiplier(self, contract: Contract) -> int:
        return self.multipliers[contract]


#: What a human plays against the bots.
HOUSE = RulesConfig()

#: Bot-vs-bot measurement. Weis, Stöck and the match bonus are off because they dominate
#: scoring variance and would drown any real difference between two agents (PLAN.md §4).
EVAL = HOUSE.variant(
    # Off for measurement: the arena's deals are each a game's first round, and a forced choice
    # on every one of them would change what every earlier measurement was taken under.
    ecken_ten_muss=False,
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

#: Coiffeur: each team plays every row of the sheet once. No Weis, no Stöck (every source
#: agrees). The contract multipliers are all ones because the *row* carries the multiplier, and
#: the game ends when the sheet is full, so there is no target.
COIFFEUR = HOUSE.variant(
    mode="coiffeur",
    multipliers={c: 1 for c in Contract},
    weis_enabled=False,
    stoeck_enabled=False,
    target_score=None,
)
