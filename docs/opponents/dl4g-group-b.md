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
| [theoliver7](theoliver7.md) | DMCTS, C++ kernel, 100 x 0.9 s on all cores; DNN trump | none | needs jasscpp built; not run | — | | |
| [FAIKUE](faikue.md) | threaded DMCTS 9 s, broken sampler; jass-kit 1.0 API | none | needs a v1 bridge; not run | — | | |
| [TedMANNERs](tedmanners.md) | ISMCTS, rule-based rollouts, 5 s | GPL-3.0 | set up; not run | — | | |
| [xXTime-OnXx](xxtime.md) | heuristics + one-world flat MC, 9.5 s | none | set up; not run | — | | |
| [Nolonar](nolonar.md) | casualT flat MC 9 s / specialT play network | none | set up; not run | — | | |

Ranked by what they are, strongest-looking first: theoliver7 (real DMCTS with a fast kernel),
TedMANNERs (true ISMCTS, heuristic rollouts), FAIKUE (DMCTS but inconsistent worlds), then the
flat Monte Carlo bots (xXTime, Nolonar casualT, Mcapozzolo), the policy networks (Rico, Nolonar
specialT) and the broken or greedy ones (RubenNunez, sobrinth).

**Why five were not run.** After the first four had been started, this session's permission
classifier refused to execute further opponent code ("Code from External"), twice. They are
triaged from source; the `tf` venv and registry entries for TedMANNERs, xXTime and Nolonar exist
and only need to be run, e.g. `python -m arena.opponents.run --opponent tedmanners --deals 100`.

## Findings that apply to every jass-kit bot

- **Undertrump.** jass-kit does not forbid undertrumping when the player could follow suit or
  discard instead; our engine applies the strict rule. It showed up in 1-2 of ~3,600 moves per
  run as a legal-set mismatch; sobrinth once played such a card (logged, our fallback played).
- **Multipliers.** Their bots were written for raw points; our `EVAL` keeps 1/1/2/2/3/4. Their
  trump choice ignores that — in our favour.
- **Shoving.** Three of the four measured bots never shove (Rico's and Mcapozzolo's shove tests
  can never fire; RubenNunez avoids it). Ours shoves in 61% of forehand hands.

## Diagnosis

All four are clear wins (> 60%), so the per-contract split is in each file rather than a hunt
for a leak. Two observations worth passing on:

- The networks and flat MC bots hold their own contracts roughly level with us (we take 47-56%
  when they declare); the gap is mostly in our contracts (we keep 71-78%).
- Deal 58 is our worst deal against both Rico and Mcapozzolo: forehand shoves five spades without
  the Jack, the forced partner calls Undenufe x4 and loses ~130:500. Across the four runs shoved
  contracts are weaker in proportion at every multiplier, so it reads as one bad hand, not a
  pattern; it is the deal to replay for the forced-partner choice.
