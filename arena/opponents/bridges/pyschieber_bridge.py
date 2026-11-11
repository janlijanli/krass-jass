"""Drives a pyschieber player (Murthy10/pyschieber, MIT) from a replayed history, one JSON request
per stdin line, one answer per stdout line. Run in its own interpreter, isolated from ours:

    python -I pyschieber_bridge.py <pyschieber checkout> [player class, default ChallengePlayer]

Every line builds a fresh player and calls it exactly as `pyschieber/game.py` would have up to the
decision at hand: `id` set first (its card counter reads it when the ninth card arrives), the nine
cards through `set_card`, then for every card played so far — in play order — the player's own
`choose_card` generator when it was its turn (its first-trick role is set in there), the card leaving
its hand, and `move_made(player_id, card, state)` with the state *before* that card reached the table,
which is when the game broadcasts it. The answer is the first value of the final generator.

Request: {"op": "trumpf", "hand": [...], "geschoben": bool, "seed": int}
         {"op": "card", "seat": int, "hand": [...], "trumpf": "ROSE", "geschoben": bool, "seed": int,
          "tricks": [{"leader": int, "cards": [...], "winner": int}, ...],
          "leader": int, "table": [...]}
Cards are pyschieber strings ("<ROSE:Ass>"); the table's trick has no winner yet.
"""

import json
import random
import sys

sys.path.insert(0, sys.argv[1])
CLASS = sys.argv[2] if len(sys.argv) > 2 else "ChallengePlayer"

from pyschieber.card import from_string_to_card  # noqa: E402

if CLASS == "ChallengePlayer":
    from pyschieber.player.challenge_player.challenge_player import ChallengePlayer as Player  # noqa: E402
elif CLASS == "GreedyPlayer":
    from pyschieber.player.greedy_player.greedy_player import GreedyPlayer as Player  # noqa: E402
else:
    raise SystemExit(f"unknown player {CLASS}")


def fresh(seat, hand):
    player = Player(name=CLASS)
    player.id = seat
    for text in hand:
        player.set_card(from_string_to_card(text))
    return player


def state(stiche, table, trumpf, geschoben):
    return dict(stiche=stiche, trumpf=trumpf, geschoben=geschoben, point_limit=1500,
                table=list(table), teams=[dict(points=0), dict(points=0)])


def card_request(req):
    me = req["seat"]
    player = fresh(me, req["hand"])
    trumpf, geschoben = req["trumpf"], req["geschoben"]
    stiche = []
    tricks = req["tricks"] + [{"leader": req["leader"], "cards": req["table"], "winner": None}]
    for trick in tricks:
        table = []
        for k, text in enumerate(trick["cards"]):
            pid = (trick["leader"] + k) % 4
            before = state(stiche, table, trumpf, geschoben)
            card = from_string_to_card(text)
            if pid == me:
                next(player.choose_card(state=before))  # what the game asks; the card is known
                player.cards.remove(card)
            player.move_made(pid, card, before)
            table.append({"player_id": pid, "card": text})
        if trick["winner"] is not None:
            stiche.append({"player_id": trick["winner"], "trumpf": trumpf, "played_cards": table})
    return str(next(player.choose_card(state=state(stiche, table, trumpf, geschoben))))


def run(req):
    random.seed(req.get("seed", 0))  # ChallengePlayer falls back to random.choice
    if req["op"] == "trumpf":
        player = fresh(0, req["hand"])
        return {"trumpf": next(player.choose_trumpf(geschoben=req["geschoben"])).name}
    return {"card": card_request(req)}


for line in sys.stdin:
    try:
        answer = run(json.loads(line))
    except Exception as e:  # noqa: BLE001
        import traceback

        answer = {"error": traceback.format_exc()[-1500:]}
    sys.stdout.write(json.dumps(answer) + "\n")
    sys.stdout.flush()
