<<<<<<< HEAD
"""Our bot against a jass-kit (HSLU DL4G) bot, double rounds, paired test, per-round diagnosis.

The HSLU "Deep Learning for Games" bots speak jass-kit's interface. Each one runs in its own
process, with its own venv: `arena/opponents/jasskit_bridge.py` loads it there and answers
jass-kit's REST format (V0.2, the JSON the HSLU jass server sends). The C++ jass-bot serves
the same format itself. Nothing of theirs is imported here — jass-kit is GPL-3.0 and most of
the bots have no licence — so they are run locally as opponents and talked to over HTTP.

    python -m arena.opponents.jasskit --bot dl4g --deals 100 --seed 1 --start 2
    python -m arena.opponents.jasskit --bot stub --deals 2 --start 1      # protocol self-check
    python -m arena.opponents.jasskit --report .runs/opp-dl4g-1.jsonl

`--start N` launches N servers of the bot (ports from `--port`) and stops them at the end;
without it the servers must already be running. Every call takes one free server under a
file lock, so a server answers one request at a time and a time-budgeted search never shares
its cores with another of its own requests.

Seats. jass-kit numbers seats the other way round (`next_player = [3, 0, 1, 2]`: the player
after j is j-1), so our seat s is their seat -s mod 4; partners stay partners. Their dealer is
the seat after forehand in their numbering (forehand = next_player[dealer]). Cards (suit*9 +
rank, ranks A K Q J 10 9 8 7 6, suits D H S C) and trumps (0-3 suits, 4 Obenabe, 5 Undenufe,
10 push) are encoded as ours. The C++ bot and the stub check the trick leaders they rebuild
from the dealer and the cards against the player we say is to play, so a wrong mapping fails
loudly. Our engine stays authoritative: an illegal card is logged and our lowest legal played;
an error or timeout is logged and a seeded random legal card played.

Per-deal results go to a JSON-lines file as each deal finishes (with both halves' contract,
declarer, shove and points, so `--report` can break the result down), and a rerun resumes.
=======
"""Seat a jass-kit (HSLU DL4G) bot at our table, through `jasskit_bridge.py` in its own venv.

Nothing of jass-kit (GPL-3.0) or of the opponent is imported here: the bot runs as a child
process with its own interpreter, one per worker process, and we exchange JSON lines with it.
Our engine stays authoritative — every card that comes back is checked against our legal moves.

Seats. jass-kit numbers seats the other way round (`next_player = [3, 0, 1, 2]`), so our seat s
is their seat -s mod 4; partners stay partners, team parity is kept. Their forehand is
`next_player[dealer]`, so the dealer is forehand + 1 in their numbering. Cards and trump codes
coincide: both decks are D, H, S, C x A K Q J 10 9 8 7 6, and both number the contracts
D H S C Obe Une = 0..5. jass-kit's shove is 10 (`PUSH`), or 6 (`PUSH_ALT`) in some bots.

Trump. Only the hand and whether it was shoved matter to the choice, so the request seats the
chooser where jass-kit's own bookkeeping expects: forehand at their seat 0 (dealer 1, forehand
flag -1), or the shoved-to partner at 2 (forehand flag 0).
>>>>>>> origin/claude/opponent-dl4g-b
"""

from __future__ import annotations

<<<<<<< HEAD
import argparse
import fcntl
import json
import os
import random
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from arena.ab import build
from arena.arena import deal_spec, paired_test, play_round
from krass_jass.agent import Agent
from krass_jass.cards import RANK_CHARS, SUIT_CHARS, card_list, card_suit
from krass_jass.rules import EVAL, HOUSE, SHOVE, Contract, RulesConfig
from krass_jass.state import RoundState
from krass_jass.tables import CARD_VALUES, STRENGTH
from krass_jass.trick import trick_winner

CFGS = {"eval": EVAL, "house": HOUSE.variant(target_score=None)}
PUSH = 10
EXT = Path(os.environ.get("JASS_EXT", "/home/user/ext"))
VENVS = EXT / "venvs"
BRIDGE = Path(__file__).with_name("jasskit_bridge.py")

#: How to start each opponent on a port. "py": the venv whose Python runs the bridge, and the
#: bridge arguments (each bot's strongest documented setting, the budget scaled to this
#: machine: see docs/opponents/). "cmd": a server that speaks the format itself.
OPPONENTS: dict[str, dict] = {
    "kit-random": {"py": "kit", "args": ["--bot", "kit-random"]},
    "dl4g-rule": {"py": "dl4g", "args": ["--bot", "dl4g-rule"]},
    "dl4g": {"py": "dl4g", "args": ["--bot", "dl4g", "--c", "8", "--time-budget", "2", "--workers", "3"]},
    "jassager": {"py": "jassager", "args": ["--bot", "jassager", "--time-budget", "2"]},
    "jassager-cnn": {"py": "jassager", "args": ["--bot", "jassager-cnn", "--time-budget", "2"]},
    "kurtoid": {"py": "kit", "args": ["--bot", "kurtoid"]},
    "jass-bot": {"cmd": [str(EXT / "jass-bot-build/build/release/jass-bot")],
                 "env": {"TRUMP_STRATEGY": "baseline", "CARD_STRATEGY": "baseline", "BIND_ADDRESS": "127.0.0.1"}},
    "stub": {"stub": True},
}


def kit_card(c: int) -> str:
    rank = RANK_CHARS[c % 9]
    return SUIT_CHARS[c // 9] + ("10" if rank == "T" else rank)


def our_card(text: str) -> int:
    rank = "T" if text[1:] == "10" else text[1:]
    return SUIT_CHARS.index(text[0]) * 9 + RANK_CHARS.index(rank)
=======
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from krass_jass.agent import Agent
from krass_jass.cards import card_list
from krass_jass.rules import EVAL, SHOVE, Contract, RulesConfig
from krass_jass.tables import CARD_VALUES, STRENGTH
from krass_jass.trick import trick_winner

BRIDGE = Path(__file__).with_name("jasskit_bridge.py")
PUSH = (10, 6)

_PROCS: dict[tuple, subprocess.Popen] = {}
>>>>>>> origin/claude/opponent-dl4g-b


def kit_seat(seat: int) -> int:
    return (-seat) % 4


<<<<<<< HEAD
def request(hand: int, current: int, dealer: int, trump: int, forehand: int, tricks: list) -> dict:
    """A jass-kit V0.2 observation for the player `current` (their numbering)."""
    players = [{"hand": []} for _ in range(4)]
    players[current] = {"hand": [kit_card(c) for c in card_list(hand)]}
    return {"version": "V0.2", "trump": trump, "dealer": dealer, "currentPlayer": current,
            "playerView": current, "forehand": forehand, "tricks": tricks, "player": players,
            "jassTyp": "SCHIEBER"}


def kit_tricks(obs) -> list[dict]:
    """Completed tricks with winner and points (as jass-kit writes them), then the open one."""
    out = []
    values = CARD_VALUES[obs.contract]
    for i, (lead, cards) in enumerate(obs.tricks_played):
        winner = trick_winner(list(cards), lead, STRENGTH[obs.contract][card_suit(cards[0])])
        points = sum(values[c] for c in cards) + (5 if i == 8 else 0)
        out.append({"cards": [kit_card(c) for c in cards], "points": points,
                    "win": kit_seat(winner), "first": kit_seat(lead)})
    if len(obs.tricks_played) < 9:
        out.append({"cards": [kit_card(c) for c in obs.trick], "first": kit_seat(obs.trick_leader)})
    return out


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass
class JassKitOpponent(Agent):
    """A jass-kit bot behind one or more REST servers. Picklable: URLs and log paths only."""

    cfg: RulesConfig = EVAL
    urls: tuple[str, ...] = ("http://127.0.0.1:8701",)
    name: str = "jasskit"
    log_dir: str = ".runs"
    timeout: float = 120.0

    def _post(self, action: str, body: dict) -> dict:
        # Take whichever server is free; wait on one if none is.
        locks = [open(f"{self.log_dir}/{self.name}-{u.rsplit(':', 1)[-1]}.lock", "a") for u in self.urls]
        try:
            chosen = None
            for lock, url in zip(locks, self.urls):
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    chosen = url
                    break
                except BlockingIOError:
                    continue
            if chosen is None:
                i = os.getpid() % len(self.urls)
                fcntl.flock(locks[i], fcntl.LOCK_EX)
                chosen = self.urls[i]
            req = urllib.request.Request(f"{chosen}/{action}", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            with _OPENER.open(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        finally:
            for lock in locks:
                lock.close()

    def _log(self, kind: str, record: dict) -> None:
        with open(f"{self.log_dir}/{self.name}-{kind}.log", "a") as fh:
            fh.write(json.dumps(record) + "\n")

    def select_trump(self, hand: int, is_forehand: bool):
        # Only the hand and whether it was shoved matter, so seat the chooser at their 0:
        # forehand 0 (dealer 1), or the shoved-to partner at 0 with forehand at 2 (dealer 3).
        body = request(hand, 0, 1 if is_forehand else 3, -1, -1 if is_forehand else 0, [])
        try:
            code = int(self._post("action_trump", body)["trump"])
        except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
            self._log("errors", {"action": "trump", "error": repr(e), "hand": [kit_card(c) for c in card_list(hand)]})
            return super().select_trump(hand, is_forehand)
        if code == PUSH and is_forehand:
            return SHOVE
        if 0 <= code <= 5:
            return Contract(code)
        self._log("illegal", {"action": "trump", "code": code, "forehand": is_forehand})
        return super().select_trump(hand, is_forehand)

    def decide(self, obs) -> int:
        legal = card_list(obs.legal_moves)
        if len(legal) == 1:
            return legal[0]
        forehand = obs.tricks_played[0][0] if obs.tricks_played else obs.trick_leader
        declared_forehand = int(obs.declarer_seat == forehand)
        body = request(obs.hand, kit_seat(obs.seat), (kit_seat(forehand) + 1) % 4, int(obs.contract),
                       declared_forehand, kit_tricks(obs))
        try:
            card = our_card(self._post("action_play_card", body)["card"])
        except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
            self._log("errors", {"action": "card", "error": repr(e), "body": body})
            return random.Random(obs.decision_seed).choice(legal)
        if not obs.legal_moves >> card & 1:
            self._log("illegal", {"card": kit_card(card), "hand": [kit_card(c) for c in card_list(obs.hand)],
                                  "trick": [kit_card(c) for c in obs.trick], "contract": int(obs.contract)})
            return legal[-1]
        return card


@dataclass
class Recorder(Agent):
    """Passes every call through to `inner` and notes it. One per seat, in the worker."""

    inner: Agent = None
    seat: int = 0
    log: list = field(default_factory=list)

    def select_trump(self, hand: int, is_forehand: bool):
        action = self.inner.select_trump(hand, is_forehand)
        self.log.append(("trump", self.seat, action if action == SHOVE else int(action)))
        return action

    def decide(self, obs) -> int:
        card = self.inner.decide(obs)
        self.log.append(("card", self.seat, card))
        return card


def _half(hands, leader, ours, theirs, our_seats, cfg, game_seed) -> dict:
    log: list = []
    seats = {s: Recorder(inner=ours if s in our_seats else theirs, seat=s, log=log) for s in range(4)}
    points = play_round(hands, None, leader, seats, cfg, game_seed)
    trumps = [e for e in log if e[0] == "trump"]
    cards = [e[2] for e in log if e[0] == "card"]
    contract, declarer = trumps[-1][2], trumps[-1][1]
    # Replay to get the raw (unmultiplied) card points, which the opponents play for.
    state = RoundState(contract=Contract(contract), hands=list(hands), cfg=cfg, leader=leader)
    for c in cards:
        state.play(c)
    us = our_seats[0] % 2
    return {"contract": contract, "declarer": declarer, "ours_declare": declarer % 2 == us,
            "shoved": len(trumps) == 2, "forehand": leader, "ours_forehand": leader % 2 == us, "ours": points[us], "theirs": points[1 - us],
            "raw_ours": state.trick_points[us], "raw_theirs": state.trick_points[1 - us], "cards": cards}


def play_deal(args) -> dict:
    ours, theirs, cfg, seed, index = args
    hands, _, leader, game_seed = deal_spec(seed, index, None)
    # As arena.double_round: same deal, same game seed, seats swapped.
    first = _half(hands, leader, ours, theirs, (0, 2), cfg, game_seed)
    second = _half(hands, leader, ours, theirs, (1, 3), cfg, game_seed)
    total = first["ours"] + first["theirs"] + second["ours"] + second["theirs"]
    share = 0.5 if total == 0 else (first["ours"] + second["ours"]) / total
    return {"deal": index, "share": share, "halves": [first, second],
            "hands": [kit_card(c) for h in hands for c in card_list(h)]}


def _stub_server(port: int) -> None:
    """A stand-in opponent of ours that checks the request the way the C++ bot does.

    It rebuilds every trick leader from the dealer and the cards with our engine's tables and
    checks it against `first` and `currentPlayer`, then plays a card that is always legal:
    the lowest of the led suit, else any non-trump, else a trump. Used to verify the seat
    and card mapping without any opponent code.
    """
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self._ok({"bot": "stub"})

        def _ok(self, body, code=200):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            b = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            try:
                hand = [our_card(c) for c in b["player"][b["currentPlayer"]]["hand"]]
                assert all(not p["hand"] for i, p in enumerate(b["player"]) if i != b["currentPlayer"])
                if self.path.endswith("action_trump"):
                    chooser = (b["dealer"] - 1) % 4 if b["forehand"] == -1 else (b["dealer"] + 1) % 4
                    assert b["currentPlayer"] == chooser and len(hand) == 9
                    self._ok({"trump": PUSH if b["forehand"] == -1 and sum(c % 9 < 4 for c in hand) < 3
                              else card_suit(hand[0])})
                    return
                trump = Contract(b["trump"])
                leader = (b["dealer"] - 1) % 4
                for t in b["tricks"]:
                    assert t["first"] == leader, ("leader", t, leader)
                    cards = [our_card(c) for c in t["cards"]]
                    if len(cards) == 4:
                        # their numbering runs backwards, so the i-th card is from first - i
                        w = trick_winner(cards, 0, STRENGTH[trump][card_suit(cards[0])])
                        leader = (leader - w) % 4
                        assert t["win"] == leader
                    else:
                        assert b["currentPlayer"] == (t["first"] - len(cards)) % 4
                done = sum(len(t["cards"]) == 4 for t in b["tricks"])
                assert len(hand) == 9 - done
                cur = [our_card(c) for c in b["tricks"][-1]["cards"]]
                t_suit = int(trump) if trump.is_trump else -1
                follow = [c for c in hand if cur and card_suit(c) == card_suit(cur[0])]
                plain = [c for c in hand if card_suit(c) != t_suit]
                card = (follow or plain or hand)[-1]
                self._ok({"card": kit_card(card)})
            except AssertionError as e:
                self._ok({"error": f"mapping: {e}"}, 500)

        def log_message(self, *a):
            pass

    HTTPServer(("127.0.0.1", port), H).serve_forever()


def start_servers(bot: str, ports: list[int], log_dir: Path) -> list[subprocess.Popen]:
    spec = OPPONENTS[bot]
    procs = []
    for port in ports:
        if spec.get("stub"):
            cmd, env = [sys.executable, __file__, "--stub-serve", str(port)], None
        elif "py" in spec:
            cmd = [str(VENVS / spec["py"] / "bin/python"), "-I", str(BRIDGE), *spec["args"], "--port", str(port)]
            # One thread for torch/BLAS: a server is one seat's search, not the whole machine.
            env = {**os.environ, "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        else:
            cmd, env = spec["cmd"], {**os.environ, **spec["env"], "PORT": str(port)}
        out = open(log_dir / f"opp-{bot}-{port}.server.log", "a")
        procs.append(subprocess.Popen(cmd, env=env, stdout=out, stderr=subprocess.STDOUT))
    for port in ports:
        for _ in range(600):
            try:
                with _OPENER.open(f"http://127.0.0.1:{port}/health", timeout=2):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError(f"{bot} on {port} did not come up; see {log_dir}/opp-{bot}-{port}.server.log")
    return procs


def _load(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {r["deal"]: r for r in rows}


NAMES = {0: "Diamonds", 1: "Hearts", 2: "Spades", 3: "Clubs", 4: "Obenabe", 5: "Undenufe"}


def report(path: Path, worst: int = 5) -> dict:
    rows = list(_load(path).values())
    shares = [r["share"] for r in rows]
    _, pv = paired_test([s - 0.5 for s in shares])
    mean, std = statistics.fmean(shares), statistics.stdev(shares)
    print(f"{path.name}: {mean:.2%} ± {std:.2%}  n={len(shares)}  p={pv:.2e}")
    halves = [h for r in rows for h in r["halves"]]
    raw = sum(h["raw_ours"] for h in halves) / max(1, sum(h["raw_ours"] + h["raw_theirs"] for h in halves))
    print(f"  raw card points (no multipliers): {raw:.2%}")
    by = defaultdict(list)
    for h in halves:
        side = "ours" if h["ours_declare"] else "theirs"
        tot = h["ours"] + h["theirs"]
        share = h["ours"] / tot if tot else 0.5
        by[(side, "all")].append((share, h))
        by[(side, NAMES[h["contract"]])].append((share, h))
    print("  declaring side, contract: rounds, our share of that round's points, declarer's raw points")
    for key in sorted(by):
        items = by[key]
        dec_raw = statistics.fmean((h["raw_ours"] if h["ours_declare"] else h["raw_theirs"]) for _, h in items)
        print(f"    {key[0]:>6} {key[1]:<9} {len(items):4d}  {statistics.fmean(s for s, _ in items):6.2%}"
              f"  {dec_raw:6.1f}")
    for side in ("ours", "theirs"):
        fh = [h for h in halves if h["ours_forehand"] == (side == "ours")]
        shoved = sum(h["shoved"] for h in fh)
        print(f"  {side} in forehand {len(fh)} rounds, shoved {shoved} ({shoved / max(1, len(fh)):.0%})")
    print(f"  worst {worst} deals for us:")
    for r in sorted(rows, key=lambda r: r["share"])[:worst]:
        desc = "; ".join(
            f"{'we' if h['ours_declare'] else 'they'} {NAMES[h['contract']]}{' (shoved)' if h['shoved'] else ''}"
            f" {h['ours']}-{h['theirs']}" for h in r["halves"])
        print(f"    deal {r['deal']}: {r['share']:.1%}  {desc}")
    return {"a_share": mean, "std": std, "p": pv, "deals": len(shares), "raw_share": raw}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", choices=sorted(OPPONENTS))
    ap.add_argument("--deals", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--cfg", choices=sorted(CFGS), default="eval")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--start", type=int, default=0, help="launch this many servers of the bot")
    ap.add_argument("--port", type=int, default=8701)
    ap.add_argument("--servers", type=int, default=1, help="servers already running (without --start)")
    ap.add_argument("--ours", nargs="*", default=[], help="DmctsAgent field=value pairs, as arena.ab")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--stub-serve", type=int, help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.stub_serve:
        _stub_server(args.stub_serve)
        return
    if args.report:
        report(args.report)
        return

    log_dir = Path(".runs")
    log_dir.mkdir(exist_ok=True)
    cfg = CFGS[args.cfg]
    n = args.start or args.servers
    ports = [args.port + i for i in range(n)]
    procs = start_servers(args.bot, ports, log_dir) if args.start else []
    try:
        ours = build(args.ours, 153_600, cfg)  # 40 x 3,840, as served, unless --ours says otherwise
        theirs = JassKitOpponent(cfg=cfg, urls=tuple(f"http://127.0.0.1:{p}" for p in ports),
                                 name=f"opp-{args.bot}", log_dir=str(log_dir))
        out = args.out or log_dir / f"opp-{args.bot}-{args.seed}-{'-'.join(args.ours) or 'shipped'}.jsonl"
        done = _load(out)
        todo = [i for i in range(args.deals) if i not in done]
        print(f"{out}: {len(done)} done, {len(todo)} to play", flush=True)
        t = time.time()
        with ProcessPoolExecutor(max_workers=args.workers) as pool, out.open("a") as fh:
            futures = [pool.submit(play_deal, (ours, theirs, cfg, args.seed, i)) for i in todo]
            for k, f in enumerate(as_completed(futures), 1):
                fh.write(json.dumps(f.result()) + "\n")
                fh.flush()
                if k % 5 == 0:
                    print(f"  {k}/{len(todo)} ({(time.time() - t) / 60:.0f} min)", flush=True)
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait(timeout=30)
    summary = report(out)
    errors = log_dir / f"opp-{args.bot}-errors.log"
    illegal = log_dir / f"opp-{args.bot}-illegal.log"
    count = lambda p: len(p.read_text().splitlines()) if p.exists() else 0
    print(f"  opponent errors/fallbacks: {count(errors)}, illegal: {count(illegal)}")
    if args.bot == "stub":
        return
    record = {"a": args.ours or ["shipped"], "b": [args.bot, *OPPONENTS[args.bot].get("args", [])],
              "seed": args.seed, "iterations": ours.determinizations * ours.iterations, "cfg": args.cfg,
              **summary, "se": summary["std"] / summary["deals"] ** 0.5, "errors": count(errors),
              "illegal": count(illegal), "minutes": round((time.time() - t) / 60, 1),
              "when": time.strftime("%Y-%m-%d %H:%M")}
    with Path("arena/opponents/results.jsonl").open("a") as fh:
        fh.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
=======
@dataclass
class JassKitBot(Agent):
    """An opponent behind the bridge. Picklable: only paths and strings; the child is per process."""

    name: str = "jass-kit"
    python: str = ""                   #: the opponent venv's interpreter
    repo: str = ""                     #: its checkout
    agent: str = ""                    #: "module:expression" building the jass-kit Agent
    path: tuple[str, ...] = ()         #: extra sys.path entries, relative to repo
    cwd: str = ""                      #: working directory, relative to repo
    api: str = "v2"                    #: "v1" for bots on the 2018 jass-kit 1.0 (PlayerRound)
    env: dict = field(default_factory=dict)
    cfg: RulesConfig = EVAL
    log_dir: str = ".runs/opponents"

    # -- the child process -------------------------------------------------------------------
    def _proc(self) -> subprocess.Popen:
        key = (os.getpid(), self.name)
        p = _PROCS.get(key)
        if p is None or p.poll() is not None:
            Path(self.log_dir).mkdir(parents=True, exist_ok=True)
            err = open(Path(self.log_dir) / f"{self.name}-{os.getpid()}.stderr", "a")
            cmd = [self.python, "-u", str(BRIDGE), "--repo", self.repo, "--agent", self.agent,
                   "--cwd", self.cwd, "--api", self.api, "--path", *self.path]
            env = {**os.environ, "CUDA_VISIBLE_DEVICES": "-1", "TF_CPP_MIN_LOG_LEVEL": "3",
                   "PYTHONHASHSEED": "0", **self.env}
            env.pop("PYTHONPATH", None)
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
                                 text=True, bufsize=1, env=env)
            _PROCS[key] = p
        return p

    def _ask(self, msg: dict) -> dict:
        p = self._proc()
        p.stdin.write(json.dumps(msg) + "\n")
        p.stdin.flush()
        line = p.stdout.readline()
        if not line:
            # A bot that cannot start is not a bot that plays our fallback card every move.
            raise RuntimeError(f"{self.name}: bridge exited with {p.wait()}, see {self.log_dir}/*.stderr")
        return json.loads(line)

    def _log(self, kind: str, record: dict) -> None:
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        with open(Path(self.log_dir) / f"{self.name}-{kind}.log", "a") as fh:
            fh.write(json.dumps(record) + "\n")

    # -- the two decisions -------------------------------------------------------------------
    def select_trump(self, hand: int, is_forehand: bool):
        player = 0 if is_forehand else 2
        msg = {"kind": "trump", "hand": card_list(hand), "dealer": 1, "player": player,
               "forehand": -1 if is_forehand else 0}
        out = self._ask(msg)
        code = out.get("trump")
        if code in PUSH and is_forehand:
            return SHOVE
        if code is not None and 0 <= code <= 5:
            return Contract(code)
        # An error, or a shove where a shove is not allowed: our rule-based choice, logged.
        self._log("fallback", {"kind": "trump", "answer": out, "hand": card_list(hand),
                               "forehand": is_forehand})
        return Agent.select_trump(self, hand, False)

    def decide(self, obs) -> int:
        if obs.tricks_played:
            forehand = obs.tricks_played[0][0]
        else:
            forehand = obs.trick_leader
        strength = STRENGTH[obs.contract]
        values = CARD_VALUES[obs.contract]
        tricks, first, winner, points = [], [], [], []
        for lead, cards in obs.tricks_played:
            tricks.append(list(cards))
            first.append(kit_seat(lead))
            winner.append(kit_seat(trick_winner(list(cards), lead, strength[cards[0] // 9])))
            points.append(sum(values[c] for c in cards))
        if obs.trick:
            tricks.append(list(obs.trick))
        first.append(kit_seat(obs.trick_leader))  # also for a trick not yet led, as jass-kit does
        msg = {
            "kind": "play", "hand": card_list(obs.hand), "player": kit_seat(obs.seat),
            "dealer": (kit_seat(forehand) + 1) % 4, "trump": int(obs.contract),
            "forehand": int(obs.declarer_seat == forehand), "declared_trump": kit_seat(obs.declarer_seat),
            "tricks": tricks, "first": first, "winner": winner, "points": points,
        }
        out = self._ask(msg)
        card = out.get("card")
        if "valid" in out and (out["valid"] != card_list(obs.legal_moves) or not out["seat_ok"]):
            # jass-kit disagrees with us on what is legal, who is to play or who won a trick.
            self._log("mismatch", {"valid": out["valid"], "seat_ok": out["seat_ok"], "msg": msg,
                                   "legal": card_list(obs.legal_moves)})
        if card is None or not (0 <= card < 36) or not obs.legal_moves >> card & 1:
            # Our engine decides what is legal. Record the disagreement and play our lowest legal.
            self._log("illegal" if card is not None else "fallback",
                      {"answer": out, "hand": card_list(obs.hand), "trick": list(obs.trick),
                       "contract": int(obs.contract), "legal": card_list(obs.legal_moves)})
            card = card_list(obs.legal_moves)[-1]
        return card

>>>>>>> origin/claude/opponent-dl4g-b
