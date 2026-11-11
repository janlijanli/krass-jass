# jass-bot (tramasys): C++ DL4G bot, 2026

- **Source:** github.com/tramasys/jass-bot @ efcc3bb (2026-09-22).
- **Licence:** **none**: no licence file, so all rights are reserved. It runs locally as an opponent
  only, as its own binary, spoken to over HTTP.
- **Runnable:** yes once compiled. It has no weights. It needs CMake >= 3.30 (PyPI `cmake` works),
  C++26, and cpp-httplib and nlohmann/json, which CMake fetches with pinned hashes. The Dockerfile uses
  clang-22. Whether g++ 13 or clang 18 here accepts `-std=c++26` for this code is untested.
- **Status: not built, not measured.** The session's permission classifier refused to compile it
  (see `README.md`).

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
cd /home/user/ext/jass-bot
/home/user/ext/venvs/build/bin/cmake --preset release   # or: -S . -B build/release -G Ninja -DCMAKE_BUILD_TYPE=Release
/home/user/ext/venvs/build/bin/cmake --build --preset release -j 2
cd /home/user/krass-jass
python -m arena.opponents.jasskit --bot jass-bot --deals 400 --seed 1 --start 1 --workers 4
python -m arena.opponents.jasskit --report .runs/opp-jass-bot-1-shipped.jsonl
```

The server accepts `/action_trump` and `/action_play_card` at the root (V0.2), and the runner calls
those. Its parser rebuilds every trick leader from the dealer and the cards and rejects a mismatch,
so a seat-mapping error would surface as errors, not as quiet misplay.

## Numbers

None yet.
