# Rico-Uttinger/DL4G — "MaxOnnxNeuronAgent2": a policy network

**Result: our bot takes 60.5% ± 12.6% of the points (n = 100 deals, p < 1e-15).** The strongest
of the four group-B bots measured, and the only one with clean play: no illegal cards, no errors.

- Source: github.com/Rico-Uttinger/DL4G @ `88a940e` (2026-01-12).
- Licence: **none** (no licence file): all rights reserved. Run locally as an opponent only.
- Weights: present, `data/card_model_v5/v6/v7.onnx` (434 kB each). Training data is not in the
  repo (`BrushData.py` converts HSLU/Swisslos logs that are not included).

## What it plays

- **Card play:** a dense network, 120 inputs (trump one-hot, hand, seat, dealer, declarer, the set
  of played cards, the set of current-trick cards) to 36 outputs; masked to jass-kit's legal cards,
  argmax. No search. `MaxOnnxNeuronAgent2` uses `card_model_v7.onnx`; their own arena script plays
  it against v6. The input has no order of play and no per-seat history, so it cannot read voids.
- **Trump:** Graf's table (the HSLU exercise's trump/no-trump/Obenabe/Undenufe scores), best
  contract. It shoves only when `player == dealer`, which never happens for forehand, so it
  **never shoves** (0 of 100) — and its shove code would be `PUSH_ALT` (6).
- Rules: jass-kit 2.0.5 (pip).

## How it was run

    # venv: $OPPONENTS_DIR/venvs/light (Python 3.12, numpy 2, jass-kit 2.0.5, onnxruntime)
    python -m arena.opponents.run --opponent rico --deals 100 --seed 1 --workers 3
    python -m arena.opponents.run --diagnose .runs/opp-rico-1-shipped.jsonl

Our bot `build([], 153_600, EVAL)`, `EVAL` rules, double rounds, same seed both halves, paired
test. 19 minutes on 3 workers. Not extended to 400: ten standard errors clear of 50%.

## Numbers

| | |
|---|---|
| our share | **60.52%** ± 12.58% (std), se 1.26% |
| deals | 100 |
| p | < 1e-15 |
| illegal cards / fallbacks / mapping mismatches | 0 / 0 / 0 |

| | rounds | our share |
|---|---:|---:|
| we declare | 100 | 71.0% |
| they declare | 100 | 46.9% |
| they declare a suit | 80 | 42-47% |
| they declare Obenabe | 20 | 52.5% |
| we shove (61%), partner declares | 61 | 68.9% |
| we declare from forehand | 39 | 74.1% |

So against the network we keep ~71% of our own contracts and lose only ~53:47 on theirs: card play
is comfortably ahead on both sides.

Worst deals, for whoever wants to replay them (seed 1):

- deal 58 (23.8%): they Spades, we lose 63:94; then **we Undenufe (shoved), 124:504** — a x4
  contract taken by the side that did not choose it. The single largest loss in the run, and worth
  a look at why the partner called Undenufe on that hand.
- deal 89 (23.6%): we Spades (shoved) 61:96; they Hearts 50:264.
- deal 66 (40.3%): they Obenabe 42:429.
