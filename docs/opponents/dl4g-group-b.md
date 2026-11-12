# HSLU DL4G student bots, group B — summary

Nine repositories from HSLU's "Deep Learning for Games" module, all built on Thomas Koller's
jass-kit (GPL-3.0). Each runs in its own venv behind `arena/opponents/jasskit_bridge.py`; nothing
of theirs is imported by our code. Our bot is the shipped one (`build([], 153_600, EVAL)`);
`EVAL` rules, double rounds, same seed for both halves, paired test, seed 1.

| opponent | what it is | licence | runnable? | our share ± std | n | p |
|---|---|---|---|---|---:|---|
| [Rico-Uttinger](rico.md) | ONNX policy network, no search | none | yes | **60.5%** ± 12.6 | 100 | < 1e-15 |
| [Mcapozzolo](mcapozzolo.md) | flat UCB MC, 200 iterations | none | yes (trump model missing) | **62.9%** ± 13.0 | 100 | < 1e-15 |
| [RubenNunez](rubennunez.md) | 15 random rollouts, no world dealt | none | yes, crashes on 23% of moves | **67.1%** ± 12.3 | 100 | < 1e-15 |
| [sobrinth](sobrinth.md) | greedy | GPL-3.0 | yes | **74.2%** ± 11.6 | 100 | < 1e-15 |
| [theoliver7](theoliver7.md) | DMCTS, C++ kernel, 400 x 0.1 s (dmcts5) on all cores; DNN trump | none | yes (jasscpp built, model file repaired) | **62.4%** ± 11.1 (interim) | 49 | 5e-15 |
| [FAIKUE](faikue.md) | threaded DMCTS 9 s, broken sampler; jass-kit 1.0 API | none | yes (v1 bridge, Cython build) | **71.8%** ± 14.0 | 100 | < 1e-15 |
| [TedMANNERs](tedmanners.md) | ISMCTS, rule-based rollouts, 5 s | GPL-3.0 | yes | **70.1%** ± 11.6 | 100 | < 1e-15 |
| [xXTime-OnXx](xxtime.md) | heuristics + one-world flat MC, 9.5 s | none | yes | **65.7%** ± 11.6 | 100 | < 1e-15 |
| [Nolonar casualT](nolonar.md) | flat MC 9 s, illegal rollouts; logistic-regression trump | none | yes | **59.7%** ± 11.3 | 100 | < 1e-15 |
| [Nolonar specialT](nolonar.md) | play network; logistic-regression trump | none | yes | **59.1%** ± 10.5 | 100 | < 1e-15 |

Ranked by what they are, strongest-looking first: theoliver7 (real DMCTS with a fast kernel),
TedMANNERs (true ISMCTS, heuristic rollouts), FAIKUE (DMCTS but inconsistent worlds), then the
flat Monte Carlo bots (xXTime, Nolonar casualT, Mcapozzolo), the policy networks (Rico, Nolonar
specialT) and the broken or greedy ones (RubenNunez, sobrinth).

All nine are measured; theoliver7 is an interim result (49 of 100 deals), stopped by the
owner. Every opponent is a clear loss for its side: the closest are the two Nolonar bots (~59%)
and Rico (60.5%).

## Findings that apply to every jass-kit bot

- **Undertrump.** jass-kit does not forbid undertrumping when the player could follow suit or
  discard instead; our engine applies the strict rule. It showed up in 1-2 of ~3,600 moves per
  run as a legal-set mismatch; sobrinth once played such a card (logged, our fallback played).
- **Multipliers.** Their bots were written for raw points; our `EVAL` keeps 1/1/2/2/3/4. Their
  trump choice ignores that — in our favour.
- **Shoving.** Five of the nine never shove (Rico, Mcapozzolo, RubenNunez, xXTime, theoliver7).
  TedMANNERs and Nolonar shove at about our rate (61-63%), FAIKUE 29%. Ours shoves in 61%.

## Diagnosis

None is at or below 52%, so the per-contract split is in each file rather than a hunt for a leak.
What carries over:

- **The gap is in our contracts.** We keep 71-83% of the points when we declare, against every
  opponent. In their contracts we take 47-63%.
- **Nolonar's trump choice is the best of the group.** It is the only opponent that wins its own
  contracts clearly (we take 42%), with a play network (specialT, 59.1%) as with a 9 s search
  (casualT, 59.7%): same trump model, same result. Its logistic-regression trump is the thing
  in this group worth a look.
- **Deal 58** (seed 1) is our worst or near-worst deal against Rico, Mcapozzolo, Nolonar casualT
  and FAIKUE: forehand shoves five spades without the Jack, our forced partner calls Undenufe x4 and
  loses ~124:504. Across all runs shoved contracts are weaker in proportion at every multiplier,
  so it reads as one bad hand, not a pattern; it is the deal to replay for the forced-partner
  choice.
- **Rules difference.** jass-kit allows the undertrump; 0-2 mismatches per run, two illegal cards
  in ~30,000 of their moves (sobrinth, Nolonar specialT), both replaced by our fallback card.
