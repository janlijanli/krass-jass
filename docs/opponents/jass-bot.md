# jass-bot (tramasys): C++ DL4G bot, 2026

- **Source:** github.com/tramasys/jass-bot @ efcc3bb (2026-09-22).
- **Licence:** **none**: no licence file, so all rights are reserved. It runs locally as an opponent
  only, as its own binary, spoken to over HTTP.
- **Runnable:** yes, compiled here with clang 18 (`-std=c++2c`; the Dockerfile uses clang-22). It has
  no weights. It needs CMake >= 3.30 (PyPI `cmake`) and cpp-httplib v0.57.1 and nlohmann/json v3.12.0,
  cloned at those tags because the proxy blocks the tarball host. The build changes nothing in their
  source; only the copy's CMake standard line differs, to let the flag through.
- **Status: measured, 2026-11-12.** Our bot wins clearly: **65.5% ± 12.0%, n = 200, p < 1e-15**.

## What it plays

The only strategy, `baseline` (`src/strategies/baseline.cpp`), with `first_legal` as a debug option:

- **Trump:** a weighted card count per contract. Trump weights J 30, 9 22, A 15, K 10, ... The
  plain-suit weights are for side aces and kings. Obe and Une use a high-card table. It adds
  `2*len*(len-1)` for trump length and +10 for J+9. It pushes from forehand below 65.
- **Cards:** one ply, no search, no memory of the play beyond the cards seen. When leading, it plays
  the top remaining card of a suit (a "Bock") if it holds one, else its cheapest card. When the
  partner is winning and it plays last, it schmiers its most valuable card. When it can beat the
  trick, it beats it with the cheapest winning card. Otherwise it plays its cheapest card.
- **Rules:** its own `legal_cards`. The protocol layer checks its own answer for legality, and our
  engine re-checks it. No Weis.

It is a "greedy+" bot: stronger than our `GreedyAgent` (it knows about Bock and schmieren) but
with no lookahead. Expect a large win for us.

## Running it

```sh
# codeload.github.com (CMake's FetchContent) is blocked by the proxy, github.com is not:
git clone --depth 1 -b v0.57.1 https://github.com/yhirose/cpp-httplib /home/user/ext/deps/cpp-httplib
git clone --depth 1 -b v3.12.0 https://github.com/nlohmann/json /home/user/ext/deps/json
# CMake does not know g++ 13's C++26 flag (g++ 13 has none); clang 18 takes -std=c++2c. Build a copy:
cp -r /home/user/ext/jass-bot /home/user/ext/jass-bot-build && cd /home/user/ext/jass-bot-build
sed -i 's/set(CMAKE_CXX_STANDARD 26)/set(CMAKE_CXX_STANDARD 23)/' CMakeLists.txt
/home/user/ext/venvs/build/bin/cmake -S . -B build/release -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=OFF -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_CXX_FLAGS=-std=c++2c \
  -DFETCHCONTENT_SOURCE_DIR_HTTPLIB=/home/user/ext/deps/cpp-httplib -DFETCHCONTENT_SOURCE_DIR_JSON=/home/user/ext/deps/json
/home/user/ext/venvs/build/bin/cmake --build build/release -j 4
cd /home/user/krass-jass
python -m arena.opponents.jasskit --bot jass-bot --deals 400 --seed 1 --start 1 --workers 4
python -m arena.opponents.jasskit --report .runs/opp-jass-bot-1-shipped.jsonl
```

The server accepts `/action_trump` and `/action_play_card` at the root (V0.2), and the runner calls
those. Its parser rebuilds every trick leader from the dealer and the cards and rejects a mismatch,
so a seat-mapping error would surface as errors, not as quiet misplay.

## Numbers

`--deals 200 --start 2 --workers 4`, our shipped bot (40 x 3,840), `EVAL` rules, double rounds on the
same seed:

| | |
|---|---|
| our share of points (multiplied) | **65.47% ± 12.00%**, n = 200, paired p < 1e-15 |
| our share of raw card points | 62.56% |
| our share when we declare / they declare | 76.3% / 49.6% |
| their declarations under 79 raw | 101 of 200 |
| opponent errors / fallbacks, illegal cards | 0, 0 (its own legality check holds) |
| time | 32 min |

200 deals rather than 400: the margin is 18 standard errors, and a larger n would only narrow it.

**Diagnosis.** It loses both ways, as a no-lookahead bot should:

- **Card play.** Defending our contracts it lets us take 115.9 raw points on average (dl4g allows
  110.6, jassager 108.4). It plays one ply, with no picture of the other hands beyond the cards already played.
- **Trump choice.** Half its declarations make under 79: Diamonds 34 of 51, Clubs 24 of 44. It
  shoves from forehand in 31% of rounds (we shove in 56%). **It almost never plays Obenabe or
  Undenufe**: 0 and 4 calls in 200 rounds, against 46 and 56 of ours. Read from the code, not measured: its high-card table for them
  probably rarely beats the trump table's `2*len*(len-1)` length bonus. The four Undenufe it did call made 112
  raw on average.
- Our worst deals are our own shoved Undenufe/Obenabe going down at x4/x3 (deals 58, 9, 36), the same
  thin-Obe/Une pattern noted in `dl4g_hslu.md`. Deal 9: shoved to, we called Obenabe and took 0 of
  471.
