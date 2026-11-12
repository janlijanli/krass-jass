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
"""

from __future__ import annotations

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


def kit_seat(seat: int) -> int:
    return (-seat) % 4


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

