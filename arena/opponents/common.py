"""Shared plumbing for seating external bots at our table: a line-protocol bridge to a bot in its
own process, a logged double round, and the run / resume / report command line every opponent uses.

The pattern is `arena/jass_the_ripper.py`'s: our engine deals, asks for moves and stays
authoritative; every card an opponent returns is checked against our legal moves, an illegal one
is logged and our lowest legal card is played instead; per-deal results go to a resumable
JSON-lines file; two arms on one seed compare deal by deal.

What this adds is the per-half record (contract, which side chose it, whether it was shoved, both
sides' points), because a share alone cannot say *where* a match was won or lost.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from arena.ab import build  # noqa: E402
from arena.arena import choose_contract, deal_spec, paired_test, resolve_weis  # noqa: E402
from krass_jass.agent import Agent  # noqa: E402
from krass_jass.cards import RANK_CHARS, SUIT_CHARS, card_list, card_rank, card_suit  # noqa: E402
from krass_jass.observation import build_observation, derive_decision_seed  # noqa: E402
from krass_jass.rules import EVAL, HOUSE, Contract, RulesConfig  # noqa: E402
from krass_jass.state import RoundState  # noqa: E402

CFGS = {"eval": EVAL, "house": HOUSE.variant(target_score=None)}
RESULTS = Path(__file__).resolve().parent / "results.jsonl"
EXT = Path(os.environ.get("KJ_EXT", "/home/user/ext"))

# -- the webplatformz/challenge card and game-type vocabulary --------------------------------

COLORS = {"D": "DIAMONDS", "H": "HEARTS", "S": "SPADES", "C": "CLUBS"}
SUIT_OF_COLOR = {v: SUIT_CHARS.index(k) for k, v in COLORS.items()}


def ch_card(c: int) -> dict:
    """Our card index as a challenge card: number 6..14 (11 Jack, 14 Ace), colour name."""
    return {"number": 14 - card_rank(c), "color": COLORS[SUIT_CHARS[card_suit(c)]]}


def our_card_ch(card: dict) -> int:
    return SUIT_OF_COLOR[card["color"]] * 9 + (14 - int(card["number"]))


def ch_game_type(contract: Contract) -> dict:
    if contract.is_trump:
        return {"mode": "TRUMPF", "trumpfColor": COLORS[SUIT_CHARS[int(contract)]]}
    return {"mode": "OBEABE" if contract == Contract.OBENABE else "UNDEUFE"}


def our_contract_ch(game_type: dict) -> Contract | str:
    from krass_jass.rules import SHOVE

    mode = game_type["mode"]
    if mode == "TRUMPF":
        return Contract(SUIT_OF_COLOR[game_type["trumpfColor"]])
    if mode == "OBEABE":
        return Contract.OBENABE
    if mode == "UNDEUFE":
        return Contract.UNDENUFE
    if mode == "SCHIEBE":
        return SHOVE
    raise ValueError(f"unknown game type {game_type!r}")


def card_text(c: int) -> str:
    return SUIT_CHARS[card_suit(c)] + RANK_CHARS[card_rank(c)]


# -- what one seat has seen, as a history -----------------------------------------------------

def forehand_of(obs) -> int:
    return obs.tricks_played[0][0] if obs.tricks_played else obs.trick_leader


def dealt_hand(obs) -> int:
    """The nine cards this seat was dealt: what it holds plus what it has played."""
    hand = obs.hand
    for lead, cards in obs.tricks_played:
        for k, c in enumerate(cards):
            if (lead + k) % 4 == obs.seat:
                hand |= 1 << c
    return hand


def trick_winners(obs) -> list[int]:
    """Winner of each completed trick: the next trick's leader, the current leader for the last."""
    leads = [lead for lead, _ in obs.tricks_played] + [obs.trick_leader]
    return leads[1:]


def challenge_history(obs, team_name: str, other_name: str) -> list[dict]:
    """The messages the challenge server would have sent this seat, ending in REQUEST_CARD.

    The protocol names no seats to the client: a bot sees the trick in play order and the name
    of each trick's winner (both seats of a team carry the team's name, as in the challenge). So
    the only mapping to verify is the play order, which is ours (seat lead+k plays k-th).
    """
    msgs: list[dict] = [{"type": "DEAL_CARDS", "data": [ch_card(c) for c in card_list(dealt_hand(obs))]}]
    if obs.declarer_seat != forehand_of(obs):
        msgs.append({"type": "BROADCAST_TRUMPF", "data": {"mode": "SCHIEBE"}})
    msgs.append({"type": "BROADCAST_TRUMPF", "data": ch_game_type(obs.contract)})
    for (lead, cards), winner in zip(obs.tricks_played, trick_winners(obs)):
        table = [ch_card(c) for c in cards]
        for k in range(1, 5):
            msgs.append({"type": "PLAYED_CARDS", "data": table[:k]})
        name = team_name if winner % 2 == obs.seat % 2 else other_name
        msgs.append({"type": "BROADCAST_STICH",
                     "data": {"name": name, "seatId": winner, "playedCards": table}})
    table = [ch_card(c) for c in obs.trick]
    for k in range(1, len(table) + 1):
        msgs.append({"type": "PLAYED_CARDS", "data": table[:k]})
    msgs.append({"type": "REQUEST_CARD", "data": table})
    return msgs


def trumpf_history(hand: int, is_forehand: bool) -> list[dict]:
    msgs: list[dict] = [{"type": "DEAL_CARDS", "data": [ch_card(c) for c in card_list(hand)]}]
    if not is_forehand:
        msgs.append({"type": "BROADCAST_TRUMPF", "data": {"mode": "SCHIEBE"}})
    msgs.append({"type": "REQUEST_TRUMPF", "data": not is_forehand})
    return msgs


# -- a bot in its own process -----------------------------------------------------------------

_BRIDGES: dict[tuple, subprocess.Popen] = {}


def ask(cmd: tuple[str, ...], request, timeout: float = 60.0, cwd: str | None = None):
    """Send one JSON line to a long-lived bridge process (one per command per worker), read one back.

    The bridge holds no state between lines, so one process per worker is safe without a lock.
    A dead or silent bridge raises; the caller logs it and falls back.
    """
    proc = _BRIDGES.get(cmd)
    if proc is None or proc.poll() is not None:
        proc = subprocess.Popen(list(cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, cwd=cwd, bufsize=1)
        _BRIDGES[cmd] = proc
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    ready, _, _ = select.select([proc.stdout], [], [], timeout)
    if not ready:
        proc.kill()
        _BRIDGES.pop(cmd, None)
        raise TimeoutError(f"{cmd[0]} did not answer in {timeout:.0f}s")
    line = proc.stdout.readline()
    if not line:
        _BRIDGES.pop(cmd, None)
        raise RuntimeError(f"{cmd[0]} exited")
    return json.loads(line)


def log_event(path: str, record: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fh:
        fh.write(json.dumps(record) + "\n")


def checked(card: int | None, obs, log: str, why: dict) -> int:
    """Our engine decides what is legal: an illegal or missing card is logged, our lowest legal played."""
    if card is not None and obs.legal_moves >> card & 1:
        return card
    log_event(log, {"kind": "illegal" if card is not None else "error",
                    "card": card_text(card) if card is not None else None,
                    "hand": [card_text(c) for c in card_list(obs.hand)],
                    "trick": [card_text(c) for c in obs.trick],
                    "contract": int(obs.contract), **why})
    return card_list(obs.legal_moves)[-1]


# -- a double round that says what happened ---------------------------------------------------

def play_round_logged(hands, leader, seats, cfg, game_seed, game_id="arena") -> dict:
    """`arena.arena.play_round` with the bidding's outcome kept. Same seeds, same moves, same score."""
    contract, declarer = choose_contract(hands, leader, seats, cfg)
    weis, stoeck, shown, announced = resolve_weis(hands, contract, leader, cfg)
    state = RoundState(contract=contract, hands=list(hands), cfg=cfg, leader=leader)
    trick_no = 0
    while not state.done:
        seat = state.to_play
        obs = build_observation(
            state, seat, declarer_seat=declarer,
            decision_seed=derive_decision_seed(game_seed, game_id, seat, 0, trick_no),
            known_cards=tuple((s, c) for s, c in shown if state.hands[s] & (1 << c)),
            weis_announced=announced,
        )
        state.play(seats[seat].decide(obs))
        trick_no = len(state.tricks_played)
    total = state.score(weis=weis, stoeck=stoeck).total
    return {"contract": int(contract), "declarer": declarer, "shoved": declarer != leader,
            "points": [total[0], total[1]],
            "tricks": [[lead, [card_text(c) for c in cards]] for lead, cards in state.tricks_played]}


def double_round_logged(hands, leader, ours, theirs, cfg, game_seed) -> dict:
    """`arena.arena.double_round`, both halves on the same seed, with each half's record.

    Half 0: we sit 0/2. Half 1: we sit 1/3. `ours` and `theirs` are each side's points.
    """
    halves = []
    for half, seats in enumerate(({0: ours, 2: ours, 1: theirs, 3: theirs},
                                  {0: theirs, 2: theirs, 1: ours, 3: ours})):
        r = play_round_logged(hands, leader, seats, cfg, game_seed)
        us = half  # our team index in this half
        r.update(ours=r["points"][us], theirs=r["points"][1 - us],
                 we_declared=r["declarer"] % 2 == us)
        halves.append(r)
    a = sum(h["ours"] for h in halves)
    b = sum(h["theirs"] for h in halves)
    return {"share": 0.5 if a + b == 0 else a / (a + b), "halves": halves, "leader": leader}


def _deal(args):
    ours, theirs, cfg, seed, index = args
    hands, _, leader, game_seed = deal_spec(seed, index, None)
    t = time.time()
    rec = double_round_logged(hands, leader, ours, theirs, cfg, game_seed)
    rec.update(deal=index, seconds=round(time.time() - t, 1))
    return rec


def load(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {r["deal"]: r for r in rows}


CONTRACT_NAMES = ["DIAMONDS", "HEARTS", "SPADES", "CLUBS", "OBENABE", "UNDENUFE"]


def diagnose(rows: dict[int, dict]) -> str:
    """Where the points went: by who chose, by contract, shove rates, worst deals."""
    lines = []
    halves = [h for r in rows.values() for h in r["halves"]]
    by: dict[tuple, list] = defaultdict(list)
    for h in halves:
        side = "ours" if h["we_declared"] else "theirs"
        by[(side,)].append(h)
        by[(side, CONTRACT_NAMES[h["contract"]])].append(h)
    lines.append("who chose | contract  |    n | our pts | their pts | our share of that half")
    for key in sorted(by, key=lambda k: (k[0], len(k), k[1:] and k[1])):
        hs = by[key]
        o = statistics.fmean(h["ours"] for h in hs)
        t = statistics.fmean(h["theirs"] for h in hs)
        name = key[1] if len(key) > 1 else "all"
        lines.append(f"{key[0]:>9} | {name:<9} | {len(hs):4d} | {o:7.1f} | {t:9.1f} | {o / (o + t):.1%}")
    for side in ("ours", "theirs"):
        hs = by[(side,)]
        if hs:
            lines.append(f"shove rate when {side} chose: {statistics.fmean(h['shoved'] for h in hs):.1%}")
    # Same deal, same seat: who chose in each half tells whether trump choice or play decided it.
    worst = sorted(rows.values(), key=lambda r: r["share"])[:5]
    lines.append("worst deals: " + ", ".join(f"#{r['deal']} {r['share']:.1%}" for r in worst))
    return "\n".join(lines)


def report(paths: list[Path]) -> None:
    arms = [load(p) for p in paths]
    for p, arm in zip(paths, arms):
        shares = [r["share"] for r in arm.values()]
        _, pv = paired_test([s - 0.5 for s in shares])
        print(f"{p.name}: {statistics.fmean(shares):.2%} ± {statistics.stdev(shares):.2%}  "
              f"n={len(shares)}  p={pv:.2e}")
        print(diagnose(arm))
    if len(arms) == 2:
        common = sorted(set(arms[0]) & set(arms[1]))
        diff = [arms[0][i]["share"] - arms[1][i]["share"] for i in common]
        _, pv = paired_test(diff)
        print(f"{paths[0].name} - {paths[1].name}: {statistics.fmean(diff):+.2%} "
              f"± {statistics.stdev(diff) / len(diff) ** 0.5:.2%} (se)  n={len(diff)}  p={pv:.2e}")


def count_lines(path: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    if Path(path).exists():
        for line in Path(path).read_text().splitlines():
            if line.strip():
                counts[json.loads(line).get("kind", "?")] += 1
    return dict(counts)


def main(name: str, make_theirs, extra_args=None) -> None:
    """The command line every opponent module shares. `make_theirs(cfg, args)` builds the agent."""
    ap = argparse.ArgumentParser(prog=f"arena.opponents.{name}")
    ap.add_argument("--deals", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--cfg", choices=sorted(CFGS), default="eval")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--ours", nargs="*", default=[], help="DmctsAgent field=value pairs, as arena.ab")
    ap.add_argument("--out", type=Path, help="per-deal results, one JSON line each; a rerun resumes")
    ap.add_argument("--report", type=Path, nargs="+", help="report one or two --out files and stop")
    ap.add_argument("--no-record", action="store_true", help="do not append to results.jsonl")
    if extra_args:
        extra_args(ap)
    args = ap.parse_args()
    if args.report:
        report(args.report)
        return

    cfg = CFGS[args.cfg]
    ours = build(args.ours, 153_600, cfg)  # 40 x 3,840, as served, unless --ours says otherwise
    theirs = make_theirs(cfg, args)
    out = args.out or Path(f".runs/{name}-{args.seed}-{args.cfg}-{'-'.join(args.ours) or 'shipped'}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    done = load(out)
    todo = [i for i in range(args.deals) if i not in done]
    print(f"{out}: {len(done)} done, {len(todo)} to play", flush=True)
    t = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool, out.open("a") as fh:
        futures = [pool.submit(_deal, (ours, theirs, cfg, args.seed, i)) for i in todo]
        for n, f in enumerate(as_completed(futures), 1):
            fh.write(json.dumps(f.result()) + "\n")
            fh.flush()
            if n % 10 == 0:
                print(f"  {n}/{len(todo)} ({(time.time() - t) / 60:.1f} min)", flush=True)

    rows = load(out)
    rows = {i: r for i, r in rows.items() if i < args.deals}
    shares = [r["share"] for r in rows.values()]
    _, pv = paired_test([s - 0.5 for s in shares])
    mean, std = statistics.fmean(shares), statistics.stdev(shares)
    events = count_lines(theirs.log)
    print(f"{ours.name} vs {theirs.name}: {mean:.2%} ± {std:.2%}  n={len(shares)}  p={pv:.2e}  "
          f"opponent events: {events or 'none'}")
    print(diagnose(rows))
    if args.no_record:
        return
    record = {
        "a": args.ours or ["shipped"], "b": [theirs.name], "deals": len(shares), "seed": args.seed,
        "iterations": ours.determinizations * ours.iterations, "cfg": args.cfg,
        "a_share": mean, "std": std, "p": pv, "se": std / len(shares) ** 0.5,
        "opponent_events": events, "minutes": round((time.time() - t) / 60, 1),
        "when": time.strftime("%Y-%m-%d %H:%M"),
    }
    with RESULTS.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


__all__ = ["Agent", "RulesConfig", "EXT", "ask", "checked", "log_event", "main"]
