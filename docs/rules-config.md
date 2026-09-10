# Rules configuration — M0 deliverable

Jass is full of house rules and the sources disagree. Every disputed point is a flag here, with a
default and a reason. **Nothing in the engine hardcodes a variant.** If you find yourself writing a
rule constant inline, it belongs in this file first.

Two presets matter:

- **`HOUSE`** — the default. What a human plays against the bots.
- **`EVAL`** — Weis, Stöck and the match bonus off. Used for every bot-vs-bot measurement, because
  those three are the dominant source of scoring variance (`PLAN.md` §4, following the HSLU/Fribourg
  benchmarking method).

Sources: pagat.com Schieber and Swiss Jass pages, Swisslos rule pages. Where they disagree the
disagreement is noted.

---

## Card encoding

Card index = `suit * 9 + rank`, so a hand is a 36-bit integer and a suit is a 9-bit mask.

| | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| **suit** | ♦ diamonds `D` | ♥ hearts `H` | ♠ spades `S` | ♣ clubs `C` |

| rank | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| | A | K | Q | J | 10 | 9 | 8 | 7 | 6 |

Rank order is fixed and *descending in the plain (non-trump) order*, so plain-order comparison is
just `rank_a < rank_b`. Trump and Undenufe orders are lookup tables over the same indices, not
different encodings.

Text form is two characters, suit letter then rank char, e.g. `DJ`, `HA`, `S6`. **Ten is `T`**, since
the wire format in `PLAN.md` §5.2 is two-character codes. The parser also accepts `D10` and is
case-insensitive; the formatter always emits `T`.

---

## Contracts and multipliers

| Contract | Code | Multiplier | Flag |
|---|---|---|---|
| Diamonds (Schellen) | `DIAMONDS` | 1 | `multipliers` |
| Spades (Schilten) | `SPADES` | 1 | `multipliers` |
| Hearts (Rosen) | `HEARTS` | 2 | `multipliers` |
| Clubs (Eichel) | `CLUBS` | 2 | `multipliers` |
| Obenabe | `OBENABE` | 3 | `multipliers` |
| Undenufe | `UNDENUFE` | 4 | `multipliers` |

The ×1 pair is Schilten + Schellen = **spades and diamonds**. This is the single easiest thing in the
whole ruleset to get wrong; `PLAN.md` had it as spades and clubs before review. German→French
mapping: Eichel↔♣, Rosen↔♥, Schilten↔♠, Schellen↔♦.

The multiplier applies to **everything**: trick points, Weis, Stöck and the match bonus.

**Disagreement:** some houses play every contract ×1 with a 1000-point target instead. Set
`multipliers` to all-ones and `target_score = 1000` for that. Some also play Undenufe at ×3 (equal to
Obenabe); `multipliers` covers it.

`allow_zurueckschieben` — **default `False`**. Whether the partner may shove back to forehand. Off is
the more common Schieber rule; when on, forehand must then choose.

---

## Card values

| Rank | Non-trump | Trump | Obenabe | Undenufe |
|---|---|---|---|---|
| A | 11 | 11 | 11 | **0** |
| K | 4 | 4 | 4 | 4 |
| Q | 3 | 3 | 3 | 3 |
| J (Puur) | 2 | **20** | 2 | 2 |
| 10 | 10 | 10 | 10 | 10 |
| 9 (Näll) | 0 | **14** | 0 | 0 |
| 8 | 0 | 0 | **8** | **8** |
| 7 | 0 | 0 | 0 | 0 |
| 6 | 0 | 0 | 0 | **11** |

Every contract totals 152 in the cards. **Undenufe inverts the values along with the order** — the 6
is worth 11 and the ace 0. Because the total is 152 either way, a "points sum to 157" test does not
catch a mis-implemented Undenufe. Test per-card values directly (`test_scoring.py` does).

`last_trick_bonus` — **default `5`**. 152 + 5 = 157 per round.

`match_bonus` — **default `100`**, `0` in `EVAL`. Awarded for taking all nine tricks. 157 + 100 = 257.

---

## Card order

| Contract | Order, strongest first |
|---|---|
| Trump suit | **J > 9 > A > K > Q > 10 > 8 > 7 > 6** |
| Plain suit | A > K > Q > J > 10 > 9 > 8 > 7 > 6 |
| Obenabe | A > K > Q > J > 10 > 9 > 8 > 7 > 6 |
| Undenufe | **6 > 7 > 8 > 9 > 10 > J > Q > K > A** |

---

## Trick-taking

Play is **anticlockwise**. The trick winner leads the next trick. Any card may be led.

Trump contracts:

- **You may always trump, even when you can follow suit.** This is the rule that separates Jass from
  Bridge/Skat/Hearts and it is why the branching factor is high. Do not "fix" it.
- Non-trump led, you can follow: play the led suit *or* any trump (subject to undertrumping).
- Non-trump led, you cannot follow: play anything (subject to undertrumping).
- **Trump led: you must follow with a trump** — `puur_exempt_trump_lead`, **default `True`**: unless
  your only trump is the Puur (trump J), in which case you may play anything. With no trump at all,
  play anything.
- `strict_undertrump` — **default `True`** (this is the Schieber rule). When a non-trump was led and
  someone has already trumped, you may not play a *lower* trump. Exception: if your hand is nothing
  but trumps, any trump is allowed.
  - **Disagreement:** some houses allow undertrumping freely. Set to `False`.
  - Note the rule does **not** apply when trump was led — there, following trump is compulsory and
    any trump is legal.

No-trump contracts (Obenabe / Undenufe): ordinary follow-suit. Follow the led suit if you can,
otherwise play anything. Highest of the led suit in the contract's order wins. There is no trumping
and no undertrumping.

---

## Weis

`weis_enabled` — **default `True`**, `False` in `EVAL`. Announced during the first trick.

`weis_large` — **default `False`**. Small Weis:

| Combination | Points |
|---|---|
| Sequence of 3 in a suit | 20 |
| Sequence of 4 | 50 |
| Sequence of 5 or more | 100 |
| Four 10s / Queens / Kings / Aces | 100 each |
| Four Jacks | 200 |
| Four 9s | 150 (see `weis_four_nines`) |

With `weis_large = True`, longer sequences score separately — 6→150, 7→200, 8→250, 9→300 — and a
card may count in **both** a four-of-a-kind and a sequence. Under small Weis it counts in only one.

`weis_four_beats_sequence` — **default `True`**. Does a four of a kind beat a sequence worth the
same 100 points? The sources genuinely differ; the default follows the common "any four of a kind
beats a sequence" reading. Only ever affects equal-point clashes.

`weis_four_nines` — **default `True`**. Common but explicitly "must be agreed" in the sources, so it
is a flag.

Sequence order is always A K Q J 10 9 8 7 6 **regardless of contract**, so J-10-9 of trumps is a
valid sequence and J-9-A is not. In Undenufe the reversed order applies for *tie-breaking* only.

Under small Weis, "each card counts once" means the best announcement is sometimes a **shorter**
sequence that steps out of a four of a kind's way: A-K-Q-J of diamonds plus four jacks scores 220 as
four jacks + A-K-Q, not 200 as four jacks alone. A run never splits into two announced sequences,
though — otherwise a run of nine would score 150 as a 4 and a 5 instead of 100.

Comparison, to decide which team scores: longer sequence beats shorter → higher top card → trump
breaks further ties → earliest to play. Equal-scoring options are announced as the *strongest* meld,
not just an equal-scoring one — a run of nine and a run of five both score 100, but only the nine
beats an opponent's run of six. **The team holding the single best Weis scores all of its
Weis; the other team scores nothing.**

`weis_manual` — **default `False`**; the web app sets it `True`. Ask the holder whether to
announce rather than announcing for them. A declined Weis leaves the contest entirely: not
scored, not announced, and unable to win the comparison for its team.

**Announcement is staged.** Everyone calls the *value* of their best Weis;
only the team holding the best one then shows its cards. That staging is an
information-boundary rule, not presentation — revealing every seat's Weis cards would leak
three hands at the top of every round.

**Known simplification:** Stöck is announced at the top of the round rather than when the
second of King/Queen is played. This gives away timing a real player would choose when to
reveal. Acceptable for v1; fix when the Weis UI becomes manual.

`stoeck_enabled` — **default `True`**, `False` in `EVAL`. King + Queen of trumps in one hand = 20
points. It is not a Weis, cannot be beaten, and is announced when the second of the two is played.
**There is no Stöck in Obenabe or Undenufe** — there is no trump suit to hold. The engine must not
award it in no-trump contracts.

---

## Game length and end conditions

`target_score` — **default `3000`**. ≈12 rounds. Also supported: `1500`, `1000`, and `None` for a
single round (useful for evaluation and for a short web session — see `PLAN.md` §1.7).

`schneider_enabled` — **default `True`**. Losers under 1500 are *Schneider*. Cosmetic; affects
reporting, not play.

`bergpreis_enabled` — **default `False`**. Bonus for reaching 1500 first. A regional variant.

`claim_order` — **default `("stoeck", "weis", "stich")`**. Which claim resolves first when two teams
cross the target in the same round.

---

## Open, deferred out of M0

These do not block the engine and are recorded so they are not forgotten:

- **Target strength** — casual or club player. Affects M4 tuning only.
- **Latency budget per bot move** — 1s? 2s? Blocks the M4/M5 architecture, not M1.
- **CPU-only or GPU** — blocks the M5 estimate.
- **Multi-human** — assumed no. Changes session handling if it ever becomes yes; decide before M2.

See `PLAN.md` §9 and `docs/plan-review.md` §4.
