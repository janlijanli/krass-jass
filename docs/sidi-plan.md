# Sidi Barrani — plan

The rules are in `docs/rules-config.md` ("Sidi Barrani — the second game mode"). This file is
the bidding language the bots will speak, and the order the work is done in. The Schieber
stays the default mode and nothing in it changes.

## The bidding language (owner, 2026-09-18)

Not rules — conventions, the way `krass_jass/convention.py` holds the card-play ones. A bot
that bids this way is readable to a human partner, and a bot that *reads* it gets the loudest
information of the hand before a card is down.

**Trump bids say which jack-or-nine you hold, and how many more trumps.**

| value | means |
|---|---|
| odd tens — 50, 70, 90, 110 | the **Bauer** (trump jack) and 1, 2, 3, 4 more trumps |
| even tens — 40, 60, 80, 100 | the **Nell** (trump nine), no Bauer, and 1, 2, 3, 4 more trumps |

So 50 is Bauer + one other trump; 80 is Nell + three. Bauer *and* Nell bids odd — the Bauer is
what is announced. Without either, normally no trump bid at all; with a lot of trumps, possibly
a Nell (even) bid.

**Supporting a partner's Bauer (odd) bid** — bid the suit again:
- with the Nell and at least one other trump (a bare Nell is normally not enough);
- or, without the Nell, with three or more trumps.

**Supporting a partner's Nell (even) bid:** only with the Bauer — unless the position is
tangled, or the game can be won on points that are as good as certain even without the bonus.

**Obenabe / Undenufe count aces / sixes.** 40 = one ace (six for Undenufe), 50 = two, and so on.
A partner supports with **+10 per ace (six)** of their own.

**Listening first.** With a very good trump it can pay to "listen" first: open Obenabe 40, hear
what the partner says about aces, and name the trump later.

**Courage is rewarded.** Up to 100–110 anything goes (*Narrenfreiheit*): a daring bid is a
legitimate bid, and the bots should not be timid below that line.

## How the bots play the Sidi (2026-09-19)

What exists, and what each part is. Nothing below is measured yet; the screens are queued
(`arena/sidi_ab.py`, "Measuring" below).

**Bidding — `krass_jass/sidi_bidding.py`.** The language above, spoken literally.

- Opening: the strongest thing the hand can say. Trumps by parity and count (Bauer + k → 30 + 20k,
  Nell + k → 20 + 20k, five or more without either → a Nell-style bid); Obenabe / Undenufe only on
  three or more aces / sixes, 30 + 10 each.
- Support: on a partner's Bauer bid with the Nell and one more trump or with three trumps, on a
  Nell bid only with the Bauer; the support's parity names the supporter's own card, and it is at
  least what the supporter would have opened with. Obenabe / Undenufe +10 per ace / six.
- Competing: bid the highest of those that beats the standing bid, capped at 150; otherwise pass.
- A seat that has already named the contract its partner now holds passes — without that rule
  two partners bid each other up (seen in the first browser game, fixed, tested).
- Doubling, in the auction and when asked after the lead: the stopper count (Bauer 2, Nell 1,
  three trumps 1; aces / sixes for Obenabe / Undenufe) against the bid's height is the rule-based
  fallback. The agent doubles on an estimate instead — next section.

**Doubling on an estimate — `rust/src/sidi_estimate.rs`** (the owner's idea, 2026-09-19): what
will the declarers take, given my cards and everything the auction said? Deal the unseen cards
400 times, weight each deal by the auction (`sidi_read.rs`, the search's own graded belief), play
it out with the play model — every seat from its own hand in that deal — and write it as the rules
do. The weighted share of deals in which the declarers reach their bid is P(make).

For the defenders a stake is worth B·(1 − 2p) undoubled and 2B·(1 − 2p) doubled, so doubling pays
exactly when p < ½. The agent doubles below `sidi_double_below` = 0.35: the margin is for the
estimate's error (the play model plays like an average bot, not like the search), and for what a
double in the auction gives up — it ends the bidding, the team's own contract with it.

Profile over 600 auctions between four agents: doubled 36% (the stopper count: 3%). The doubled
bids are genuinely worse — the declarer's own estimate of making them is 0.46 against 0.61 for the
undoubled, median bid 110 against 90. That also says the literal bidder bids high; the evaluator
(step 4) is what should fix that, and the arena is what says whether doubling this often pays.
Flags: `DmctsAgent.sidi_double_model` (on), `sidi_double_below`, `sidi_double_samples`.

Profile over 3,000 auctions between four of these bidders: never thrown in, doubled 3%, median
bid 100, almost always a trump suit. Whether those bids are makeable is exactly what the hand
evaluator (step 4) is for.

**Playing for the bid — `rust/src/objective.rs`, `sidi_reward`.** The Schieber search maximises a
share of the card points; a Sidi hand is written as cards *plus the stake*. The search now scores
every imagined hand the way it will be written: the difference between what the two teams write,
stake included, scaled into [0, 1] by the largest difference the bid allows. One point short of
the bid costs the whole stake, and the search sees that edge — from both sides, since the
defenders' value is the mirror image. Match is read off the points (157 to nothing), because the
search does not track tricks through a playout. Mirrored in `krass_jass/objective.py` and held to
the same numbers by `tests/test_sidi_search.py`. Flag: `DmctsAgent.sidi_objective`.

**Reading the auction — `rust/src/sidi_read.rs`.** Every bid is a statement about the bidder's
dealt hand, and the belief pool (`belief.rs`) weights each imagined deal by how well it agrees:

| bid | parity (Bauer / Nell) | count |
|---|---|---|
| a seat's first bid | believed | believed (0.7 a trump off) |
| a later bid, e.g. 70 → 90 | believed | a judgement call (0.2 a trump off) |
| a jump of 40 or more over the standing bid, e.g. 60 → 110 | believed | believed again |
| support of Obenabe / Undenufe | — | +10 per ace / six, believed |
| 157, 257 | — | nothing about cards |

A contradicted parity costs a world 2.0 in log weight (1.0 for an even bid from a hand with
neither card — a long suit may be bid that way). **Nothing is ever a filter**: bids are also
placed to shut the opponents out (120 instead of 110), a human bids as they like, and a belief
that removes worlds on a claim breaks the moment the claim is a bluff. Flag and weight:
`DmctsAgent.sidi_alpha` (1.0, as the Schieber's bid weight; to be tuned once it is measured).
The Schieber's bid model is switched off in the Sidi, as is the Schieber's game-score projection.

**What the bots do not do yet.** Tactical heights (120 to keep the others under), listening first
with Obenabe 40, pricing their *own* bid by what the hand can make. Those are steps 4 and
7: an evaluator fitted by simulation, then a search over the auction.

## Measuring

`arena/sidi_ab.py` — the Schieber protocol for a Sidi hand: every hand twice with the teams
swapped on one seed, a paired test on the per-hand difference in **points written** (cards plus
stake). Each seat bids and doubles with its own agent, so an arm that differs only in play bids
identically in both halves of a pair, and an arm that differs in doubling is measured on it.
Queued at 38,400 iterations, 1,000 double hands each: reading the auction (`sidi_alpha` 1 vs 0 —
which also switches the auction off in the doubling estimate), playing for the bid
(`sidi_objective` on vs off), and doubling on the estimate (`sidi_double_model` on vs off).

## Order of work

| step | what | measured by |
|---|---|---|
| 1 | Engine: mode flag, auction, doubling window, bonus scoring, game end, dealer — Python and Rust in the same commits, an auction reference written from the rules text, Hypothesis properties, the event-stream port test extended to Sidi | tests |
| 2 | App: bidding panel (value ladder × six contracts, pass, double), the double question after the lead, auction bubbles at the seats, contract banner, bonus line on the Jasstafel, mode picker; wasm build | browser check |
| 3 | Bots, playable: the convention bidder above as the first rule-based bidder; the search's objective becomes card points ± the bonus at the bid's threshold (`objective.rs` `reward_f`) | arena, paired, whole games |
| 4 | Hand evaluator: simulate each of the six contracts over completed deals, record the *distribution* of the team's points, fit P(points ≥ v) per contract. Bid and double by expected value on it, speaking the convention's parity | arena against step 3 |
| 5 | Beliefs from the auction: P(the whole auction \| a world) under the bots' own bidder, weighted like the Schieber bid (β). The Schieber's version of this was worth +1.3 | A/B, replicated |
| 6 | Play model retrained on Sidi self-play, with bid, double and declarer as inputs | A/B |
| 7 | Optional: a search over the auction itself, valued by step 4's evaluator. The literature's warning (MCTS trump selection "rarely learns to shove") says only after 4 | A/B |

Compute on this Mac: step 4's data is roughly one night (≈20k hands × six contracts × a few
completions at a reduced budget); each A/B is ≈2.5 h; step 6's recording ≈2 h.
