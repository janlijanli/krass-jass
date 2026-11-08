"""What each Coiffeur game is worth to the team that chooses it — step 1 of `docs/coiffeur-plan.md`.

`arena/contracts.py` prices the Schieber's six calls; this prices every game a Coiffeur chooser
can name: the six contracts, the Tutti, the two Slaloms, the two Guschtis, the six 3×3 openings and
the two Misères, the Mitte. (The 2026-10-31 run predates the Tutti, the 2026-11-01 run the Mitte;
`arena/fit_coiffeur.py` reads the games a file holds by name, and `--games` prices a new row alone.) Same method: hold the chooser's hand, deal the other 27 cards at random several times,
play each game out with the real card-play bot, and store what the choosing team writes.

**The label** is what goes on the sheet before the row's multiplier — the choosing team's card
points, or for a Misère the opponents' — in full rather than in tens, so a fit is not rounded
twice. A 3×3's later blocks are named during the round by whoever leads tricks 4 and 7, with the
bots' rule (`coiffeur_select.choose_block`), exactly as in a game.

The chooser leads, as in the Coiffeur. Nothing in card play reads who chose except the bid model,
which is off in the Coiffeur, so a hand's value does not depend on which seat holds it.

Usage::

    python -m arena.coiffeur_contracts generate --hands 2000 --deals 4 --out coiffeur_games.npz
    python -m arena.coiffeur_contracts summary coiffeur_games.npz
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from krass_jass.agent import DmctsAgent  # noqa: E402
from krass_jass.coiffeur_select import choose_block  # noqa: E402
from krass_jass.observation import build_observation, derive_decision_seed  # noqa: E402
from krass_jass.rules import COIFFEUR, Contract, RulesConfig  # noqa: E402
from krass_jass.schedule import Schedule, for_row  # noqa: E402
from krass_jass.state import RoundState  # noqa: E402

#: Every game a chooser can name with a fresh sheet, in a fixed order: the six contracts (as
#: `None`), then each extra row's games.
GAMES: list[tuple[str, Contract, Schedule | None]] = [(c.name, c, None) for c in Contract] + [
    (s.name, s.count, s) for row in ("TUTTI", "SLALOM", "GUSCHTI", "TRIO", "MISERE", "MITTE") for s in for_row(row, COIFFEUR)
]

#: The Coiffeur as played — no Weis, no Stöck, the match bonus on — scored in full points.
LABEL_CFG: RulesConfig = COIFFEUR.variant(coiffeur_tens=False)


def label_agent(iterations: int) -> DmctsAgent:
    """The card player that prices the games: the search at a reduced budget, as §5n priced the
    Schieber's calls — the bid model off (it is the Schieber's) and the tree policy off (it costs
    ~11x a move, and 18 games a deal is already 18 rounds)."""
    return DmctsAgent(
        determinizations=40,
        iterations=max(1, iterations // 40),
        cfg=LABEL_CFG,
        read_bidding=False,
        bid_alpha=0.0,
        tree_policy=False,
        label="coiffeur-labeller",
    )


def play_game(hands: list[int], game: tuple, agent: DmctsAgent, game_seed: int) -> int:
    """One round of `game` with seat 0 choosing and leading. Returns what seat 0's team writes,
    in points, before the row's multiplier."""
    name, contract, schedule = game
    st = RoundState(
        contract=contract, hands=list(hands), cfg=LABEL_CFG, leader=0,
        schedule=schedule.tricks if schedule is not None else None,
        tutti=schedule is not None and schedule.led,
    )
    misere = schedule is not None and schedule.misere
    while not st.done:
        if st.block_pending:
            st.set_block(choose_block(st.hands[st.to_play], st.block_options(), LABEL_CFG))
        seat = st.to_play
        obs = build_observation(
            st, seat, declarer_seat=0, misere=misere,
            decision_seed=derive_decision_seed(game_seed, "coiffeur-games", seat, 0, len(st.tricks_played)),
        )
        st.play(agent.decide(obs))
    total = st.score(weis=(0, 0), stoeck=(0, 0)).total
    return total[1] if misere else total[0]


def _deal(seed: int, hand_index: int, deals: int) -> tuple[int, list[list[int]]]:
    """A chooser's hand and `deals` completions of the other 27 cards, from `(seed, index)`."""
    rng = random.Random(f"coiffeur-games:{seed}:{hand_index}")
    deck = list(range(36))
    rng.shuffle(deck)
    own, rest = deck[:9], deck[9:]
    hand = sum(1 << c for c in own)
    out = []
    for _ in range(deals):
        rng.shuffle(rest)
        out.append([hand] + [sum(1 << c for c in rest[i * 9 : (i + 1) * 9]) for i in range(3)])
    return hand, out


def _label_chunk(args) -> list[tuple[int, int, list[int], list[int]]]:
    seed, indices, deals, iterations, names = args
    games = [g for g in GAMES if g[0] in names]
    agent = label_agent(iterations)
    rows = []
    for h in indices:
        _, completions = _deal(seed, h, deals)
        for k, hands in enumerate(completions):
            # Common random numbers: every game on this deal shares the decision seeds.
            game_seed = seed * 1_000_003 + h * 64 + k
            rows.append((h, k, hands, [play_game(hands, g, agent, game_seed) for g in games]))
    return rows


def generate(
    hands: int, deals: int, seed: int, iterations: int, workers: int, out: Path, names: list[str] | None = None,
    first: int = 0,
) -> None:
    """`names`: price only these games (all by default) — a new row is priced on its own.
    `first`: start at this hand index, so a long run can be done in pieces (`merge` joins them);
    every hand is dealt from `(seed, index)`, so the pieces are exactly the one run."""
    names = names or [g[0] for g in GAMES]
    games = [g for g in GAMES if g[0] in names]
    workers = max(1, min(workers, hands))
    chunks = [list(range(first + i, first + hands, workers)) for i in range(workers)]
    started = time.time()
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for part in pool.map(_label_chunk, [(seed, c, deals, iterations, names) for c in chunks if c]):
            rows.extend(part)
    rows.sort(key=lambda r: (r[0], r[1]))
    np.savez_compressed(
        out,
        hand_index=np.array([r[0] for r in rows], dtype=np.int32),
        hands=np.array([r[2] for r in rows], dtype=np.uint64),
        values=np.array([r[3] for r in rows], dtype=np.float64),
        games=np.array([g[0] for g in games]),
        seed=seed,
        iterations=iterations,
    )
    print(f"wrote {len(rows)} deals ({hands} hands x {deals}) x {len(games)} games to {out} "
          f"in {time.time() - started:.0f}s")


def merge(parts: list[Path], out: Path) -> None:
    """Join pieces of one run (`generate --first`) into one file, in hand order."""
    loaded = [np.load(p) for p in parts]
    games = [list(map(str, d["games"])) for d in loaded]
    if any(g != games[0] for g in games) or len({int(d["seed"]) for d in loaded}) != 1:
        raise SystemExit("pieces differ in games or seed")
    order = np.argsort(np.concatenate([d["hand_index"] for d in loaded]), kind="stable")
    cat = lambda key: np.concatenate([d[key] for d in loaded])[order]  # noqa: E731
    np.savez_compressed(out, hand_index=cat("hand_index"), hands=cat("hands"), values=cat("values"),
                        games=loaded[0]["games"], seed=loaded[0]["seed"], iterations=loaded[0]["iterations"])
    print(f"merged {len(parts)} pieces, {len(order)} deals, into {out}")


def summary(path: Path) -> None:
    """Mean label per game and how often each is the hand's best — the first look at the data."""
    data = np.load(path)
    values, games = data["values"], [str(g) for g in data["games"]]
    best = values.argmax(axis=1)
    print(f"{len(values)} deals, {len(games)} games")
    for i, g in enumerate(games):
        col = values[:, i]
        print(f"{g:20s} mean {col.mean():6.1f}  sd {col.std():5.1f}  best {np.mean(best == i):5.1%}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--hands", type=int, default=2000)
    g.add_argument("--deals", type=int, default=4)
    g.add_argument("--seed", type=int, default=1)
    g.add_argument("--iterations", type=int, default=2400)
    g.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    g.add_argument("--out", type=Path, required=True)
    g.add_argument("--games", default="", help="comma-separated game names; all by default")
    g.add_argument("--first", type=int, default=0, help="first hand index (for a run in pieces)")
    mg = sub.add_parser("merge")
    mg.add_argument("parts", type=Path, nargs="+")
    mg.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("summary")
    s.add_argument("path", type=Path)
    args = ap.parse_args()
    if args.cmd == "generate":
        names = [n.strip().upper() for n in args.games.split(",") if n.strip()] or None
        generate(args.hands, args.deals, args.seed, args.iterations, args.workers, args.out, names, args.first)
    elif args.cmd == "merge":
        merge(args.parts, args.out)
    else:
        summary(args.path)


if __name__ == "__main__":
    main()
