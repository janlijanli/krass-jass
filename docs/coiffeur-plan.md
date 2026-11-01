# Coiffeur — plan

The rules are in `docs/rules-config.md` ("Coiffeur"). This file is what is built, what the bots do,
and the training runs the mode needs. The Schieber and the Sidi stay as they are.

## What makes the Coiffeur a different game (research, 2026-10-30)

1. **The choice is an allocation, not a pick.** In the Schieber the question is "which contract is
   this hand best at?". Here every row must be played once, so it is "which row does this hand fill
   *better than a later hand would*?". A hand that is decent in hearts may be wasted on hearts if
   the dear rows are still open and a better hearts hand is likely to come. Rows kept open have an
   *option value*; that value falls as the sheet fills.
2. **The multiplier is on one team's points, not on a difference.** Only the choosing team writes.
   A weak hand in a ×8 row is not a symmetric risk as in the Schieber, it is a cheap row thrown
   away: 60 points at ×8 is 480 where a strong hand would have written 1,000+.
3. **Shoving goes to the opponent.** A shove hands the choice — and a row of *theirs* — to the
   next seat. It is far costlier than the Schieber's shove to the partner, until one team is done.
4. **The chooser leads**, as in the Sidi and unlike the Schieber.
5. **Jokers** take any contract: they are where monster hands go, and keeping one open is worth a
   random hand's *best* contract, not its average one.
6. **Random multipliers** (the default) mean nothing can be learned per row. A selector must work
   in `multiplier × (value − reserve)`, so the permutation of the day just rescales it.
7. **Late game**, a team behind needs variance and a team ahead needs safety; the score is known to
   everyone, including what each side's remaining rows can still fetch.

## What exists (2026-10-30)

- **Engine**, Python and Rust in the same commit: `krass_jass/coiffeur.py` / `rust/src/coiffeur.rs`
  (sheet, multipliers, choice wire form `HEARTS` / `HEARTS/JOKER1`), `Game.bid` → `_choose`,
  `_score_coiffeur`, events (`multipliers` on `game_started`, `row` on `contract_set`, `written` on
  `round_scored`, `decided_by: "sheet"`). `tests/test_coiffeur.py` from the rule text,
  `tests/test_game_port.py` holds both implementations to one event stream.
- **Choice, untrained** — `krass_jass/coiffeur_select.py`, `Agent.coiffeur_choice`. Scores the hand
  with the Schieber's trump weights and values each open choice as
  `multiplier[row] × (edge − reserve[row])`. Reserves are measured means (20,000 random hands);
  the Joker reserve is the mean of a hand's best edge; the shove threshold is a guess
  (`krass_jass/data/coiffeur_weights.json`). Shoves ~22% of rounds in self-play.
- **Card play** is the Schieber's search unchanged — maximising the round's share is right for
  both sides, since only the choosers' points count and the total is fixed. The Schieber's
  bid-reading model (`bid_alpha`, `read_bidding`) is **off**: a Coiffeur choice depends on the
  sheet, and reading it as a Schieber choice would mislead the beliefs.
- `arena/games.py` plays whole Coiffeur games (`cfg=COIFFEUR`).

Not yet: the selector in Rust (so not offline), the web app (sheet view, row picker, Joker), the
bot service endpoint, Slalom / Guschti.

## Training runs this needs

In order; each is measured before the next.

| step | what | data / compute (this Mac) | measured by |
|---|---|---|---|
| 1 | **Contract values in points.** `arena/contracts.py`, relabelled: the choosing team's points per contract (not the Schieber's difference), chooser leading, 20k hands × 6 contracts × 8 completions at a reduced budget | ≈ one night | held-out R² of the fit |
| 2 | **Value map.** Fit `E[points \| hand, contract]` from the trump features, replacing the Schieber edge in `coiffeur_select` (points, not score units) | minutes | regret on step 1's table |
| 3 | **Reserves and option value.** Reserve per row as a function of open rows (and rows the other team still has), fitted by simulating whole sheets with the step-2 values; the Joker's reserve the same way | hours (no search: values come from step 1's table) | regret per game |
| 4 | **Shove threshold**, both phases (to the opponent; to the partner once one team is done) | from step 3 | paired whole games |
| 5 | **A/B whole games**: the fitted selector vs the untrained one, double games on one seed, paired test on the per-game score difference | ≈ 2–3 h per 1,000 double games at 38,400 iterations | `arena/games.py` |
| 6 | **Play model and beliefs from Coiffeur self-play** (chooser leads; who chose what into which row is a signal, like the Schieber bid's +1.3) | ≈ 2 h recording + fit | A/B, replicated |
| 7 | Optional: late-game objective (needs X points to win) | — | A/B |

**Step 1 is running** (started 2026-10-31): `arena/coiffeur_contracts.py` prices all 18 games a
chooser can name — six contracts, two Slaloms, two Guschtis, six 3×3 openings, two Misères — on 1,500
hands × 2 deals at 2,400 iterations without the tree policy, as §5n priced the Schieber's calls. About
seven hours on eight cores; output in `arena/runs/2026-10-31/coiffeur_games.npz`, `summary` reads it.

**The extra rows (Slalom, Guschti, 3×3, Misère) need the same runs, and one of their own.** Their games are
valued today as the mean edge of the contracts their tricks are played in, and kept at a random hand's
best game in the row (`extra_reserve` in `coiffeur_weights.json`, untrained). Step 1 extends to them
directly: simulate each game (2 Slaloms, 2 Guschtis, 24 3×3s) as a contract and fit its value. The
play model of step 6 has only ever seen rounds in one order: inside a schedule it is shown the trick's
contract, which is right for the trick and blind to the order change still to come. Whether that costs
anything is a measurement — the search plays the schedule correctly either way, only the model of the
other seats is approximate.

Random multipliers make step 1–3's tables reusable for any sheet: they are per contract, and the
multiplier enters only as a factor.
