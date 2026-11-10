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

`ecken_ten_muss` — **default `True`** (owner, 2026-11-06), the **Müessi**. Whoever was dealt the
Ecken 10 opens a game's first round. In the **Schieber** it must choose trump without shoving; in the
**Coiffeur** it only opens and may shove like anyone (owner, 2026-11-07: "the Ecken 10 only decides who
is first in the Müessi"). From the second round the choice passes on one seat in play order
(counter-clockwise), shoving as usual. The Sidi has no shove. The table marks who is in the Müessi
with a gold M (`Game.muessi_seat`): the Schieber's first round, and every Coiffeur round's first
chooser — the M does not move with a shove. **Off in `EVAL`**: every arena deal
is a game's first round, so on there it would force a choice on every deal measured. Known gap: the
bots' bid likelihood still reads a first-round choice as if forehand could have shoved.

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

The question reaches a seat **on its turn in the first trick**, in play order, the same
moment the call itself is made — not to the whole table before a card is down. The seat on
turn is the only one that may answer, and it answers before it plays. That is the rule, and
it is also the only point at which the answer can be an informed one: by your turn you have
seen what was led.

**Announcement is staged, in three steps.** Each player calls the *value* of their best Weis
when their turn comes round in the first trick — not all at once when the contract settles.
Once every call is in, the **single best** Weis shows its cards to prove it. Everything then
comes off the table.

The winning *team* scores all of its Weis, but only that one Weis is ever shown: a partner's
holding stays private. This is an information-boundary rule rather than presentation —
revealing every seat's cards would give away three hands at the top of each round, and
revealing a partner's gives away one for nothing.

**Stöck is announced when the second of King/Queen of trumps is played**, as at the table —
not at the top of the round. The timing carries information: holding both trump honours is
worth knowing, and revealing it early is a choice a real player would rather make
themselves. Every card is played over nine tricks, so a held Stöck is always eventually
announced; the timing changes, not whether it scores.

`stoeck_enabled` — **default `True`**, `False` in `EVAL`. King + Queen of trumps in one hand = 20
points. It is not a Weis, cannot be beaten, and is announced when the second of the two is played.
**There is no Stöck in Obenabe or Undenufe** — there is no trump suit to hold. The engine must not
award it in no-trump contracts.

---

## The Jasstafel

How the score is written on the board, rather than how it is calculated. Notation follows
<https://jassverzeichnis.ch/schreiben-jassen-uebersicht>; the layout follows the board a Jass
app draws.

**The two teams face each other across a horizontal centre strip**, not side by side, and the
far team's half is turned upside down so each player reads their own marks the right way up
from their seat. The strip carries both totals and the target.

**Each total sits on the side its own marks are on.** Rotating the far half flips its marks
to the other side of the board, so a "them on the left, us on the right" reading puts every
total beside the *other* team's marks — which is unreadable, and was wrong here until someone
looked at a board and said so.

| Mark | Worth |
|---|---|
| full-height upright | 100 |
| cross | 50 |
| short tick on the baseline | 20 |

Height and shape carry the value, not stroke count. A first attempt used a double upright for
100 and a single for 20; on the board they read as four identical vertical lines with no way
to tell 140 from 400. A run of one kind of mark is followed by a gap so the groups read
apart.

Five marks fill a row, and a completed row is struck through — the bundling the notation calls
for, drawn at row scale. Whatever is left under 20 is **written out as a number**; real scores
are not multiples of twenty, and rounding them would put the wrong total on the board.

**Marks accumulate; they are not redrawn.** Each round is written up as it is scored and the
marks stay where they were put. Only the remainder is wiped and rewritten, because the next
round's leftover joins it and may become a new mark. So a team can end with three 50-marks
where a redrawn total would show a hundred and a fifty — that is not an error, it is what a
board that has been written on looks like, and it is why the bundling rule exists at all. The
invariant is that marks plus remainder always equal the cumulative score.

Red on black, as the app's board is. `MARKS` and `PER_ROW` in `web/static/tafel.js` are the
table, and `--chalk` in the stylesheet is the colour; changing any of them is a one-line
change rather than a rewrite.

## Game length and end conditions

`target_score` — **default `3000`**. ≈12 rounds. Also supported: `1500`, `1000`, and `None` for a
single round (useful for evaluation and for a short web session — see `PLAN.md` §1.7).

`schneider_enabled` — **default `True`**. Losers under 1500 are *Schneider*. Cosmetic; affects
reporting, not play.

`bergpreis_enabled` — **default `False`**. Bonus for reaching 1500 first. A regional variant.

`claim_order` — **default `("stoeck", "weis", "stich")`**. Which claim resolves first when two teams
cross the target in the same round.

---

## Table conventions

Not rules — the engine checks none of them — but agreed before the first card, so every seat knows
them. Chosen in the settings panel, in every mode; the bots play them and read them.

`discard_signal` — **default `"weakest"`**. What a discard (neither following nor trumping) says.

- `"weakest"`: throw from the weakest side suit. Read as "not this suit": the partner does not
  lead it back.
- `"sister"` — *Farbpaar* (owner, 2026-11-10). Throw the other suit of the same colour as the one
  you want: Schaufel asks for Kreuz, Kreuz for Schaufel, Ecken for Herz, Herz for Ecken.
  - **The sister is trump:** throw the wanted suit itself. Ecken trump, a thrown Herz asks for Herz.
  - **Schmieren is weak evidence.** A card worth ten or more thrown while the thrower's partner is
    taking the trick counts only until a real discard comes, and is not read as a request.
  - **A second discard of another suit confirms.** Kreuz 8 first, then Herz 10: Schaufel is wanted,
    and strongly — the thrower kept Schaufel and let two other suits go.
  - Throwing the suit one asked for takes the request back.

  The reading is `read_signals` in `krass_jass/convention.py` (`rust/src/convention.rs`). The partner
  brings the asked suit when it leads — its best card of it, or the lowest — and the play model the
  beliefs and the tree read the table through is one fitted to self-play under this convention
  (`krass_jass/data/play_policy_sister.json`).

---

## Open, deferred out of M0

These do not block the engine and are recorded so they are not forgotten:

- **Target strength** — casual or club player. Affects M4 tuning only.
- **Latency budget per bot move** — 1s? 2s? Blocks the M4/M5 architecture, not M1.
- **CPU-only or GPU** — blocks the M5 estimate.
- **Multi-human** — assumed no. Changes session handling if it ever becomes yes; decide before M2.

See `PLAN.md` §9 and `docs/plan-review.md` §4.

---

## Sidi Barrani — the second game mode

`mode` — **default `"schieber"`**. `"sidi"` switches the bidding, scoring and game end to Sidi
Barrani; the trick-taking is the Schieber's, unchanged. The `SIDI` preset carries the decisions
below. They were taken by the owner on 2026-09-18, from four sources that disagree
(pagat.com, jassverzeichnis.ch, swissjass.ch's rules PDF, a Fribourg tournament sheet).

**Contracts.** The six Schieber contracts. No Slalom, no Misère — deliberately, not deferred.
Every contract counts **×1**: `multipliers` all ones.

**The auction.** The seat after the dealer calls first, then round the table in play order.
A call is one of:

| Call | Legal when |
|---|---|
| a bid: contract + value | the value is higher than the standing bid. There is no order among contracts: Hearts 100 beats Spades 90, not Spades 100 |
| pass | always. A seat that passed may bid again when its turn comes round |
| double | a bid stands and the caller is on the *other* team from its bidder |

`sidi_bids` — **default `40, 50, … 150, 157, 257`**. 157 is every card point; 257 is Match.
A seat may overbid its own partner.

The auction ends when three seats pass in a row after a bid, when a bid of 257 is made, or when
an opponent doubles. If all four pass before anyone bids, the hand is thrown in and **the next
seat deals**. The highest bidder declares and **leads the first trick**.

**Doubling.** Only the declarer's opponents may double, and they may do so **at any time until the
second card of the first trick is on the table** (`sidi_double_after_lead`, default `True`): in the
auction **out of turn as well** — the moment a bid is made, without waiting for the seat in between
to speak (owner, 2026-09-19; a double is the only call that may come out of turn, and it does not
move the turn) — and once more after the declarer has led. The app asks the player right after
each opposing bid, and again after the lead. It has to *ask* —
at a real table a player can knock at any moment, and a question at the one point where it can
still matter is the only faithful way to simulate that. The seat after the leader is asked
first, then the seat before the leader. A double in the auction ends the auction
(`sidi_double_ends_auction`, default `True`; every source that allows it agrees). **No redouble**,
and no flag for one.

**Scoring.** Both teams write their card points (157 a round, 257 with Match: `match_bonus`
stays 100). On top, the bid is a stake: if the declaring team's points reach the bid it writes
the bid as a bonus; if not, the opponents write it. A double doubles the bonus.

| | made | failed |
|---|---|---|
| Hearts 100, 113 points | declarers 113 + 100, opponents 44 | — |
| Hearts 120 doubled, 113 points | — | declarers 113, opponents 44 + 240 |
| Match (257) made | declarers 257 + 257 = **514** | — |
| Match doubled, failed at 119 | — | declarers 119, opponents 38 + **514** |

One rule for every bid, Match included: bonus = bid × 2 if doubled.

**No Weis, no Stöck.** `weis_enabled` and `stoeck_enabled` are off in the preset.

**Game end.** `target_score` **2000**. A round is always played to the end — there is no
claiming the target mid-round, so `claim_order` does not apply. After a round, if either
team has 2000 or more, the higher score wins. There is **no end rule** (neither the
"Überbiet-" nor the "Bonus-Schlussregel"): a wild bid near the target is part of the tactics.
A dead level score at or above the target (2021 : 2021) has no rule of its own: nobody has won, so another hand is dealt. Deliberately not treated further (owner, 2026-09-18).

**Dealer.** After a played hand the **declarer deals**, so the seat to their right — the next in
play order — makes the first call (owner, 2026-09-20). After a hand thrown in, the deal simply
passes on. The very first dealer is settled by the Ecken 10, as in the Schieber.

---

## Coiffeur — the third game mode

`mode = "coiffeur"`, preset **`COIFFEUR`**. The trick-taking is the Schieber's, unchanged; the
choosing, scoring and game end are the sheet's. Sources: pagat.com (Coiffeur-Schieber), Swisslos,
jassverzeichnis.ch, lodige.com, and the Coiffeur-Partnerschieber regulation of Jassclub Wasserturm.
They agree on the core and disagree on the details; every detail is a flag or listed as open below.
Defaults taken 2026-10-30 when the mode was started and **confirmed by the owner 2026-10-31**, with
one change: points are written in tens.

**The sheet.** Each team has a column of **seven rows** — diamonds, hearts, spades, clubs, Obenabe,
Undenufe and the **Chance** — plus the extra rows (next sections; all six by default, so thirteen rows
and a game of **26 rounds**). Each team plays every row exactly once. The Chance (owner, 2026-11-01:
the two Jokers became one Chance) is free of choice: it takes any game, a contract or any extra row's
— `coiffeur_chance_takes_extra`, **default `True`**; `False` limits it to the six contracts, as on
Swisslos's Joker. A game whose own row is filled can only go into the Chance.

**Multipliers.** Each row has one, the same for both teams. **The Chance is always ×13**
(`coiffeur_chance_multiplier`, owner, 2026-11-01) and is never part of the draw.
`coiffeur_random_multipliers` — **default `True`** (owner, 2026-10-30): the other rows get a
permutation of 1..n over the n of them played — 1..12 with all six extra rows — drawn from the game
seed (`krass_jass/coiffeur.py`, the deal's SplitMix64 → Fisher-Yates → Lemire on its own stream, so
both implementations deal the same sheet). With `False`, `coiffeur_multipliers` — **default
`4, 2, 3, 1, 5, 6, ·, 7, 8, 9, 10, 11, 12`** in slot order (the Chance's slot is not read),
jassverzeichnis.ch's sheet for the contracts: Eichel ×1, Rosen ×2, Schilten ×3, Schellen ×4, Obenabe
×5, Undenufe ×6; the extra rows follow on. **Disagreement:** pagat's
four-player table puts acorns/spades ×1, flowers/clubs ×2, shields/diamonds ×3, bells/hearts ×4 —
the sources do not even agree which suit is cheapest, which is one reason random is a good default.

**Choosing.** Forehand (the seat after the dealer) chooses a row or shoves. In the game's first
round forehand is the Ecken 10 (`ecken_ten_muss`, above), who may shove too. A shove goes to the
**next seat in play order — an opponent**, not the partner. After four shoves the choice is back
with forehand, who must choose ("im Loch", "im Fass"). Once one team has filled its column only the
other team chooses: the first seat of that team from forehand chooses or shoves **to its partner**,
who may shove back once; then it must choose. The dealer passes on as in the Schieber.

**Play.** Whoever chooses **leads** the first trick. No Weis, no Stöck (every source agrees).

**Scoring.** Only the choosing team writes: its card points (157 a round) into the row, times the
row's multiplier.
`coiffeur_tens` — **default `True`** (owner, 2026-10-31): the points are written in tens, rounded
half up (84 → 8, 85 → 9), and the tens are multiplied. **Rounding is ours:** Wasserturm rounds up
from 4; the owner asked for tens, not for a rounding rule. With `False` the points are written in full.

**Match** (owner, 2026-11-03). `coiffeur_match_stroke` — **default `10`**. A match is not a bonus in
the row: the row gets the 157 card points like any full hand (16 in tens), and the team earns a
**stroke** ( | ) in the sheet's own **Match** category, worth 10 as written and **never multiplied**.
The stroke goes to the team that took all nine tricks: the choosing team, or its opponents in a
**counter-match**, where the choosing team writes 0. The choosing team in a Misère never earns one
(next section). `match_bonus` stays 100 so the engine sees the match; the 100 itself is not written.
`None` is the rule before: the match bonus counted into the row (257 → 26 × the multiplier).
`coiffeur_score_opponents` — **default `False`**. When `True` the defenders are credited with their
card points times the same multiplier (Jassclub Wasserturm's rule); their row stays open.

**Game end.** When both columns are full. The higher total wins; a level total is a draw
(`winner = -1`, `decided_by = "sheet"`). `target_score` is `None`.

**Open, not implemented** (each needs a decision before it is built):

- **The other extra rows** — Zick-Zack, Züri. Researched 2026-10-31, below; not built, each
  waiting for the owner's definition. Tutti, Slalom, Guschti, 3×3, Misère and Mitte are (next
  sections).
- **A wrong choice** ("Fehlwahl") — the engine refuses a closed row, so it cannot arise.

### Coiffeur — Tutti, Slalom, Guschti, 3×3 and Misère (built 2026-10-31 and 2026-11-01)

The owner chose these five, and the Mitte (next section). `coiffeur_extra_rows` — **default all six** (owner, 2026-10-31, Tutti
2026-11-01); `()` is the six contracts and the Chance. They sit after the Chance on the sheet (slots
7–12: Tutti, Slalom, Guschti, 3×3, Misère, Mitte), and with random multipliers the permutation grows to 1..12. `krass_jass/schedule.py` and `rust/src/schedule.rs`
write each game out as the contract of each of its nine tricks.

- **Counted in the first trick's contract**, as every source that says how agrees.
- **Slalom**: the chooser picks Obenabe-first or Undenufe-first (`SLALOM_OBENABE`, `SLALOM_UNDENUFE`).
- **Guschti**: five tricks one way, then four the other, the chooser picking which first (Swisslos).
  `coiffeur_guschti_45` — **default `False`**; `True` also offers four then five (jasswiki,
  swissjass.ch's Riesenslalom, Fässler).
- **3×3** (owner, 2026-10-31): three blocks of three tricks. The chooser names the first block
  (`TRIO_HEARTS`), **whoever leads trick 4 names the second, whoever leads trick 7 the third** —
  whichever team they are on. Each may name any contract, and the suit may change from block to
  block, but the three must include at least one trump suit and at least one Obenabe or Undenufe:
  the third block is forced when the first two left one out. The game has a phase for it (`block`,
  event `block_chosen`). The search does not know a block before it is named and draws it at random
  from what may be named, once per iteration; the bots name a block by the rule selector's edge
  (`coiffeur_select.choose_block`).
- **Tutti** (owner, 2026-11-01, swissjass.ch's definition): **the suit led to each trick is trump for
  that trick.** Every trick is therefore a trump lead: follow the suit led if you can, the Puur
  exempt; nobody can trump in, because no other suit is trump; the highest card of the led suit in
  trump order (Puur, Nell, Ace…) takes it. The round is **counted as if the first trick's suit were
  trump all round** — its Puur 20 and Nell 14, the other Jacks 2 and nines 0 — so the chooser, who
  leads, picks the counting suit with the first card. Until a trick is led its order is unknown
  (`None` in the schedule, `-2` in the observation); until the first card the round's contract is a
  placeholder, Obenabe, and the search treats the count as open until it sees the lead
  (`Kernel::count_open`).
- **Misère** (owner, 2026-10-31): the chooser picks Obenabe or Undenufe (`MISERE_OBENABE`), and the
  aim is to take as few points as possible. The choosing team writes the points the **opponents**
  took — 157 minus its own — so both teams play to avoid points, and the search's objective is
  turned round for every seat (`Stakes::misere`). **It must take at least one trick** (owner,
  2026-11-03): if the opponents take all nine it writes 0 and they earn a match stroke; the search
  sees that edge (`Stakes::misere_declarers`, read off the points as the Sidi reads Match). Taking
  all nine in its own Misère writes 0 and earns no stroke.
- **The Chance** takes any of these games too (`coiffeur_chance_takes_extra`, above).

### Coiffeur — Mitte (built 2026-11-06)

The owner's definition, 2026-11-06 (jasswiki's Mezzo/Mitte had one line and no full rule). It is
the sixth extra row, `"MITTE"` in `coiffeur_extra_rows` (**on by default**, so thirteen rows, 26
rounds, multipliers 1..12 and the Chance ×13), sheet slot 12, wire name `MITTE`.

- **Card order** (`rules.Order.MITTE`, `tables::MITTE`): no trump. The **ten** is highest, then
  outwards from it in pairs — **9 = Under**, **8 = Ober**, **7 = King**, **6 = Ace**. A pair ranks
  equal, and **of an equal pair the card played first takes the trick** ("whichever lies first").
  Follow suit as in Obenabe; a card not of the led suit never takes the trick.
- **Counting** — by the first trick, like every extra row, but its first *card* does not always
  decide: **the first card of trick 1 that is not a ten** does. Under, Ober, King or Ace (above the
  ten) counts the round as **Obenabe**, a 9, 8, 7 or 6 (below it) as **Undenufe**. A ten led first
  leaves it to the next card, and so on (owner: "next card decides"). Only tens can come before the
  deciding card, and a ten is worth 10 either way, so no point is counted twice. **Ours:** four
  tens in trick 1 leave it Obenabe — the owner's rule does not reach that case.
- The Chance may take a Mitte (`coiffeur_chance_takes_extra`).

How the bots value it is in `docs/coiffeur-plan.md`; the search plays it with the trick order per
trick and counts it as above (`Kernel::on_card`, `Kernel::mitte_at`).

### Coiffeur — the extra rows, researched (2026-10-31)

Sources: Swisslos (the ten-row Coiffeur), swissjass.ch "Die neuen Trumpfvarianten im Coiffeurjass"
(2003, the most exact), schweizerjass.ch's Fässler Coiffeur (14 rows), jasswiki.ch's taxonomy, and
pagat (three-player Coiffeur). They agree on the names more than on the rules. Where they differ, the
definitions are listed side by side; **the owner picks one per row before it is built.**

**What every source agrees on.** Only the choosing team writes, at the row's multiplier. A row that
mixes card orders **counts all nine tricks as the first trick's order** (swissjass.ch, Fässler): a
Slalom begun in Obenabe is counted as an Obenabe, so the eights are worth 8 throughout.

| Row | Definition | Who decides | Disagreement |
|---|---|---|---|
| **Slalom** (Zick-Zack in pagat) | Obenabe and Undenufe alternate trick by trick | The chooser, which order comes first (Swisslos, Fässler, pagat) | none |
| **Guschti** (5/4, Riesenslalom) | A block of tricks in one order, then the rest in the other | The chooser, which first | **The split.** Swisslos: 5 then 4. jasswiki: 4 Obenabe then 5 Undenufe is "Guschti", the reverse is "Mary". swissjass.ch "Riesenslalom": the chooser picks any of 4/5, 5/4 either way round. Fässler: "5/4 – 4/5". |
| **3×3** (Trio, "3 mal 3"; TUO in pagat) | Three tricks each of a trump suit, Obenabe and Undenufe; the trump suit stays the same | **Three readings.** swissjass.ch: whoever leads trick 1 picks the first block, whoever leads trick 4 the second, whoever leads trick 7 makes trump if it is still to come. Fässler: the chooser fixes the order, or "open": the winner of each block's last trick picks the next. pagat (TUO): fixed order — trump of the chooser's choice, then Undenufe, then Obenabe. | the order and who picks it |
| **Zick-Zack** (Fässler only) | Trump, Obenabe, Undenufe in rotation trick by trick, the trump suit fixed | The chooser fixes the rotation, or open: the winner of the second trick picks | one source |
| **Tutti** | **Three different games under one name.** swissjass.ch: the suit led to each trick is trump for that trick; counted as if trick 1's suit were trump all along (its Puur 20, its Nell 14, the other Puure 2, the other nines 0). jasswiki: Obenabe with Puur and Nell as the highest cards, or a changing trump. pagat: another name for Gustav, i.e. a Guschti. | — | the definition itself |
| **Züri** (Fässler only) | Every card is trump: every Puur counts 20, every Nell 14 — 302 a round, 402 with a match | — | one source; the trick-taking is not spelled out |
| **Misère** | Take as few points as possible | **Two readings.** swissjass.ch: always played Obenabe, and the *opponents'* points are what the choosing team writes. Fässler, jasswiki: any contract may be played as a Misère. | the contract, and what is written |
| **Mezzo** (Mitte, Tännli) | A new card order: the ten is highest and the rest rank from the middle outwards | — | jasswiki only, one line; no full rule found |
| **Frei** | A third or fourth Joker | the chooser | none |

**Ten rows** is the established extension (Swisslos: the eight plus Slalom and Guschti 5/4). Fässler
has fourteen, ×1 to ×14. With random multipliers the permutation simply grows to 1..n.

**What it costs to build** (`docs/coiffeur-plan.md` takes the order):

1. *Card order per trick* — Slalom, Guschti, 3×3, Zick-Zack. The contract becomes a sequence of nine
   per-trick orders drawn from the existing six, plus a counting order (trick 1's). Legal moves,
   trick winners, scoring, void inference and the Rust search kernel all have to read the order of
   *this* trick instead of the round's. No new card order, so the legal-move table keeps its keys. The
   "open" 3×3 also adds decisions in the middle of the round, which the event log and the observation
   carry and the search must model as a choice node.
2. *Trump per trick* — swissjass.ch's Tutti. Trump is unknown until the lead, so the leader's choice
   of suit is also a choice of trump. Same machinery as step 1, with a different rule for the order.
3. *A different objective* — Misère. The play is ordinary; the score is turned round, so the search's
   objective and the selector's value flip sign. Cheapest to build, but the bots' play model was fitted
   on players who want points.
4. *A new card order* — Mezzo, Züri. A new ranking and new point values: new legal-move and
   trick-winner tables in both implementations, and a rule nobody has written down in full.

