# Other people's Jass bots against ours

One file per opponent in this directory; the triage of each group:

- [challenge-era.md](challenge-era.md) — the Zühlke Jass Challenge bots (DonaldTrumpf, pyschieber, …)
- [dl4g-group-a.md](dl4g-group-a.md) — HSLU DL4G student bots, group A, and the shared jass-kit bridge
- [others.md](others.md) — reinforcement-learning and supervised bots (luegl/JassAI, …)
- [jass-mu-zero.md](jass-mu-zero.md) — MuZero (HSLU)
- JassTheRipper (Fribourg/HSLU MCTS): `arena/jass_the_ripper.py`, results in `docs/measurements.md`

## Results so far

Our shipped bot (153,600 iterations) against each, double rounds, same seed both halves, paired test.
`EVAL` = Weis, Stöck and match bonus off, our multipliers; `flat` = every contract x1.

| opponent | what it is | rules | our share | n |
|---|---|---|---|---|
| sobrinth (DL4G) | greedy | EVAL | 74.2% | 100 |
| RubenNunez (DL4G) | 15 random rollouts | EVAL | 67.1% | 100 |
| DonaldTrumpf | rule-based, 4th Zühlke 2017 | EVAL | 66.95% ± 12.5 | 400 |
| Mcapozzolo (DL4G) | flat UCB Monte Carlo | EVAL | 62.9% | 100 |
| pyschieber ChallengePlayer | rule-based, card counting | EVAL | 62.4% ± 11.4 | 400 |
| dl4g_hslu (DL4G) | root-parallel ISMCTS | EVAL | 60.5% | 100 |
| Rico-Uttinger (DL4G) | policy network | EVAL | 60.5% | 100 |
| JassTheRipper | DMCTS, Fribourg/HSLU | EVAL | 54.88% ± 10.5 | 400 |
| jass-mu-zero | MuZero, HSLU | EVAL | 55.32% ± 11.0 | 100 |
| jass-mu-zero | MuZero, HSLU | flat | 51.86% ± 10.7 | 400 |
| JassFormer v2 (jberclaz) | transformer, imitation + self-play | chibre (theirs) | 50.88% ± 8.3 | 400 |
| JassFormer v2, their bidding for both | card play only | chibre | 51.82% ± 6.2 | 400 |

All significant. **Every one points at the same place: our trump selection** — our margin is in the
rounds we declare, we call Obenabe/Undenufe far more often than any of them (43% of halves against
MuZero's 12%) and take less there than in suits, our worst deals are shoved no-trump calls, and with
other multiplier tables our forehand shoves 74–78%. Card play alone beats the strongest learned
opponent by ~2 points (JassFormer, same contract both teams). The trump weights were fitted against our
own bot under one multiplier table (§5n); refitting them against the opponents' scoring is next.

Results, one line per run: `arena/opponents/results.jsonl`.
