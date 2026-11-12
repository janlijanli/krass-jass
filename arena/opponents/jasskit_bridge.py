<<<<<<< HEAD
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
=======
"""Opponent side of the jass-kit bridge: runs *inside the opponent's own venv*, never ours.

HSLU's DL4G bots are `jass.agents.agent.Agent` subclasses from Thomas Koller's jass-kit
(GPL-3.0). Nothing under `krass_jass/` may import that, so this script is the only place that
does, and it runs as a separate process: `arena/opponents/jasskit.py` starts it with the
opponent's interpreter and talks JSON lines over stdin/stdout.

    <venv>/bin/python arena/opponents/jasskit_bridge.py --repo <checkout> --agent module:expr

One request per line in, one answer per line out:

    {"kind": "trump", "hand": [ids], "dealer": d, "player": p, "forehand": -1 | 0}
    {"kind": "play", "hand": [ids], "dealer": d, "player": p, "trump": t, "forehand": 1 | 0,
     "declared_trump": s, "tricks": [[ids], ...], "first": [...], "winner": [...], "points": [...]}
 -> {"trump": int} | {"card": int} | {"error": "..."}

Seats, cards and trump codes are already in jass-kit's numbering when they arrive (the
adapter converts). The observation is filled field by field rather than through
`GameObservation.from_json`, because the jass-kit versions in these repositories disagree
on that JSON and agree on the fields.

Bots print freely; the real stdout is kept for answers and `sys.stdout` points at stderr.
>>>>>>> origin/claude/opponent-dl4g-b
"""

from __future__ import annotations

import argparse
<<<<<<< HEAD
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
=======
import importlib
import json
import os
import sys
import traceback
>>>>>>> origin/claude/opponent-dl4g-b


def main() -> None:
    ap = argparse.ArgumentParser()
<<<<<<< HEAD
    ap.add_argument("--bot", choices=sorted(BOTS), required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--time-budget", type=float, help="seconds a move, for the time-budgeted searches")
    ap.add_argument("--workers", type=int, help="dl4g: root-parallel worker processes")
    ap.add_argument("--c", type=float, help="UCB1 exploration constant")
    args = ap.parse_args()
    agent = BOTS[args.bot](args)
    print(f"{args.bot} ready on {args.port}", flush=True)
    serve(args.bot, agent, args.port)
=======
    ap.add_argument("--repo", required=True, help="the opponent's checkout; it goes on sys.path")
    ap.add_argument("--path", nargs="*", default=[], help="extra sys.path entries, relative to --repo")
    ap.add_argument("--cwd", default="", help="working directory, relative to --repo (model paths)")
    ap.add_argument("--agent", required=True, help="module:expression, e.g. my_agent:MyAgent()")
    ap.add_argument("--api", choices=("v2", "v1"), default="v2",
                    help="v2: jass-kit 2.x GameObservation / action_trump / action_play_card; "
                         "v1: the 2018 jass-kit 1.0 PlayerRound / select_trump / play_card")
    args = ap.parse_args()

    answers = os.fdopen(os.dup(1), "w", buffering=1)
    sys.stdout = sys.stderr

    os.chdir(os.path.join(args.repo, args.cwd))
    for p in [args.repo, *(os.path.join(args.repo, q) for q in args.path), os.getcwd()]:
        sys.path.insert(0, p)

    import numpy as np

    if args.api == "v2":
        from jass.game.game_observation import GameObservation as View
        from jass.game.rule_schieber import RuleSchieber

        rule = RuleSchieber()
    else:
        from jass.base.player_round import PlayerRound
        from jass.base.rule_schieber import RuleSchieber

        rule = RuleSchieber()

        def View():  # noqa: N802 - stands in for the v2 class
            return PlayerRound(jass_type="SCHIEBER_1000", rule=rule)

    module, _, expr = args.agent.partition(":")
    agent = eval(expr, vars(importlib.import_module(module)))

    def observation(msg: dict):
        obs = View()
        obs.dealer = msg["dealer"]
        obs.player = obs.player_view = msg["player"]
        obs.trump = msg.get("trump", -1)
        obs.forehand = msg["forehand"]
        if args.api == "v1":  # v1 spells the flag None (may shove) / False (shoved) / True
            obs.forehand = {-1: None, 0: False, 1: True}[obs.forehand]
        obs.declared_trump = msg.get("declared_trump", -1)
        obs.hand[msg["hand"]] = 1
        first = msg.get("first", [])
        for i, cards in enumerate(msg.get("tricks", [])):
            obs.tricks[i, : len(cards)] = cards
            obs.nr_played_cards += len(cards)
        # One more than the tricks with cards when a trick is about to be led: jass-kit sets the
        # next leader as soon as a trick closes.
        obs.trick_first_player[: len(first)] = first
        winners, points = msg.get("winner", []), msg.get("points", [])
        for i, (w, pts) in enumerate(zip(winners, points)):
            obs.trick_winner[i] = w
            obs.trick_points[i] = pts
            if args.api == "v2":
                obs.points[w % 2] += pts
            elif w % 2 == 0:
                obs.points_team_0 += pts
            else:
                obs.points_team_1 += pts
        obs.nr_tricks, obs.nr_cards_in_trick = divmod(obs.nr_played_cards, 4)
        obs.current_trick = obs.tricks[obs.nr_tricks] if obs.nr_played_cards < 36 else None
        return obs

    for line in sys.stdin:
        msg = json.loads(line)
        try:
            obs = observation(msg)
            if msg["kind"] == "trump":
                choose = agent.action_trump if args.api == "v2" else agent.select_trump
                out = {"trump": int(choose(obs))}
            else:
                # The mapping check, on jass-kit's side of the line: its own legal cards, the seat
                # it reconstructs as next to play, and its winner of every finished trick.
                legal = rule.get_valid_cards_from_obs(obs) if args.api == "v2" else obs.get_valid_cards()
                valid = [int(c) for c in np.flatnonzero(legal)]
                seat = (obs.trick_first_player[obs.nr_tricks] - obs.nr_cards_in_trick) % 4
                winners = [int(rule.calc_winner(obs.tricks[i], obs.trick_first_player[i], obs.trump))
                           for i in range(obs.nr_tricks)]
                play = agent.action_play_card if args.api == "v2" else agent.play_card
                out = {"card": int(play(obs)), "valid": valid,
                       "seat_ok": bool(seat == obs.player and winners == list(obs.trick_winner[:obs.nr_tricks]))}
        except Exception as e:  # report and carry on: the adapter falls back and logs it
            traceback.print_exc()
            out = {"error": f"{type(e).__name__}: {e}"}
        answers.write(json.dumps(out) + "\n")
>>>>>>> origin/claude/opponent-dl4g-b


if __name__ == "__main__":
    main()
