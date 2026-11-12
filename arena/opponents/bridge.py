"""One bridge for every external bot: an `Agent` whose decisions come from a subprocess.

The wire format is neutral — *our* encoding, never theirs — so each opponent's server script
(`servers/<name>_server.py`, run in that opponent's own interpreter) does the translation on its
side and this module stays the same for all of them:

    -> {"op": "trump", "hand": [card, ...], "forehand": true}
    <- {"trump": 0..5} | {"trump": "shove"}
    -> {"op": "play", "seat": s, "hand": [...], "legal": [...], "contract": 0..5,
        "declarer": s, "trick": [card, ...], "trick_leader": s,
        "tricks_played": [[leader, [c0, c1, c2, c3]], ...]}
    <- {"card": card}
    <- {"error": "..."}   (either op: the server could not answer; logged, and we fall back)

Cards are our indices, ``suit * 9 + rank`` with suits ``"DHSC"`` and ranks ``"AKQJT9876"``.
Contracts are `Contract` values: 0-3 the trump suit, 4 Obenabe, 5 Undenufe. Seats are ours:
the next seat to play after ``s`` is ``s + 1``, partners are ``s`` and ``s + 2``. One JSON object
per line each way; anything the server prints that is not the reply goes to its stderr.

Our engine is authoritative. A card that is not in our legal moves is logged and replaced by our
lowest legal card (as `arena/jass_the_ripper.py` does), and a server that dies or answers garbage
is logged as an *error* and replaced the same way — so a broken bridge shows up as a rate, not as
a crash or a quietly random opponent. `count_events` reads those logs back for the report.

Picklable: only paths cross the process pool. Each worker process starts its own server on first
use, so calls never interleave; `lock_file` serialises across workers for a server that is not
safe to run more than once at a time (none of these so far).
"""

from __future__ import annotations

import atexit
import fcntl
import json
import os
import subprocess
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from krass_jass.agent import Agent
from krass_jass.cards import card_list
from krass_jass.rules import EVAL, SHOVE, Contract, RulesConfig

_SERVERS: dict[tuple, subprocess.Popen] = {}


def _close_all() -> None:
    for proc in _SERVERS.values():
        try:
            proc.stdin.close()
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001 - shutting down
            proc.kill()


atexit.register(_close_all)


@dataclass
class BridgeAgent(Agent):
    """An opponent behind a JSON-lines subprocess. Subclass or configure per opponent."""

    cfg: RulesConfig = EVAL
    python: str = "python3"              #: the opponent's own interpreter (its venv)
    server: str = ""                     #: our server script for it
    args: tuple[str, ...] = ()
    name: str = "bridge"
    log_dir: str = ".runs/opponents"
    lock_file: str = ""                  #: set to serialise every call across processes
    env: dict = field(default_factory=dict)

    # -- process ----------------------------------------------------------------

    def _proc(self) -> subprocess.Popen:
        key = (os.getpid(), self.python, self.server, self.args)
        proc = _SERVERS.get(key)
        if proc is None or proc.poll() is not None:
            Path(self.log_dir).mkdir(parents=True, exist_ok=True)
            err = open(Path(self.log_dir) / f"{self.name}-stderr.log", "a")
            # -I: isolated mode, so nothing from our environment or cwd is on their path.
            proc = subprocess.Popen(
                [self.python, "-I", self.server, *self.args],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1,
                env={**{k: os.environ[k] for k in ("PATH", "HOME", "LANG") if k in os.environ},
                     "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", **self.env},
            )
            _SERVERS[key] = proc
        return proc

    def _call(self, msg: dict) -> dict:
        lock = open(self.lock_file, "a") if self.lock_file else nullcontext()
        with lock as fh:
            if fh is not None:
                fcntl.flock(fh, fcntl.LOCK_EX)
            proc = self._proc()
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
        if not line:
            raise RuntimeError(f"{self.name} server exited (code {proc.poll()})")
        reply = json.loads(line)
        if "error" in reply:  # the server caught an exception of its own
            raise RuntimeError(f"{self.name} server: {reply['error']}")
        return reply

    def _log(self, kind: str, record: dict) -> None:
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        with open(Path(self.log_dir) / f"{self.name}-{kind}.log", "a") as fh:
            fh.write(json.dumps(record) + "\n")

    # -- Agent ------------------------------------------------------------------

    def select_trump(self, hand: int, is_forehand: bool):
        msg = {"op": "trump", "hand": card_list(hand), "forehand": is_forehand}
        try:
            code = self._call(msg)["trump"]
        except Exception as e:  # noqa: BLE001 - logged and counted, never silent
            self._log("errors", {"msg": msg, "error": repr(e)})
            code = 4
        if code == "shove":
            if is_forehand:
                return SHOVE
            self._log("errors", {"msg": msg, "error": "shoved back"})
            code = 4
        self._log("calls", {"op": "trump"})
        return Contract(int(code))

    def decide(self, obs) -> int:
        msg = {
            "op": "play", "seat": obs.seat, "hand": card_list(obs.hand),
            "legal": card_list(obs.legal_moves), "contract": int(obs.contract),
            "declarer": obs.declarer_seat, "trick": list(obs.trick), "trick_leader": obs.trick_leader,
            "tricks_played": [[lead, list(cards)] for lead, cards in obs.tricks_played],
        }
        fallback = card_list(obs.legal_moves)[-1]
        try:
            card = int(self._call(msg)["card"])
        except Exception as e:  # noqa: BLE001
            self._log("errors", {"msg": msg, "error": repr(e)})
            return fallback
        self._log("calls", {"op": "play"})
        if not (0 <= card < 36 and obs.legal_moves >> card & 1):
            self._log("illegal", {"card": card, **msg})
            return fallback
        return card


def count_events(log_dir: str, name: str) -> dict[str, int]:
    """Calls, errors and illegal cards logged so far for opponent `name`."""
    out = {}
    for kind in ("calls", "errors", "illegal"):
        p = Path(log_dir) / f"{name}-{kind}.log"
        out[kind] = sum(1 for _ in p.open()) if p.exists() else 0
    return out
