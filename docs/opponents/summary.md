# Every opponent so far, and what it says about our bot

*Interim, 2026-11-12 08:30 UTC. Group B (theoliver7, FAIKUE, TedMANNERs, xXTime, Nolonar ×2) and
group A's jass-bot and kurtoid are still running, about 18 hours more. Their rows get filled in when
they finish. The assessment below does not depend on them, unless theoliver7 lands close to 50%.*

Every number is our **shipped** bot (`build([], 153_600, cfg)`, 40 × 3,840, beliefs and tree policy
on) against the opponent at its strongest shipped configuration. Each deal is a double round with the
same seed in both halves, and p comes from a paired test of the per-deal share against 50%. "Share" is
our fraction of all points over the double round. Sources: `arena/opponents/results.jsonl` and
`docs/opponents/` on each branch (named in the last column).

## The scores

Sorted by our margin on the opponent's own rules, where that differs from ours. Rows whose table is
not `EVAL` are marked.

| # | Opponent | What it is | Table | n | **Our share** | p | Branch |
|---|---|---|---|---|---|---|---|
| 1 | **JassFormer v2** (jberclaz) | 4.8M-param transformer, imitation + PPO, no search | chibre (its rules: suits only, ♠×2) | 400 | **50.88%** ± 8.3 | 0.034 | opponent-jberclaz |
| | | | same, JassFormer bids for both sides | 400 | 51.82% ± 6.2 | 5e-9 | |
| | | | `EVAL` (our rules) | 400 | 60.50% ± 14.6 | ≈0 | |
| 2 | **jass-mu-zero** (Bürli, HSLU MSc) | MuZero, latent MCTS-100, learned bidding | flat (its rules: all ×1) | 400 | **51.86%** ± 10.7 | 5e-4 | opponent-mu-zero |
| | | | `EVAL` | 100 | 55.32% ± 11.0 | 1e-6 | |
| 3 | **JassTheRipper** (Niklaus, Fribourg/HSLU) | determinized MCTS + domain knowledge, 100k runs | `EVAL` | 400 | **54.88%** ± 10.5 | ≈0 | festive-turing-vsivva |
| 4 | **PIMC** (AlessioVerardo) | 20 worlds × 50 UCB1 sims, perfect-information per world | suits ×1 (its engine has no Obenabe/Undenufe) | 400 | **56.32%** ± 9.2 | ≈0 | opponent-rl |
| | | | same, our shove rate restored | 400 | 56.79% ± 9.0 | ≈0 | |
| 5 | jassager FullMCTS (HSLU DL4G) | ISMCTS 9.5 s, void-aware | `EVAL` | 100 | 59.7% | ≈0 | opponent-dl4g-a |
| 6 | dl4g_hslu (HSLU DL4G) | root-parallel ISMCTS, random rollouts | `EVAL` | 100 | 60.47% ± 12.5 | ≈0 | opponent-dl4g-a |
| 7 | Rico-Uttinger (DL4G B) | policy network, no search | `EVAL` | 100 | 60.52% ± 12.6 | ≈0 | opponent-dl4g-b |
| 8 | pyschieber ChallengePlayer | rule-based (the Zühlke challenge baseline) | `EVAL` | 400 | 62.39% ± 11.4 | ≈0 | opponent-challenge |
| 9 | Mcapozzolo (DL4G B) | flat Monte Carlo | `EVAL` | 100 | 62.88% ± 13.0 | ≈0 | opponent-dl4g-b |
| 10 | DonaldTrumpf (Zühlke 2017, 4th) | rule-based | `EVAL` | 400 | 66.95% ± 12.5 | ≈0 | festive-turing-vsivva |
| 11 | RubenNunez (DL4G B) | 15 random rollouts (crashes on 23% of moves) | `EVAL` | 100 | 67.14% ± 12.3 | ≈0 | opponent-dl4g-b |
| 12 | jassager CNN (DL4G A) | CNN rollouts | `EVAL` | 100 | 67.5% | ≈0 | opponent-dl4g-a |
| 13 | **luegl/JassAI** | PPO, two MLPs, never shoves | `EVAL` | 400 | **69.93%** ± 11.9 | ≈0 | opponent-rl |
| 14 | sobrinth (DL4G B) | greedy | `EVAL` | 100 | 74.24% ± 11.6 | ≈0 | opponent-dl4g-b |
| 15 | **FR8803** (TF-Agents DQN) | 8-output DQN; in effect random | `EVAL` | 400 | **76.84%** ± 12.6 | ≈0 | opponent-rl |
| — | *reference: uniformly random* | | `EVAL` | 300 | *76.39% ± 12.6* | | `docs/measurements.md` |
| — | theoliver7, FAIKUE, TedMANNERs, xXTime, Nolonar ×2 | (DL4G B) | | | *running* | | opponent-dl4g-b |
| — | jass-bot, kurtoid | (DL4G A) | | | *running* | | opponent-dl4g-a |
| — | not runnable | andieder, gregunz (no weights ever committed), pajai (Python 2 + Keras 1, no licence) | | | | | `others.md` |

**We beat every opponent we could run, all with p < 0.05.** On `EVAL` (our rules) the closest is
JassTheRipper at 54.9%, and nothing else is under 55%. **Two opponents fall under the 52% bar on
their own rules:** JassFormer (50.9%) and MuZero (51.9%). Both are learned bots that also *bid* with a
learned model, and both are played on tables whose multipliers differ from ours. That is the key to
the assessment.

## Where the margin comes from, and where it leaks

### 1. Card play: a consistent +2 to +5 points, even against the best

- **JassFormer, pure card play.** On deals where both teams named the same contract, only the card
  play differs between the halves: there we take **52.05%** (n = 269, p = 4e-8).
- **JassFormer, the bid arm.** With JassFormer bidding for both sides, we take 51.82% (p = 5e-9).
- **JassTheRipper and MuZero** bid on their own: 54.9% (`EVAL`) and 51.9% (flat).
- **PIMC.** It keeps only 60.1% of its own contracts; we keep 73.6% of ours.

Nothing here says the card play is weak.

### 2. Bidding: the leak, and it is a transfer problem

Our trump selector scores each contract as *(edge − baseline) × multiplier* and shoves below a
fixed threshold (3.02). Both the weights and the threshold were fitted on our multiplier table. On
any other table they misfire:

| Table | Our forehand shove rate | Opponent's |
|---|---|---|
| `EVAL` (fitted) | 53–55% | luegl 0%, FR8803 15% (random) |
| suits ×1 (PIMC) | **81.5%** | 49% |
| chibre (JassFormer) | **78.2%** | 55.5% |
| flat (MuZero) | about 74% (parent's report) | |

**Evidence that this costs points:**
- **JassFormer, decomposed** (its session's diagnosis). Where the bids differ, we take **48.5%**
  (n = 131); where we shove and JassFormer keeps the same hand, **47.5%** (n = 93). Letting
  JassFormer bid for both sides lifts us from 50.88% to 51.82%. So about **+1 point** is ours to
  take on that table from bidding alone.
  - The ×2 on spades also multiplies a *negative* edge, which steers a shoved-to partner away from
    spades even when holding the spade Jack (deal 270: they call spades on ♠J 6 and win 294:20;
    we call clubs and go 78:79).
- **PIMC.** Restoring a 53% shove rate with a recalibrated threshold gave **+0.47 ± 0.30 (p = 0.12)**:
  real, but small there.
- **MuZero.** 51.9% flat against 55.3% on `EVAL`. Part of that gap is MuZero not knowing our
  multipliers, and part is our bidding misfiring on flat.

**What this does and does not mean.**
- On our own house table the selector is fitted (+58% of games against the hand-written weights,
  §5n), so this is not a bug in what the owner plays.
- It is why two opponents get within 2 points of us **on their rules**. Our selector does not know
  what a contract is worth at a multiplier it was not fitted to.

### 3. The shoved-to partner's Undenufe

These are the worst deals for us across opponents:

- **luegl, deal 301** (26.8%): the partner calls Undenufe on ♦9 6 ♥A J ♠A K 8 6 ♣Q, with two sixes
  and three high cards. It goes 132:496.
- **luegl overall:** when we declare, the round is lost 13 times in 400. Six of those are a shoved
  Undenufe (6 of 59, 10.2%; other contracts lose 0–8%), and each costs ×3 or ×4.
- **The parent and group B** report the same pattern against DonaldTrumpf, MuZero and the DL4G B
  bots: the worst deal is a shoved-to Undenufe.
- CLAUDE.md already flags it: the selector "calls Obenabe/Undenufe about half the time — check that
  against human play".

This is the one lead that matters **on our own table**. It is a tail risk: frequent enough to show
up in the worst deals everywhere, but it moves the mean by under a point.

### 4. What the defence numbers do and do not show

Our share of the *opponent's* contracts runs from 37% (MuZero) to 69% (FR8803). Read naively, that
looks like a weak defence. Measured like for like, it isn't one:
- **PIMC:** it keeps 60.1% of its contracts; we keep 73.6% of ours. So we defend its contracts 13.5
  points better than it defends ours.
- **luegl:** it keeps 46.3% of its own contracts; we keep 81.8% of ours.

The defence share mostly reflects how good the declarer's *hand* is, and that is set by the bidding.
It is not a separate weakness.

## Update, 2026-11-12: the multiplier-aware threshold (`docs/measurements.md` §5z)

- **Item 1 below is built and on** (`DmctsAgent.trump_scale`, the owner's call). The shove threshold
  scales with the table's multiplier sum. It is exactly 1.0 on the house table.
- **JassFormer, chibre:** **+0.38% ± 0.18** of share against the shipped selector, n = 400, p = 0.032.
  Our shove rate drops from 78% to 70%. On the 50.88% row above, that puts us near 51.3%.
- **Flat self-play:** +0.27% ± 0.19, n = 1,000, p = 0.15. That is what the offline pricing predicts.
- **MuZero itself was not re-run:** its setup was refused in that session.
- **The gain is smaller than the ~1 point hoped for.** Offline, a threshold refit per table would
  add about another +0.4 to +1.3 points per declared round.
- **Item 2:** the self-play labels show the partner's Obe/Une calls are not overcalled (+108 over its
  best suit on `EVAL`). Nothing to change from them.

## How we could improve: assessment, in order of expected value

1. **Make the trump selector multiplier-aware. Cheap, and the one clear gain.**
   - The shove decision compares a *multiplied* edge with a *fixed* threshold. Either fit the
     threshold per multiplier table, or fit it on the unmultiplied edge and apply the multiplier to
     the shove alternative as well.
   - Then refit `arena/fit_trump.py` on the flat (all ×1) and chibre tables, alongside our house
     table.
   - Measure by re-running JassFormer (chibre) and MuZero (flat). Expected: about +1 point on those
     tables, which lifts both clear of 52%.
   - On our house table it should be neutral. Check that with the usual A/B, and keep it only if it
     is neutral or better.
   - Cost: hours of simulation; no search changes.
2. **Look at the shoved-to partner's Undenufe. Medium cost, uncertain gain.**
   - A targeted A/B on `HOUSE`/`EVAL`: either a stricter Undenufe requirement when shoved to (sixes
     and sevens counted, high cards penalised), or refitting the partner-side weights separately
     from forehand.
   - Use `arena/contracts.py` to measure the contract values of those hands before changing anything.
   - Expect under a point on the mean, but a real cut in the 3×/4× disasters, which is what a human
     opponent notices.
3. **Find out whether our opponent model generalises to foreign bots.**
   - Our beliefs and tree policy are fitted to our own self-play (§5o, §5p, §5w). Against a
     different style, they could help less, or mislead.
   - The parent is already running JassTheRipper with beliefs off and with the tree policy off, on
     the same deals. That result decides this item:
     - If either is worth about zero or less against JassTheRipper, the next step is a play model
       fitted on a mix of our self-play and foreign bots' games. The bridges in `arena/opponents/`
       can generate those games.
     - If both still help, there is nothing to do here.
4. **Not worth pursuing**, from the measurements already on record:
   - More search budget: flat beyond 153,600 (§3b).
   - Value or policy networks: closed on this hardware (§5s, §5t).
   - Sharper beliefs: saturated four times over (§5q, §5r).
   - Nothing in these opponent results contradicts those findings. Against the strongest searchers
     (JassTheRipper, MuZero), the margin is a steady few points, with no one deal type that loses.

**In one line:** the card play beats every bot we could run. The two near-misses come from bidding
on tables our trump weights were not fitted to. Make the trump selector multiplier-aware, then
re-measure JassFormer and MuZero.
