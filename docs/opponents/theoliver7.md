# theoliver7/hslu-dl4g — DMCTS (C++ kernel) + DNN trump

**Interim result, stopped by the owner: our bot takes 62.4% ± 11.1% of the points
(n = 49 of 100 planned deals, p = 5e-15).** No illegal cards, no fallbacks; one mapping mismatch,
the undertrump rules difference.

- Source: github.com/theoliver7/hslu-dl4g @ `0421b80` (2023-11-09).
- Licence: **none** (no licence file): all rights reserved. Run locally as an opponent only.
- Built on jass-kit 2.x (GPL-3.0) and on `jasscpp`, the Python binding of Thomas Koller's
  jass-kit-cpp (github.com/thomas-koller/jass-kit-cpp, public; not on PyPI).

## What it plays

- **Card play:** determinized MCTS. `DeterminizationCppMCTSAgent` deals `determinizations`
  consistent worlds (`HandSampler2`, which respects the number of cards each seat holds), runs a
  perfect-information UCT search in each with the C++ game simulator and random rollouts, and
  sums the root visit counts across worlds. Worlds are spread over `cpu_count() + 1` processes;
  each search runs for `cutoff_time` seconds (time-limited, not iteration-limited). Reward is the
  team's share of the round's points.
- Served configurations (`service/player_service.py`): `dmcts2` 100 worlds x 0.9 s, `dmcts3`
  200 x 0.4 s, `dmcts4` 300 x 0.2 s, `dmcts5` 400 x 0.1 s; the README cites a 30 s decision window.
  On 4 cores `dmcts2` is ~18 s a move.
- A pure-Python `DeterminizationMCTSAgent` (`dmcts0/1`, 100 worlds x 1 s) and an
  `InformationSetMCTSAgent` (1,000-4,000 iterations) are also served.
- **Trump:** a six-layer dense Keras network on hand + forehand flag (`notebooks/models/v1..v8`,
  SavedModel format, Keras 2 — present in the repo). `PUSH` is class 6; as rearhand it takes the
  third-ranked class, not the second (`np.argsort(...)[2]` on a 1-row max) — looks like a bug.
  Without the model it falls back to Graf's trump table, shoving at <= 68.
- Rules: jass-kit's Schieber (no multipliers in their scoring, no Weis).

## How it was run

1. `jasscpp` built from github.com/thomas-koller/jass-kit-cpp (no licence file) with CMake + make
   into `$OPPONENTS_DIR/jass-kit-cpp/build/source/jasscpp.cpython-311-x86_64-linux-gnu.so`,
   outside our repository; the registry puts that directory on the bridge's `sys.path`.
2. The trump model `notebooks/models/v7` has a `keras_metadata.pb` corrupted by CRLF line endings
   at commit time (Keras: parse error). A copy with CRLF -> LF repaired is at
   `$OPPONENTS_DIR/theoliver7-models/v7`; their checkout is untouched. With it the network loads
   (without it the bot silently falls back to the Graf table).
3. Configuration **dmcts5**: 400 worlds x 0.1 s, one of the four it serves. It spreads the worlds
   over `cpu_count() + 1` processes, so it gets the whole machine and runs with one worker. dmcts2
   (100 x 0.9 s) would have been ~2.5x slower.

        # venv: $OPPONENTS_DIR/venvs/old (Python 3.11, numpy 1.23.5, tensorflow-cpu 2.12, jass-kit 2.0.5)
        python -m arena.opponents.run --opponent theoliver7 --deals 100 --seed 1 --workers 1

Our bot `build([], 153_600, EVAL)`, `EVAL` rules, double rounds, same seed both halves, paired
test. ~4.3 min a deal; it spends 111 s a half, ours 18 s. **Stopped by the owner at 49 deals**
(~3.5 h); the run file resumes from there if it is ever wanted.

## Numbers (interim, n = 49)

| | |
|---|---|
| our share | **62.35%** ± 11.06% (std), se 1.58% |
| deals | 49 (of 100 planned; stopped by the owner) |
| p | 5.3e-15 |
| fallbacks / illegal cards | 0 / 0 |
| mapping mismatches | 1 — jass-kit allows an undertrump our strict rule forbids |

| | rounds | our share |
|---|---:|---:|
| we declare | 49 | 73.7% |
| they declare | 49 | 48.1% |

It **never shoved** (0 of 49 forehand hands; the network's shove class never won). Its own
contracts come out level (48% for us), its Obenabe the strongest (34% for us, n = 8). Our own
contracts hold at 74%, as against the other search bots: its card play is a real DMCTS, but at
0.1 s a world it is not close to ours.

Worst deal (36, 38.5%): our shoved partner's Undenufe, 264:364.
