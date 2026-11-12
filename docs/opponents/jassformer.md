# Opponent: JassFormer v2 (jberclaz/jass)

**Result (400 deals, double rounds, the same seed for both halves, paired t-test, shipped bot
`build([], 153_600, cfg)`):**

| table | our share | std | n | p | illegal | errors |
|---|---|---|---|---|---|---|
| **chibre** (their rules: suit trumps only, spades ×2) | **50.88%** | 8.34% | 400 | 0.034 | 0 | 0 |
| chibre, JassFormer bids for both teams, our search plays the cards | **51.82%** | 6.23% | 400 | 4.8e-9 | 0 | 0 |
| EVAL (our rules: Obenabe/Undenufe, our multipliers) | 60.50% | 14.55% | 400 | ≈0 | 0 | 0 |

On its own rules we are **above 50 but below 52**. In card play we beat it clearly. The gap is in
**our trump choice under ×1/×2 multipliers**. The EVAL number flatters us: whenever we call
Obenabe or Undenufe, the network is playing a contract it never saw in training.

## What it is

- [github.com/jberclaz/jass](https://github.com/jberclaz/jass), MIT licence (© leflat.com).
  Checked at commit `fd5ed39` (2026-10-23).
- It is a Java Chibre game. Its AI, "JassFormer v2", is a 6-layer transformer (d=256, 4.8M
  parameters). It was trained by imitating a Monte Carlo player, then by two rounds of PPO.
- **The weights are a release asset:**
  - URL: `https://github.com/jberclaz/jass/releases/download/jassformer-v2/jassformer.onnx`
  - sha256: `032533d5296e4a607dc16522eea597bce10fa386343c5d63fa348729ad2e3de8`
- **Strongest shipped configuration:** the network alone, playing its argmax. It has two heads:
  - `card_logits` [36].
  - `trump_logits` [5], where index 4 means pass.
- **Input:** 96 tokens. It needs no search.

## How it is seated

- **Their Java is not run.** Building or running their Maven project was not permitted in this
  environment.
- **What we run instead.** `arena/opponents/jassformer.py` re-implements their state encoding
  (`ArtificialPlayer` / `GameView` / the token builder) in Python, then runs the ONNX file in
  `onnxruntime`. This is an arena-only dependency, and nothing under `krass_jass/` imports it.
- **No code of theirs is in the repo.** The port is our own code, written from their source,
  with attribution in the module docstring (MIT).
- **What the port reproduces:**
  - Seat order: SELF, RIGHT = next to play, ACROSS, LEFT.
  - The card and colour mapping. Theirs is spade/heart/club/diamond with ranks 6..A; ours is D H S C
    with ranks A..6.
  - The belief table:
    - priors of 1/3;
    - a failed follow zeroes the led suit, except the trump Jack;
    - renormalise;
    - top 4 kept above 0.34.
  - Their legality rules.
  - Their argmax tie rule.
- Download the model to `/home/user/ext/jass-model/jassformer.onnx`, or pass `--model`.

```
python -m arena.opponents.jassformer --deals 400 --cfg chibre            # their rules
python -m arena.opponents.jassformer --deals 400 --cfg eval              # our EVAL rules
python -m arena.opponents.jassformer --deals 400 --cfg chibre --our-bid jassformer
python -m arena.opponents.jassformer --report .runs/jassformer-chibre-1-shipped.jsonl [--show 225]
```

A run resumes from its `--out` file. Each finished run appends one line to
`arena/opponents/results.jsonl`.

### Fidelity checks

| Check | Result |
|---|---|
| Card and colour mapping | round-trips |
| Their legal set vs ours | agree on all but one corner in 10,800 decisions (see below) |
| Belief table | never contradicts the true deal |
| Faithful port vs random play | 72.88% |
| Faithful port vs the same network with no beliefs | 50.56% (p = 0.021) |
| Faithful port vs a wrong colour mapping | 57.48% |
| Faithful port vs left/right swapped | 49.92% |
| Faithful port vs teams swapped | 49.99% |

The wrong colour mapping and the left/right swap are deliberate sabotage. The large drop from the
wrong colour mapping shows the encoding matters. The two swaps changing nothing is how their
network treats those positions, not a port error. Speed is about 5 ms a decision on one thread.

## Their rules against `docs/rules-config.md`

| Rule | Theirs | Ours | Notes |
|---|---|---|---|
| Contracts | four suit trumps only | also Obenabe/Undenufe | |
| Multipliers | spades ×2, on everything (tricks, last trick, match 200, Stöck) | our presets | the `chibre` config is `EVAL` with D/H/C ×1, S ×2 |
| Shove | forehand may pass to the partner, who must choose | same | |
| Puur (trump Jack) | exempt from following a trump lead | same | |
| Undertrump | not allowed while holding a higher trump | allowed | applies only in one corner: when the hand holds nothing but trumps, after an overtrump. If their pick is illegal for us, we take its best legal card; it never happened |
| Weis | yes, in their game | off in evaluation, as for every A/B | |
| Scoring unit | single hands from 0–0 | | the per-round share is the right unit |

## Diagnosis (chibre table)

- **Overall.** Declaring, we take 70.5% of the half. Defending, we take 68.2%; JassFormer takes 31.9% of its own declared halves.
- **Card play is strong.** When both teams bid the same contract in the two halves, the
  comparison is pure card play: we take **52.05%** (n=269, p=3.6e-8). With the network bidding for
  both sides, we take 51.82%.
- **Bidding loses.** Where the bids differ we take 48.49% (n=131, p=0.13). The clearest case is
  when we shove and JassFormer keeps the same hand: there we take 47.49% (n=93).
  - **Our shove rate from forehand is 78.2% on this table.** It is 54.5% on EVAL, and JassFormer's
    is 55.5%.
  - **Why.** `krass_jass.trump` scores a contract as (score − baseline) × multiplier, and the shove
    threshold of 3.022 was fitted on our multiplier table. With three suits at ×1, hands that should
    be kept fall under the threshold.
  - **A second effect.** A ×2 multiplies a *negative* edge, so a partner we shove to is steered away
    from spades even when they hold the spade Jack.
- **Annotated deals:**
  - **Deal 225, 24.5%.** Forehand holds C J Q 8 6, H J 8, D A, S A K. Our score for clubs is 2.1
    on this table and 4.2 on EVAL.
    - JassFormer keeps clubs and wins **151–6**.
    - We shove; our partner calls diamonds holding D K 9 6 and loses 71–86.
  - **Deal 270, 20.8%.** JassFormer shoves, and its partner, holding S J 6, calls spades: 294–20.
    Our partner is shoved to with S J 6, C 9 7, and calls clubs: 78–79.
  - **Deal 124, 25.5%.** We shove and our partner calls diamonds: 62–95. JassFormer keeps clubs: 139–18.
- **In the bid arm, the worst deals are all spades.** Doubled stakes widen the swing. This is
  variance, not a pattern.

**For the central decision (this branch does not change our play):** the trump selector's
threshold and weights do not carry over to other multiplier tables. Refitting `fit_trump` per
multiplier preset, or folding the multiplier into the threshold rather than the edge, would
probably close most of the 1-point gap. The card play needs nothing.
