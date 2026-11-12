"""Our bot against DonaldTrumpf (edualc/DonaldTrumpf, MIT), 4th place in the Zühlke Jass Challenge 2017.

A hand-written rule-based bot in JavaScript for the webplatformz/challenge server. It runs in its
own Node process (`bridges/challenge_brain.js`), which replays to a freshly loaded copy of its
decision code the challenge-protocol messages one seat would have received, and returns its answer
to the final REQUEST_TRUMPF / REQUEST_CARD. Nothing of it is imported into Python or vendored.

    git clone --depth 1 https://github.com/edualc/DonaldTrumpf /home/user/ext/edualc_DonaldTrumpf
    (cd /home/user/ext/_deps && npm install --ignore-scripts lodash@4.17.21)   # its one runtime dep
    python -m arena.opponents.donald_trumpf --deals 400 --seed 1
    python -m arena.opponents.donald_trumpf --report .runs/donald_trumpf-1-eval-shipped.jsonl

Seats. The challenge protocol never tells a client a seat number: it sees the trick in play order
and the *name* of each trick's winner (a team's two bots share a name, "DonaldTrumpf 3000" — the
name its card counter tests for). So the mapping to check is only that partner = two cards back in
the trick, which holds for our play order (seat lead+k plays k-th).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from arena.opponents.common import (
    EXT, Agent, RulesConfig, ask, challenge_history, checked, log_event, main, our_card_ch,
    our_contract_ch, trumpf_history,
)
from pathlib import Path

from krass_jass.rules import EVAL

BRIDGE = str(Path(__file__).resolve().parent / "bridges" / "challenge_brain.js")
TEAM = "DonaldTrumpf 3000"   # its ChanceCalc credits a trick to its team by this name
OTHER = "krass-jass"


@dataclass
class DonaldTrumpf(Agent):
    """Picklable: a client directory and a log path; the Node process starts lazily per worker."""

    cfg: RulesConfig = EVAL
    client: str = str(EXT / "edualc_DonaldTrumpf" / "client")
    node_path: str = str(EXT / "_deps" / "node_modules")
    log: str = ".runs/donald_trumpf-events.jsonl"
    name: str = "DonaldTrumpf"

    def _ask(self, messages):
        # Their code runs sandboxed: no network (own namespace), and Node's permission model lets
        # it read only the bridge, its own checkout and its one dependency — no writes, no
        # child processes, no workers.
        os.environ["NODE_PATH"] = self.node_path
        # A directory grant needs the `/*` form; a bare directory path grants nothing below it.
        return ask(("unshare", "-n", "node", "--permission", f"--allow-fs-read={BRIDGE}",
                    f"--allow-fs-read={self.client}/*", f"--allow-fs-read={self.node_path}/*",
                    BRIDGE, self.client), messages)

    def select_trump(self, hand: int, is_forehand: bool):
        try:
            answer = self._ask(trumpf_history(hand, is_forehand))
            return our_contract_ch(answer["data"])
        except Exception as e:  # noqa: BLE001 — a broken opponent must not stop the match
            log_event(self.log, {"kind": "trump_error", "error": repr(e)[:300]})
            return super().select_trump(hand, is_forehand)

    def decide(self, obs) -> int:
        try:
            answer = self._ask(challenge_history(obs, TEAM, OTHER))
            card = our_card_ch(answer["data"]) if answer.get("data") else None
            why = {} if card is not None else {"error": str(answer.get("error"))[:300]}
        except Exception as e:  # noqa: BLE001
            card, why = None, {"error": repr(e)[:300]}
        return checked(card, obs, self.log, why)


if __name__ == "__main__":
    main("donald_trumpf", lambda cfg, args: DonaldTrumpf(cfg=cfg))
