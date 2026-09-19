"""A first Sidi Barrani bidder: the owner's bidding language, spoken literally.

The language is in `docs/sidi-plan.md`. This module is its rule-based speaker — step 3 of that
plan, the rung every later bidder is measured against. It is deliberately literal: the value a
bot bids *says* what it holds, so a human partner can read it, and a later belief model can read
it back.

- Trump, **odd** value: the Bauer and k more trumps, 30 + 20k (50 = Bauer + one).
- Trump, **even** value: the Nell without the Bauer and k more, 20 + 20k (80 = Nell + three).
  Neither: no trump bid, unless the suit is long (five or more), then a Nell-style bid.
- Obenabe / Undenufe: 30 + 10 per ace / six (40 = one). Only opened on three or more.
- Support a partner's Bauer bid with the Nell and one more trump, or three trumps without it;
  support a partner's Nell bid only with the Bauer. A support's parity names the supporter's own
  card, as an opening's does. Support Obenabe / Undenufe at +10 per ace / six.
- Doubling is a stopper count against the standing bid. A placeholder until the hand evaluator
  (plan step 4) can price a double properly.
"""

from __future__ import annotations

from .auction import Call
from .cards import card_rank, card_suit, card_list
from .rules import Contract, RulesConfig

RANK_A, RANK_J, RANK_9, RANK_6 = 0, 3, 5, 8


def _trumps(hand: int, suit: int) -> tuple[bool, bool, int]:
    cards = [c for c in card_list(hand) if card_suit(c) == suit]
    ranks = {card_rank(c) for c in cards}
    return RANK_J in ranks, RANK_9 in ranks, len(cards)


def _count_rank(hand: int, rank: int) -> int:
    return sum(1 for c in card_list(hand) if card_rank(c) == rank)


def trump_value(hand: int, suit: int) -> int | None:
    """What the language says for this suit as trump, or None for "say nothing"."""
    bauer, nell, n = _trumps(hand, suit)
    more = n - 1
    if bauer and more >= 1:
        return 30 + 20 * more
    if nell and more >= 1:
        return 20 + 20 * more
    if n >= 5:
        return 20 + 20 * more
    return None


def slalom_count(hand: int, contract: Contract) -> int:
    return _count_rank(hand, RANK_A if contract is Contract.OBENABE else RANK_6)


def opening(hand: int) -> tuple[Contract, int] | None:
    """The strongest thing this hand can say on its own."""
    best: tuple[Contract, int] | None = None
    for suit in range(4):
        value = trump_value(hand, suit)
        if value is not None and (best is None or value > best[1]):
            best = (Contract(suit), value)
    for contract in (Contract.OBENABE, Contract.UNDENUFE):
        count = slalom_count(hand, contract)
        if count >= 3:
            value = 30 + 10 * count
            if best is None or value > best[1]:
                best = (contract, value)
    return best


def _with_parity(least: int, odd: bool, floor: int) -> int:
    """The smallest value of the right parity that is at least `least` and beats `floor`."""
    value = max(least, floor + 10)
    if (value // 10) % 2 != odd:
        value += 10
    return value


def support(hand: int, contract: Contract, value: int, floor: int = 0) -> int | None:
    """What to bid on a partner's `contract value`, or None for no support.

    A support speaks the same language as an opening: its parity names the supporter's own card —
    even for the Nell on a partner's Bauer, odd for the Bauer on a partner's Nell — and it is at
    least what the supporter would have opened with.
    """
    if contract in (Contract.OBENABE, Contract.UNDENUFE):
        count = slalom_count(hand, contract)
        return value + 10 * count if count else None
    bauer, nell, n = _trumps(hand, int(contract))
    if value % 20 == 10:          # odd tens: the partner has the Bauer
        if (nell and n >= 2) or n >= 3:
            return _with_parity(20 + 20 * (n - 1), odd=False, floor=max(floor, value))
        return None
    if bauer:                     # even tens: the partner has the Nell
        return _with_parity(30 + 20 * (n - 1), odd=True, floor=max(floor, value))
    return None


def _ladder(value: int, cfg: RulesConfig) -> int:
    """The value on the ladder, capped below 157 — the language stops at 150."""
    return min(value, max(v for v in cfg.sidi_bids if v <= 150))


def _may_double(hand: int, contract: Contract, value: int) -> bool:
    if contract in (Contract.OBENABE, Contract.UNDENUFE):
        return slalom_count(hand, contract) >= 2 and value >= 90
    bauer, nell, n = _trumps(hand, int(contract))
    stoppers = 2 * bauer + nell + (n >= 3)
    return (stoppers >= 3 and value >= 90) or (stoppers >= 2 and value >= 120)


def choose_call(
    hand: int, auction: tuple, seat: int, cfg: RulesConfig, double: bool | None = None
) -> str:
    """One call, in its wire form. `auction` is `(seat, call)` pairs so far, as in an observation.

    `double` overrides the stopper count when the caller has a better answer — the agent's
    make-probability estimate (`rust/src/sidi_estimate.rs`).
    """
    calls = [(s, Call.parse(c)) for s, c in auction]
    high = next(((s, c) for s, c in reversed(calls) if c.kind == "bid"), None)
    floor = high[1].value if high else 0

    if high is not None and (high[0] - seat) % 2 == 1:
        # The opponents hold it: double if the hand says their number is not there.
        if (_may_double(hand, high[1].contract, high[1].value) if double is None else double):
            return "DOUBLE"

    if high is not None and high[0] == (seat + 2) % 4:
        # The partner holds it. If that bid is in a contract this seat has already named — the
        # partner supporting it, or it having supported the partner — the message is sent:
        # raising again only bids the partnership up against itself.
        named = {c.contract for s, c in calls if s == seat and c.kind == "bid"}
        if high[1].contract in named:
            return "PASS"

    options: list[tuple[Contract, int]] = []
    partner = next(((s, c) for s, c in reversed(calls) if c.kind == "bid" and s == (seat + 2) % 4), None)
    if partner is not None:
        raised = support(hand, partner[1].contract, partner[1].value, floor)
        if raised is not None:
            options.append((partner[1].contract, raised))
    own = opening(hand)
    if own is not None:
        options.append(own)

    for contract, value in sorted(options, key=lambda o: -o[1]):
        value = _ladder(value, cfg)
        if value > floor:
            return str(Call("bid", contract, value))
    return "PASS"


def double_after_lead(hand: int, contract: Contract, value: int) -> bool:
    """The question after the lead: the same stopper count, on the cards still in hand."""
    return _may_double(hand, contract, value)
