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
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import traceback


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="the opponent's checkout; it goes on sys.path")
    ap.add_argument("--path", nargs="*", default=[], help="extra sys.path entries, relative to --repo")
    ap.add_argument("--cwd", default="", help="working directory, relative to --repo (model paths)")
    ap.add_argument("--agent", required=True, help="module:expression, e.g. my_agent:MyAgent()")
    args = ap.parse_args()

    answers = os.fdopen(os.dup(1), "w", buffering=1)
    sys.stdout = sys.stderr

    os.chdir(os.path.join(args.repo, args.cwd))
    for p in [args.repo, *(os.path.join(args.repo, q) for q in args.path), os.getcwd()]:
        sys.path.insert(0, p)

    import numpy as np
    from jass.game.game_observation import GameObservation
    from jass.game.rule_schieber import RuleSchieber

    rule = RuleSchieber()

    module, _, expr = args.agent.partition(":")
    agent = eval(expr, vars(importlib.import_module(module)))

    def observation(msg: dict) -> GameObservation:
        obs = GameObservation()
        obs.dealer = msg["dealer"]
        obs.player = obs.player_view = msg["player"]
        obs.trump = msg.get("trump", -1)
        obs.forehand = msg["forehand"]
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
            obs.points[w % 2] += pts
        obs.nr_tricks, obs.nr_cards_in_trick = divmod(obs.nr_played_cards, 4)
        obs.current_trick = obs.tricks[obs.nr_tricks] if obs.nr_played_cards < 36 else None
        return obs

    for line in sys.stdin:
        msg = json.loads(line)
        try:
            obs = observation(msg)
            if msg["kind"] == "trump":
                out = {"trump": int(agent.action_trump(obs))}
            else:
                # The mapping check, on jass-kit's side of the line: its own legal cards, the seat
                # it reconstructs as next to play, and its winner of every finished trick.
                valid = [int(c) for c in np.flatnonzero(rule.get_valid_cards_from_obs(obs))]
                seat = (obs.trick_first_player[obs.nr_tricks] - obs.nr_cards_in_trick) % 4
                winners = [int(rule.calc_winner(obs.tricks[i], obs.trick_first_player[i], obs.trump))
                           for i in range(obs.nr_tricks)]
                out = {"card": int(agent.action_play_card(obs)), "valid": valid,
                       "seat_ok": bool(seat == obs.player and winners == list(obs.trick_winner[:obs.nr_tricks]))}
        except Exception as e:  # report and carry on: the adapter falls back and logs it
            traceback.print_exc()
            out = {"error": f"{type(e).__name__}: {e}"}
        answers.write(json.dumps(out) + "\n")


if __name__ == "__main__":
    main()
