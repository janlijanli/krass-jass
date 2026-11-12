"""A jass-kit agent behind a tiny REST server, run in the *opponent's* own venv.

This file is the one place where a jass-kit agent is loaded, and it never runs in our
interpreter: `arena/opponents/jasskit.py` starts it as a subprocess with the opponent venv's
Python, and talks to it over HTTP. Nothing under `krass_jass/` imports it, and it imports
nothing of ours. jass-kit (github.com/thomas-koller/jass-kit-py) is GPL-3.0; several of the
bots it loads have no licence at all — run locally as opponents, nothing more.

    /home/user/ext/venvs/dl4g/bin/python -I arena/opponents/jasskit_bridge.py --bot dl4g --port 8701

The wire format is jass-kit's own (`GameObservation.from_json`, version V0.2), the JSON the
HSLU jass server sends to a player:

    POST /action_trump        -> {"trump": 0..5 | 10}
    POST /action_play_card    -> {"card": "DA" ...}
    GET  /health              -> {"bot": ..., "status": "ok"}

A `/<player>/` prefix (as on the HSLU server) is accepted and ignored. The server is
single-threaded on purpose: one request at a time, so a time-budgeted search never shares
its cores with another of its own requests.

Each bot is a factory in BOTS: the checkouts it needs on `sys.path` and how to build its
strongest documented setting. Checkouts live in $JASS_EXT (default /home/user/ext).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types
from http.server import BaseHTTPRequestHandler, HTTPServer

EXT = os.environ.get("JASS_EXT", "/home/user/ext")


def _path(*dirs: str) -> None:
    for d in reversed(dirs):
        sys.path.insert(0, os.path.join(EXT, d))


def _kit_random(_args):
    _path("jass-kit-py")
    from jass.agents.agent_random_schieber import AgentRandomSchieber

    return AgentRandomSchieber()


def _dl4g_rule(_args):
    # Joelius300's rule-based agent: the "Graf" trump heuristic and a greedy card rule.
    _path("dl4g_hslu", "joelius-jass-kit")
    from jass_bot.agents.rule_based import RuleBasedAgent

    return RuleBasedAgent()


def _dl4g_ismcts(args):
    # Root-parallel ISMCTS, as deployed for the HSLU tournament (docker-compose.yaml, report
    # §"Tuning"): C = 8 was their best, 15 workers x 9.75 s. Budget and workers are ours to set.
    _path("dl4g_hslu", "joelius-jass-kit")
    from jass_bot.agents.multi_processing_ISMCTS import MultiProcessingISMCTS

    return MultiProcessingISMCTS(
        args.time_budget if args.time_budget is not None else 9.75,
        ucb1_c_param=args.c if args.c is not None else 8.0,
        num_workers=args.workers if args.workers is not None else -1,
        ignore_same_player_safety=True,
    )


def _jassager(args, cnn: bool):
    _path("jassager")
    os.chdir(os.path.join(EXT, "jassager"))  # their model loader resolves paths from the cwd
    import bots.mcts_bots.util.mcts_implementation as impl

    if args.time_budget is not None:
        impl.MAX_SEARCH_DURATION = args.time_budget  # theirs: 9.5 s, for trump and for cards
    if cnn:
        from bots import MCTSCNNRollout

        return MCTSCNNRollout(c_param=args.c if args.c is not None else 1.3)
    from bots import FullMCTS

    return FullMCTS()


def _kurtoid(_args):
    """Kurtoid's "Trumpruler" (its tournament bot), written against the 2019 jass-kit API.

    That kit (`jass.base.*`, `jass.player.*`) lived on a private HSLU GitLab. Its few names that
    Trumpruler touches are mapped here onto the current kit: a PlayerRound is the observation
    with `rule`, `get_valid_cards()` and `forehand = None` until trump is declared.
    """
    _path("kurtoid/app", "jass-kit-py")
    import numpy as np
    from jass.agents.agent import Agent
    from jass.game import const
    from jass.game.rule_schieber import RuleSchieber

    rule = RuleSchieber()

    class PlayerRound:
        def __init__(self, obs):
            self.hand = obs.hand.copy()
            self.tricks = obs.tricks.copy()
            self.nr_tricks = obs.nr_tricks
            self.trick_first_player = obs.trick_first_player.copy()
            self.current_trick = (self.tricks[obs.nr_tricks] if obs.nr_tricks < 9
                                  else np.full(4, -1, dtype=np.int32))
            self.nr_cards_in_trick = obs.nr_cards_in_trick
            self.trump = obs.trump
            self.player = obs.player
            self.dealer = obs.dealer
            self.forehand = None if obs.forehand == -1 else bool(obs.forehand)
            self.rule = rule

        def get_valid_cards(self):
            return rule.get_valid_cards(self.hand, self.current_trick, self.nr_cards_in_trick, self.trump)

    class Player:
        pass

    mods = {
        "jass.base": types.ModuleType("jass.base"),
        "jass.base.const": const,
        "jass.base.player_round": types.SimpleNamespace(PlayerRound=PlayerRound),
        "jass.base.rule_schieber": types.SimpleNamespace(RuleSchieber=RuleSchieber),
        "jass.player": types.ModuleType("jass.player"),
        "jass.player.player": types.SimpleNamespace(Player=Player),
    }
    sys.modules.update(mods)
    from trumpruloid import Trumpruloid

    bot = Trumpruloid()

    class Adapter(Agent):
        def action_trump(self, obs):
            return int(bot.select_trump(PlayerRound(obs)))

        def action_play_card(self, obs):
            return int(bot.play_card(PlayerRound(obs)))

    return Adapter()


BOTS = {
    "kit-random": _kit_random,
    "dl4g-rule": _dl4g_rule,
    "dl4g": _dl4g_ismcts,
    "jassager": lambda a: _jassager(a, cnn=False),
    "jassager-cnn": lambda a: _jassager(a, cnn=True),
    "kurtoid": _kurtoid,
}


def serve(bot_name: str, agent, port: int) -> None:
    from jass.game.const import card_strings
    from jass.game.game_observation import GameObservation

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._send(200, {"bot": bot_name, "status": "ok"})

        def do_POST(self):
            action = self.path.rstrip("/").rsplit("/", 1)[-1]
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                obs = GameObservation.from_json(body)
                t = time.time()
                if action == "action_trump":
                    out = {"trump": int(agent.action_trump(obs))}
                elif action == "action_play_card":
                    out = {"card": str(card_strings[int(agent.action_play_card(obs))])}
                else:
                    self._send(404, {"error": f"unknown action {action}"})
                    return
                out["seconds"] = round(time.time() - t, 3)
                self._send(200, out)
            except Exception as e:  # noqa: BLE001 — the caller logs it and falls back
                self._send(500, {"error": f"{type(e).__name__}: {e}"})

        def log_message(self, *a):
            pass

    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", choices=sorted(BOTS), required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--time-budget", type=float, help="seconds a move, for the time-budgeted searches")
    ap.add_argument("--workers", type=int, help="dl4g: root-parallel worker processes")
    ap.add_argument("--c", type=float, help="UCB1 exploration constant")
    args = ap.parse_args()
    agent = BOTS[args.bot](args)
    print(f"{args.bot} ready on {args.port}", flush=True)
    serve(args.bot, agent, args.port)


if __name__ == "__main__":
    main()
