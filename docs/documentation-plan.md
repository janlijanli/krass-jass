# Documentation plan — "how the bot works"

Status: plan only. Build after M2 (needs a web app to live in); the data pipeline in §3 can
start today.

The goal is documentation *inside the web app* explaining how the bot plays, honest about
how strong it is, and specific enough that a sceptical reader can check the claims.

---

## 1. Three audiences, three documents

Writing one page for everyone produces a page that serves no one. The split:

| Doc | Reader | Question they arrived with | Length |
|---|---|---|---|
| **How your opponent thinks** | The player, mid-game or just after | "Why did it do *that*?" | 1 screen + a replay |
| **Is it actually any good?** | The sceptic | "Prove it." | ~3 screens, chart-led |
| **How it's built** | A developer, or you in six months | "What are the moving parts?" | Long-form, linked to source |

Only the first is on the critical path for a playable app. The second is what makes the
project interesting to anyone else. The third mostly already exists as `PLAN.md`,
`docs/plan-review.md` and `docs/rules-config.md` — it needs assembling and a diagram, not
new research.

---

## 2. Where it lives

- Routes: `/how-it-works` (player), `/strength` (sceptic), `/internals` (developer).
- Source: Markdown in `docs/site/`, rendered server-side by the same Jinja stack as the
  rest of the app. **Not** a separate docs generator — a second toolchain for four pages is
  not worth its maintenance.
- The developer doc links directly to source lines on the repo host rather than restating
  code. Restated code goes stale silently; a link goes stale loudly.

---

## 3. Numbers must be generated, never typed

**This is the main engineering decision in this plan, and the one that decides whether the
docs are still true in a year.**

Every figure in `/strength` and every throughput number in `/internals` comes from a
machine-readable artifact, not from prose someone typed:

```
CI: bench/benchmark.py --json      →  benchmark.json
CI: arena/ladder.py --json         →  ladder.json      (nightly, large n)
                                          │
                                          ▼
                        docs/site/data/ (committed, dated)
                                          │
                                          ▼
                     page renders tables + charts + "measured on <date>"
```

Consequences to build in:

- Every number renders with **the date it was measured and the sample size**. A figure
  without an `n` is not evidence.
- The nightly ladder job already exists in intent (`PLAN.md` §4: "a regression should fail
  the build"). Point the docs at the same artifact.
- `arena/ladder.py` needs a `--json` flag. Small; do it whenever.
- If an artifact is older than some threshold, the page says so rather than quietly
  presenting stale numbers as current.

---

## 4. `/how-it-works` — the player's page

Aim for one screen, then a replay. Sections:

1. **The short version.** It imagines the hidden cards many times, plays each imagined deal
   out thousands of times, and picks the card that does best on average. Three sentences,
   no jargon.
2. **What it knows and what it doesn't.** Explicitly: it sees its own hand, the cards
   played, and nothing else. Worth stating plainly because players assume bots cheat — and
   here the claim is backed by a fuzz test, which is worth linking.
3. **What it works out.** Void inference, in one example: "you discarded a heart on a spade
   lead, so it knows you have no spades." This is the single most legible piece of bot
   reasoning and it makes the rest credible.
4. **Where it's weak.** See §7 — non-negotiable.
5. **Show me.** A replay of the round just played, with the search's own numbers per card.

---

## 5. `/strength` — the statistics

They asked for this explicitly, so it gets real treatment rather than a table of results.
Each item below is a short section with a concrete number from the artifact.

**5.1 Why we measure share of points, not games won.**
A game to 3000 is ~12 rounds; win/lose is one bit per hour of play. Share of the 157 points
in a round is a continuous measure available every round, so it carries far more
information per unit of compute. State the conversion so the reader can translate: a
consistent 52% of points is a large edge over a season, not a small one.

**5.2 Deal luck, and the double round.**
The core explanation, and it should be a picture: the same deal played twice with the teams
swapped. Give the actual measured spread — in our runs, per-deal share has a standard
deviation around 8%, which means a 50-deal match cannot resolve a 2% skill difference. Then
show what pairing does to that number. This is the section that justifies everything else.

**5.3 Paired vs unpaired testing.**
Short, but include it: double rounds create paired data, and testing it as if it were
unpaired throws away most of the variance reduction. Worth saying because the project's own
plan got this wrong before review — an honest note that costs nothing and buys credibility.

**5.4 What "p = 0.03" does and does not mean.**
One paragraph. It is the probability of seeing a difference this large if the two agents
were actually equal. It is *not* the probability that the agent is better, and a
non-significant result is not evidence of equality — it is usually evidence of too few
deals.

**5.5 Statistical power — how many deals you actually need.**
The section most strength claims omit. With a per-deal standard deviation `s`, detecting a
true difference `d` needs roughly `n ≈ (2s/d)²` deals. At `s ≈ 8%`, resolving a 1% edge
takes ~250 double rounds; resolving 0.5% takes ~1000. Include the table. This is what lets
a reader interpret a null result correctly, and we hit it live: a 16× search-budget
increase looked significant at n=40 (p=0.04) and vanished at n=60 (p=0.73). Use that as the
worked example — it is more instructive than any invented one.

**5.6 Confidence intervals, not just p-values.**
Report every matchup as `share ± 95% CI`. An interval says how big the effect might be; a
p-value only says whether it is distinguishable from zero.

**5.7 Why Weis, Stöck and the match bonus are switched off when measuring.**
They add large, luck-driven swings that drown the difference between two agents. Note that
they are *on* for human play — measurement conditions and playing conditions differ
deliberately, and saying so pre-empts the obvious objection.

**5.8 The baseline ladder, and what the top rung means.**
random → greedy → rule-based → DMCTS(small) → DMCTS(large) → cheating MCTS. Two things to
draw out:
- **Greedy scores about the same as random** in our measurements. Good illustration that a
  plausible-sounding heuristic can be worth nothing, and a reason to keep dumb baselines.
- **The cheating bot sees every hand**, so the gap between it and the real agent is the
  price of playing with hidden information — the part no amount of extra search can fix.
  Our current measurement puts that at roughly 7.5 points of share. This is the most
  interesting number on the page and it should be the headline of the section.

**5.9 Against humans.**
When there is data. Until then, say there is none, and cite what the published research
found for this exact variant (parity with strong amateurs) rather than implying our numbers
transfer. Design the round-logging for this now so the data exists later.

**Optional:** convert the ladder into Elo-style ratings. Nice for a single headline number,
but it hides the pairwise detail and assumes transitivity that card-game agents often
violate. Include only alongside the raw matchups, never instead.

---

## 6. `/internals` — the developer's page

Mostly assembly. Order:

1. Architecture diagram: browser → web → engine → bots, with the observation boundary drawn
   as the security perimeter it is.
2. The engine: bitboards, why, and the measured throughput.
3. Why the search is Rust — the profile, the 73/27 rollout/tree split, the Amdahl argument,
   and the corpus arithmetic that made it necessary. Already written up in
   `docs/plan-review.md` §1; this is a rewrite for an outside reader.
4. DMCTS: determinization, void constraints, UCT, aggregation across determinizations.
5. The exact endgame solver, including *why it replaces the search rather than running at
   every leaf* — a nice, concrete cost-driven design decision.
6. The three rules that make Jass different, since they are what a reader with
   Bridge/Hearts intuition will get wrong.
7. Determinism and replay: one game seed, derived per-decision seeds, bit-for-bit replay.
8. Testing: the independent reference implementation, property tests, mutation results.

---

## 7. Honesty constraints — not optional

The failure mode for this kind of page is overclaiming, and it is worse than saying nothing.

- **Do not imply superhuman play.** The published result for this variant is *parity* with
  strong amateurs. Our own agent has never been measured against a human.
- **State the known weakness.** The bot's individual card play is much stronger than its
  team play; it does not follow human signalling conventions. Research participants noticed
  exactly this. A player who reads it up front experiences a documented limitation instead
  of a broken partner.
- **Every claim carries its `n` and its date.**
- **Say what was measured with Weis off.**

---

## 8. The leak constraint — a real security issue for this feature

A "why did it play that?" panel is a hidden-state disclosure channel. The search trace names
the cards the bot imagined in other hands, and its per-candidate scores leak information
about the real ones.

Therefore:

- Traces render **after the round ends**, never during. Same rule as the debug panel
  (`PLAN.md` §6, threat T2).
- The mid-game endpoint gets the same CI assertion as the observation builder: no unseen
  card identifier in the response.
- The `/how-it-works` replay uses the *finished* round, so it is safe by construction — but
  it must read from a post-round endpoint, not from live game state.

Getting this wrong turns the documentation feature into a cheat button.

---

## 8b. Visualisations

The statistics sections are the reason this page exists, and statistics prose without
pictures does not land. Each figure below earns its place by showing something a sentence
cannot.

**Rules that apply to all of them:**

- **Inline SVG, hand-written, animated with CSS or a short `requestAnimationFrame` loop.**
  No chart framework. These are six bespoke figures, not a dashboard, and a charting
  library would be more code than the figures. This matches the frontend approach in
  `PLAN.md` §5.1 — vanilla, small, no framework fight.
- **Motion must carry the argument, never decorate it.** If the figure reads the same when
  paused, it should be static.
- **Every animated figure has a static end state** and renders correctly under
  `prefers-reduced-motion`, which is also what makes it screenshot-able.
- **Play on scroll-into-view, with a replay control.** Never loop indefinitely — a looping
  animation beside body text is unreadable.
- **Theme-aware and colourblind-safe.** Never encode a claim in hue alone; pair colour with
  position, shape or a label.

### The six figures

**1. Deal luck vs skill — the case for double rounds.** *Animated, and the most important
one on the page.* Two histograms of per-deal point share. First the raw one: wide, ~8%
standard deviation, with the true 2% skill difference marked — visibly drowned. Then animate
each deal collapsing into its paired partner, and watch the distribution contract until the
difference separates from zero. This single figure justifies the entire evaluation
methodology and is far more convincing than the paragraph it replaces.

**2. Statistical power curve.** Detectable effect size against number of deals, with our
actual matchups plotted on it. Marks why n=60 could not resolve a 16× budget difference.
Interactive: drag `n`, watch the resolvable effect move. Static fallback is the same curve
with three labelled points.

**3. Ladder forest plot.** Each matchup as a point with its 95% CI, a vertical line at 50%.
Intervals crossing the line are visibly inconclusive — which is the honest way to present
greedy-vs-random rather than a bar chart implying a result. No animation needed.

**4. The search, animated.** The most compelling figure for a lay reader. One real position;
determinizations deal the unseen cards over and over (cards flickering into different hands),
each producing a vote, votes accumulating into a bar per candidate card, converging as the
count rises. Shows sampling, aggregation and convergence in one object, and uses real trace
data from an actual decision rather than a mock-up.

**5. Void inference.** A 4×9 card grid per opponent. As the replay steps through tricks,
cells grey out as they are ruled out. Include the Puur case explicitly — the trump suit
greys out *except* the Jack — because that is the moment the viewer realises the inference
is precise rather than approximate.

**6. Throughput, Python vs Rust.** A simple bar pair, log scale, with the consequence
spelled out underneath in wall-clock time rather than ops/sec: 33 days against 1.5 days for
one training corpus. The units people feel.

### Where the data comes from

Figures 3, 4 and 5 render from real artifacts — the ladder JSON of §3, and recorded search
traces and void inferences from a real round. Nothing is drawn from invented numbers. A
figure built on mock data will eventually be mistaken for evidence, including by us.

---

## 9. Resources to cite

Already collected in `PLAN.md` §10; the docs should cite them inline rather than in a dump
at the end. The ones that matter for `/strength` and `/internals`:

- Niklaus, *JassTheRipper* (MSc, Fribourg 2019) — the DMCTS results and human comparison
- Niklaus et al., *Survey of AI for Card Games and Its Application to the Swiss Game Jass*,
  SDS 2019
- Cowling, Powley & Whitehouse, *Information Set Monte Carlo Tree Search*, 2012
- Browne et al., *A Survey of Monte Carlo Tree Search Methods*, 2012
- pagat.com Schieber and Swiss Jass pages; Swisslos rules — for the rules documentation
- For the team-play discussion: the Hanabi zero-shot-coordination literature (Hu et al.,
  *"Other-Play" for Zero-Shot Coordination*, 2020), which is the clearest published account
  of why self-play agents develop conventions their human partners cannot read

---

## 10. Status

**Built**, as three tabs behind the hamburger rather than three routes — the app is a single
screen, so a panel is the right shape.

- `docs/measurements.json` is the artifact. Both builds read it; neither types a number into
  prose. `web/app.py` copies it in at startup and `scripts/make_site.py` copies it into the
  static build, so the two cannot drift.
- Four figures, hand-written inline SVG: the ladder as a forest plot with confidence
  intervals, the saturation curve, the void-inference walkthrough, and throughput.
- The honesty constraints of §7 are in the copy: no claim of superhuman play, the team-play
  weakness stated up front, every figure carrying its date and `n`, and the offline build's
  "all four hands are in this tab" caveat said plainly.

Still outstanding: `arena/ladder.py --json` so the artifact regenerates from a run rather
than being hand-maintained, and the replay viewer with per-decision traces (M6).

## 11. Effort

Roughly a week of work, most of it writing rather than code — assuming the replay viewer is
counted under M6 where it already lives. The data pipeline is an hour. The statistics
sections are the slowest part to write well and the most valuable, because almost nobody
does them properly.
