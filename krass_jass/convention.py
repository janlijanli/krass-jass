"""Table conventions: how the bot plays among moves the search cannot separate.

The search decides what to play. This decides *which* of the moves it rates the same, and
only those — it never overrides a preference the search actually expressed. That restriction
is the whole design: a convention that can talk the bot out of a better card is worse than no
convention, and `docs/measurements.md` §5i measured exactly that — hand-written play rules given
real weight inside the search cost 0.84 of a round's share.

Why bother at all. Determinized search plays its own cards well and is unreadable as a
*partner*: it neither sends the signals a human expects nor plays in the shape that lets a
partner plan. These are the Swiss Schieber conventions, taken from the Swisslos "Jass-Onkel"
tips, jassverzeichnis.ch, the Luzerner Zeitung's "Verwerfen, Anziehen & Schieben", Watson's
nine situations and a Schieber champion's tips in Blick — and implemented as tie-breaks, so
they make the bot legible without making it weaker.

**Leading**

1. *Opponents out of trump* — the best card left in a side suit is a trick: cash it.
2. *Trumpf ziehen* — the declaring team draws the opponents' trumps. With the Bauer and two or
   more others, lead the Bauer; with exactly one other, lead that one ("nicht zu zweit"); never
   the Bauer alone ("nie blutt"). Without the Bauer, lead the best trump left if held, or with
   three or more, the second one ("Trumpf-Ass nicht zu dritt").
3. *Showing the Bauer* — holding it alone, lead a Brettli (6 to 9) of the strongest side suit:
   it tells the partner the Bauer is there without spending it.
4. *Cashing from the top* — aces first, then kings as each becomes the best left, avoiding a
   suit the partner has thrown away ("wenn der Partner eine Farbe verwirft, diese nicht
   bringen").
5. *Anziehen* — in the strongest suit without its best card, lead the lowest, so the ace is
   drawn and the king becomes the Bock.

**Following**

1. *Obenabe/Undenufe* — when the partner leads the best card of a suit, drop the next one under
   it (the king under the ace, the seven under the six), so the partner can count the suit.
2. *Schmieren* — last to play with the partner taking the trick, give it points: the highest
   card that is neither a trump nor the best left of its suit. And never trump the partner's
   trick ("du trumpfst zu viel").
3. *Verwerfen* — unable to follow and not trumping, throw from the *weakest* side suit, lowest
   first, never the best card of a suit. The partner reads it as "not this suit". (This
   replaces an earlier colour-pair convention — throw the sister of the suit you want — which
   is not what Swiss tables play.)
4. *Losing the trick anyway* — an opponent is taking it and nothing tied can beat it: spend the
   least.

The bot now *reads* one convention back — the partner's discards, when choosing what to lead.
It does not yet read the Brettli that shows the Bauer, or anziehen.
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
#: A move the search barely explored has an unreliable score, so nothing below this share of
#: the visits is ever eligible — whatever the window. It is what makes a pure *price* safe:
#: `vote_slack=1.0` drops the visit condition and leaves `score_slack` as the most a
#: convention may cost, in share of the round's points (`docs/measurements.md` §5u).
MIN_VISIT_SHARE = 0.005


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


def tied(candidates, determinizations: int, vote_slack: float = VOTE_SLACK,
         score_slack: float = SCORE_SLACK):
    """The moves the search could not separate, best first.

    `candidates` is `native.dmcts` output: `(card, visits, mean_score, determinizations)`.
    """
    if not candidates:
        return []
    best = candidates[0]
    slack = max(1, round(vote_slack * max(1, determinizations)))
    floor = MIN_VISIT_SHARE * determinizations
    return [
        c for c in candidates
        if c[3] >= best[3] - slack and c[2] >= best[2] - score_slack and (c is best or c[3] >= floor)
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


def partner_discards(obs) -> int:
    """Suits the partner has thrown away — as a 4-bit mask.

    A discard is a card of neither the led suit nor trump. Swiss play reads it as "not this
    suit", so the bot does not lead it back just because it is strong there.
    """
    partner = obs.seat ^ 2
    trump = obs.contract.trump_suit if obs.contract.is_trump else -1
    mask = 0
    tricks = list(obs.tricks_played) + ([(obs.trick_leader, tuple(obs.trick))] if obs.trick else [])
    for leader, cards in tricks:
        if not cards:
            continue
        led = card_suit(cards[0])
        for i, c in enumerate(cards):
            if (leader + i) % NUM_SEATS == partner and card_suit(c) not in (led, trump):
                mask |= 1 << card_suit(c)
    return mask


def _suit_strength(hand: int, live: int, suit: int, contract: Contract) -> float:
    """How much a side suit is worth to its holder: the best card left dominates, then
    points, then length."""
    mine = hand & SUIT_MASK[suit]
    if not mine:
        return -1.0
    values = CARD_VALUES[contract]
    score = 0.1 * bin(mine).count("1") + sum(values[c] for c in card_list(mine)) / 11.0
    if _top_live(live, suit, contract) & hand:
        score += 2.0
    return score


def _lowest(cards, contract: Contract) -> int:
    """The cheapest card, then the weakest — `-strength`, not `-index`, so Undenufe is right."""
    values = CARD_VALUES[contract]
    return min(cards, key=lambda c: (values[c], STRENGTH[contract][card_suit(c)][c]))


def _lead(cards, obs, forbidden, live, trump, boss) -> int | None:
    contract = obs.contract
    values = CARD_VALUES[contract]
    declaring = (obs.declarer_seat & 1) == (obs.seat & 1)
    out_of_trump = opponents_out_of_trump(forbidden, obs.hand | obs.played, obs.seat, contract)
    discarded = partner_discards(obs)

    # 1. The opponents are out of trump: the best card left in a side suit is a trick.
    if out_of_trump and boss:
        return max(boss, key=lambda c: (values[c], -c))

    held_trumps = []
    if trump >= 0:
        strength = STRENGTH[contract][trump]
        held_trumps = sorted(card_list(obs.hand & SUIT_MASK[trump]), key=lambda c: -strength[c])
    bauer = trump * 9 + 3 if trump >= 0 else -1          # the Jack of trumps

    # 2. Trumpf ziehen — the declaring team draws the opponents' trumps, by the Swiss rules:
    #    the Bauer with two or more others; with exactly one other, that one; never alone.
    if declaring and held_trumps and not out_of_trump:
        n = len(held_trumps)
        target = None
        if bauer in held_trumps:
            target = held_trumps[1] if n == 2 else (bauer if n >= 3 else None)
        elif _top_live(live, trump, contract) == 1 << held_trumps[0]:
            target = held_trumps[0] if n >= 2 else None
        elif n >= 3:
            target = held_trumps[1]                     # the ace with two more: the second one
        if target in cards:
            return target

    # 3. The Bauer "blutt": show it with a Brettli (6 to 9) of the strongest side suit.
    if declaring and held_trumps == [bauer]:
        brettli = [c for c in cards if card_suit(c) != trump and c % 9 >= 5]
        if brettli:
            best = max(range(4), key=lambda s: (s != trump) * (_suit_strength(obs.hand, live, s, contract) + 10))
            return min(brettli, key=lambda c: (card_suit(c) != best, values[c], -c))

    # 4. Cash from the top — aces, then kings as each becomes the best left — avoiding a suit
    #    the partner threw away.
    side = [c for c in boss if card_suit(c) != trump]
    if side:
        wanted = [c for c in side if not discarded >> card_suit(c) & 1] or side
        return max(wanted, key=lambda c: (values[c], -c))

    # 5. Anziehen — in the strongest suit without its best card, lead the lowest.
    suits = [s for s in range(4) if s != trump and not discarded >> s & 1
             and bin(obs.hand & SUIT_MASK[s]).count("1") >= 2
             and not _top_live(live, s, contract) & obs.hand]
    suits = [s for s in suits if any(card_suit(c) == s for c in cards)]
    if suits:
        strong = max(suits, key=lambda s: _suit_strength(obs.hand, live, s, contract))
        return _lowest([c for c in cards if card_suit(c) == strong], contract)
    return None


def _follow(cards, obs, live, trump, boss) -> int | None:
    contract = obs.contract
    values = CARD_VALUES[contract]
    led = card_suit(obs.trick[0])
    by_led = STRENGTH[contract][led]
    best_i = max(range(len(obs.trick)), key=lambda i: by_led[obs.trick[i]])
    winner = (obs.trick_leader + best_i) % NUM_SEATS
    partner = obs.seat ^ 2
    best_strength = by_led[obs.trick[best_i]]

    # 1. Obenabe/Undenufe: the partner led the best card of a suit — drop the next one under it
    #    (the king under the ace, the seven under the six), so the partner can count the suit.
    if (contract in (Contract.OBENABE, Contract.UNDENUFE) and obs.trick_leader == partner
            and len(obs.trick) >= 1):
        top = obs.trick[0]
        in_suit = [c for c in range(led * 9, led * 9 + 9)]
        if max(in_suit, key=lambda c: by_led[c]) == top:
            nxt = max((c for c in in_suit if c != top), key=lambda c: by_led[c])
            if nxt in cards:
                return nxt

    if winner == partner:
        # 2. Schmieren — last to play, the trick is ours: give it points, but not a trump and
        #    not the best card left of a suit.
        if len(obs.trick) == 3:
            gifts = [c for c in cards if card_suit(c) != trump and c not in boss]
            if gifts:
                return max(gifts, key=lambda c: (values[c], -c))
        # Don't trump the partner's trick — "du trumpfst zu viel".
        plain = [c for c in cards if card_suit(c) != trump]
        if plain and len(plain) < len(cards):
            return _lowest(plain, contract)

    # 3. Verwerfen — neither following nor trumping: throw from the weakest side suit, lowest
    #    first, never the best card left of a suit.
    throws = [c for c in cards if card_suit(c) not in (led, trump) and c not in boss]
    if throws:
        weakest = min(sorted({card_suit(c) for c in throws}),
                      key=lambda s: _suit_strength(obs.hand, live, s, contract))
        return _lowest([c for c in throws if card_suit(c) == weakest], contract)

    # 4. An opponent is taking the trick and nothing tied can beat it: spend the least.
    if winner != partner and all(by_led[c] <= best_strength for c in cards):
        return _lowest(cards, contract)
    return None


def choose(candidates, obs, forbidden, vote_slack: float = VOTE_SLACK,
           score_slack: float = SCORE_SLACK) -> int:
    """The card to play, given what the search returned.

    Returns the search's own first choice unless a convention applies to a move it rated the
    same.
    """
    if not candidates:
        raise ValueError("no candidates")
    fallback = candidates[0][0]
    # Every determinization votes for exactly one move, so the votes sum to the budget.
    options = tied(candidates, sum(c[3] for c in candidates), vote_slack, score_slack)
    if len(options) < 2:
        return fallback

    cards = [c[0] for c in options]
    live = obs.hand | obs.unseen
    trump = obs.contract.trump_suit if obs.contract.is_trump else -1
    boss = {c for c in cards if _top_live(live, card_suit(c), obs.contract) == 1 << c}
    pick = (_lead(cards, obs, forbidden, live, trump, [c for c in cards if c in boss])
            if not obs.trick else _follow(cards, obs, live, trump, boss))
    return fallback if pick is None else pick
