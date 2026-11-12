# JassTheRipper (Joel Niklaus, Fribourg/HSLU)

Determinized MCTS with domain knowledge and rule-based trump choice, from the master's thesis
this project's research section cites (github.com/JoelNiklaus/JassTheRipper). **No licence file**:
run locally as an opponent only, over its own REST server; nothing of it is in this repository.

## How it is run

Built with JDK 11 (Gradle 5.4.1 wrapper), *run* on Java 8 — its REST server needs `javax.xml.bind`,
which Java 11 removed:

    cd JassTheRipper && ./gradlew installDist -x test          # JDK 11, LC_ALL=C.UTF-8
    java -cp "build/install/JassTheRipper/lib/*" to.joeli.jass.client.rest.Server   # Java 8, port 80
    python -m arena.jass_the_ripper --deals 400 --seed 1

Endpoint `runs-100000`: `RunMode.RUNS` at `StrengthLevel.HSLU_SERVER` — a fixed budget per move, the
configuration it played the HSLU tournament server with — and rule-based trump.

- **Not thread-safe.** Concurrent requests corrupt each other's search (it answered with cards from
  another request's hand). Every call goes through one file lock; it still uses all cores inside a move.
- **Its own bug, ~0.5% of searches:** "The current player's cards are empty" in a playout; it then plays a
  random legal card. 52 of 11,132 searches in the run below.
- Seat mapping (HSLU numbering, -s mod 4, dealer the seat after forehand) is checked by its own server
  on every move; 0 illegal cards in 400 deals.

## Numbers

`EVAL` rules, double rounds, same seed both halves, paired test, our shipped bot (40 x 3,840):

| | share | n | p |
|---|---|---|---|
| shipped vs JassTheRipper/runs-100000 | **54.88% ± 10.51** | 400 | ≈ 0 |

| beliefs off | 53.86% ± 10.99 | 400 | |
| tree policy off | 54.36% ± 11.35 | 400 | |

Paired by deal: beliefs are worth **+1.02 ± 0.51** (p = 0.047) against it, the tree policy +0.52 ± 0.47
(p = 0.27) — `docs/measurements.md` §5z. Fallbacks: 149 of 31,787 searches (0.47%).
