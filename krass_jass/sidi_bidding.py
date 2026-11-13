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
- Never outbid the opponents in a contract they named: with their trumps, wait for the knock.
- Doubling is a stopper count against the standing bid. A placeholder until the hand evaluator
  (plan step 4) can price a double properly.

That is the style `"count"` — «Aggressiv» in the menu, and the default. The second style,
`"feel"` — «Gspürsch mi, füehlsch mi» (owner, 2026-11-12) — is further down: a bid is the
cheapest step and the message is *which contract, and how often*, so two partners find each
other over several rounds. Which style a seat speaks is public (`RulesConfig.sidi_bid_styles`).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .auction import Call
from .cards import card_rank, card_suit, card_list
from .rules import Contract, RulesConfig

RANK_A, RANK_K, RANK_J, RANK_9, RANK_7, RANK_6 = 0, 1, 3, 5, 7, 8

#: The two bidding styles, in the order Rust numbers them (0, 1).
STYLES = ("count", "feel")


def style_of(styles: tuple, seat: int) -> str:
    """The style `seat` speaks. An empty tuple is a table where everyone counts."""
    return styles[seat] if styles else "count"


def style_codes(styles: tuple) -> list[int] | None:
    """The styles as Rust numbers them, or None for a table where everyone counts."""
    if not styles or all(style == "count" for style in styles):
        return None
    return [STYLES.index(style) for style in styles]


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
    hand: int, auction: tuple, seat: int, cfg: RulesConfig, double: bool | None = None,
    style: str = "count",
) -> str:
    """One call, in its wire form. `auction` is `(seat, call)` pairs so far, as in an observation.

    `double` overrides the stopper count when the caller has a better answer — the agent's
    make-probability estimate (`rust/src/sidi_estimate.rs`). `style` is the language this seat
    speaks; doubling is the same in both.
    """
    calls = [(s, Call.parse(c)) for s, c in auction]
    high = next(((s, c) for s, c in reversed(calls) if c.kind == "bid"), None)
    floor = high[1].value if high else 0

    if high is not None and (high[0] - seat) % 2 == 1:
        # The opponents hold it: double if the hand says their number is not there.
        if (_may_double(hand, high[1].contract, high[1].value) if double is None else double):
            return "DOUBLE"

    if style == "feel":
        return _feel_call(hand, calls, seat, cfg)

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

    # Never outbid the opponents in a contract they named (owner, 2026-09-19): holding their
    # trumps is a reason to wait for the knock, not to take the suit off them at a higher price.
    theirs = {c.contract for s, c in calls if c.kind == "bid" and (s - seat) % 2 == 1}
    for contract, value in sorted(options, key=lambda o: -o[1]):
        value = _ladder(value, cfg)
        if value > floor and contract not in theirs:
            return str(Call("bid", contract, value))
    return "PASS"


def double_after_lead(hand: int, contract: Contract, value: int) -> bool:
    """The question after the lead: the same stopper count, on the cards still in hand."""
    return _may_double(hand, contract, value)


# -- «Gspürsch mi, füehlsch mi» --------------------------------------------------------------
#
# The second style (owner, 2026-11-12). The counting language puts the message in the bid's
# *height*, so one bid says everything. Here a bid is the cheapest step — the standing bid + 10 —
# and the message is which contract, and how often:
#
# - a first bid in a contract: "my best game", strength `open` or more (and three trumps);
# - raising the partner's contract: "it fits" — the Bauer, the Nell or three trumps, an ace / a
#   six for Obenabe / Undenufe — and strength `raise` or more;
# - a new contract over the partner's: "not yours, but here I have something";
# - the same contract again: one more point of strength per bid;
# - a step of 20 or more: much stronger — `jump` points more than the plain step would say;
# - pass: "I have said everything". Never a refusal; a seat may come back in.
#
# Parity is a hint only: a seat that jumps into a trump suit it has not named takes the odd one
# of the two jumps (+20, +30) with the Bauer. A seat never bids above
# `lid_base + 10 x (its own strength + what the partner has shown)`.
#
# The numbers are in `data/sidi_feel.json`, one file for both implementations.

_NO_TRUMP = (Contract.OBENABE, Contract.UNDENUFE)


@lru_cache(maxsize=1)
def feel_weights() -> dict:
    path = Path(__file__).parent / "data" / "sidi_feel.json"
    return {k: v for k, v in json.loads(path.read_text()).items() if not k.startswith("_")}


def feel_strength(hand: int, contract: Contract) -> int:
    """What the hand is worth in `contract`, in the points the style counts in."""
    w = feel_weights()
    cards = card_list(hand)
    if contract in _NO_TRUMP:
        top, second = (RANK_A, RANK_K) if contract is Contract.OBENABE else (RANK_6, RANK_7)
        tops = {card_suit(c) for c in cards if card_rank(c) == top}
        seconds = sum(1 for c in cards if card_rank(c) == second and card_suit(c) in tops)
        return w["top"] * len(tops) + w["second"] * seconds
    suit = int(contract)
    bauer, nell, n = _trumps(hand, suit)
    aces = [card_suit(c) for c in cards if card_rank(c) == RANK_A]
    return (
        w["bauer"] * bauer + w["nell"] * nell + w["trump_ace"] * (suit in aces)
        + max(0, n - w["long_from"] + 1) + w["side_ace"] * sum(1 for a in aces if a != suit)
    )


def feel_fit(hand: int, contract: Contract) -> bool:
    """Enough to say "it fits" to a partner's contract."""
    if contract in _NO_TRUMP:
        return slalom_count(hand, contract) >= 1
    bauer, nell, n = _trumps(hand, int(contract))
    return bauer or nell or n >= 3


def feel_shown(calls: list, seat: int) -> dict:
    """The strength `seat` has shown so far, per contract it has bid: what its bids *said*.

    Read off the auction alone, so the partner, the reader (`rust/src/sidi_read.rs`) and the
    bidder itself all arrive at the same number.
    """
    w = feel_weights()
    partner = (seat + 2) % 4
    shown: dict = {}
    partners: set = set()
    standing = 30
    for s, call in calls:
        if call.kind != "bid":
            continue
        if s == seat:
            if call.contract in shown:
                said = shown[call.contract] + 1
            else:
                said = w["raise"] if call.contract in partners else w["open"]
            if call.value - standing >= 20:
                said += w["jump"]
            shown[call.contract] = said
        elif s == partner:
            partners.add(call.contract)
        standing = call.value
    return shown


def _feel_value(hand, contract, mine, partners, standing, cap) -> int | None:
    """The value this seat would bid in `contract` now, or None if it has nothing to say there."""
    w = feel_weights()
    strength = feel_strength(hand, contract)
    first = contract not in mine
    trump = contract not in _NO_TRUMP
    if not first:
        need = mine[contract] + 1
    elif contract in partners:
        if not feel_fit(hand, contract):
            return None
        need = w["raise"]
    else:
        if trump and _trumps(hand, int(contract))[2] < w["min_trumps"]:
            return None
        need = w["open"]
    if strength < need:
        return None
    lid = min(cap, w["lid_base"] + 10 * (strength + partners.get(contract, 0)))
    plain = standing + 10
    if plain > lid:
        return None
    if strength >= need + w["jump"]:
        jump = standing + 20
        if trump and first and _trumps(hand, int(contract))[0] and (jump // 10) % 2 == 0:
            jump += 10          # the Bauer: the odd one of the two jumps, if the lid allows it
        if jump > lid:
            jump = standing + 20
        if jump <= lid:
            return jump
    return plain


def _feel_call(hand: int, calls: list, seat: int, cfg: RulesConfig) -> str:
    partner = (seat + 2) % 4
    high = next(((s, c) for s, c in reversed(calls) if c.kind == "bid"), None)
    standing = high[1].value if high else 30
    cap = max(v for v in cfg.sidi_bids if v <= 150)
    mine = feel_shown(calls, seat)
    partners = feel_shown(calls, partner)
    theirs = {c.contract for s, c in calls if c.kind == "bid" and (s - seat) % 2 == 1}

    def value(contract: Contract) -> int | None:
        if contract in theirs:      # never outbid the opponents in a contract they named
            return None
        return _feel_value(hand, contract, mine, partners, standing, cap)

    # The partner's latest contract first: agreeing is what the auction is for.
    latest = next((c.contract for s, c in reversed(calls) if c.kind == "bid" and s == partner), None)
    if latest is not None:
        v = value(latest)
        if v is not None:
            return str(Call("bid", latest, v))
        if high[0] == partner and feel_fit(hand, latest):
            return "PASS"           # it fits and all is said: leave the partner in it
    # Otherwise this seat's own best game — one it has named, or a new one. The stronger wins,
    # the lower contract on a tie.
    best: tuple[int, Contract, int] | None = None
    for contract in Contract:
        if contract == latest:
            continue
        v = value(contract)
        if v is None:
            continue
        strength = feel_strength(hand, contract)
        if best is None or strength > best[0]:
            best = (strength, contract, v)
    if best is not None:
        return str(Call("bid", best[1], best[2]))
    return "PASS"
