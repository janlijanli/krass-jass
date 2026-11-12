"""Bridge server for luegl/JassAI (PPO, PyTorch). Runs in its own venv: see docs/opponents/luegl.md.

    <venv>/bin/python -I luegl_server.py <checkout> [checkpoint]

Translates the bridge's neutral messages (our card indices and seats, `arena/opponents/bridge.py`)
into the arguments their `PPOAgent.act_trump` / `act_card` take, *exactly as their `train.py`
built them*: `leader_seat` is the leader of the current trick, `my_team` the seat's team (their
teams are seats 0&2 and 1&3, and play goes seat+1, the same as ours, so our seats are their
seats), `team_punkte` the game score (0:0 — each of our deals is a game's first round) and
`team_punkte_runde` the round's points so far, counted with their own `Karte.punkte` and
`Karte.schlaegt` (their engine adds the +5 last-trick bonus only at the end, so it never shows
here). Inference mode (`training = False`): argmax, as their `rl_bot.py` and `versus.py` play.
"""

import json
import os
import sys

checkout = sys.argv[1]
ckpt = sys.argv[2] if len(sys.argv) > 2 else os.path.join(checkout, "checkpoints", "rl_checkpoint_latest.pt")
sys.path.insert(0, checkout)
os.chdir(checkout)

import torch  # noqa: E402

torch.set_num_threads(1)

from jass_2 import Karte  # noqa: E402
from rl_agent import PPOAgent  # noqa: E402

# Our suits D H S C -> their Schellen, Rosen, Schilten, Eichel. Any bijection would do (nothing
# in their encoding favours a suit); this is the usual French<->German correspondence.
SUIT = {0: "Schellen", 1: "Rosen", 2: "Schilten", 3: "Eichel"}
SUIT_BACK = {v: k for k, v in SUIT.items()}
# Our ranks A K Q J T 9 8 7 6 -> their values.
RANK = ["As", "König", "Ober", "Under", "Banner", "9", "8", "7", "6"]
CONTRACT = {0: SUIT[0], 1: SUIT[1], 2: SUIT[2], 3: SUIT[3], 4: "Obenabe", 5: "Undenufe"}
CONTRACT_BACK = {v: k for k, v in CONTRACT.items()}


def karte(c: int) -> Karte:
    return Karte(SUIT[c // 9], RANK[c % 9])


def index(k: Karte) -> int:
    return SUIT_BACK[k.farbe] * 9 + RANK.index(k.wert)


def winner(cards, leader, trumpf):
    best, best_i = cards[0], 0
    for i, k in enumerate(cards[1:], 1):
        if k.schlaegt(best, cards[0].farbe, trumpf):
            best, best_i = k, i
    return (leader + best_i) % 4


agent = PPOAgent()
agent.training = False
episode = agent.load(ckpt)
print(f"luegl: loaded {ckpt} (episode {episode})", file=sys.stderr, flush=True)

for line in sys.stdin:
    msg = json.loads(line)
    if msg["op"] == "trump":
        hand = sorted(karte(c) for c in msg["hand"])
        # Their TrumpNet has six outputs and no shove: it never shoves, `muss_wahlen` or not.
        _, _, _, _, trumpf = agent.act_trump(hand, not msg["forehand"])
        reply = {"trump": CONTRACT_BACK[trumpf]}
    else:
        trumpf = CONTRACT[msg["contract"]]
        hand = sorted(karte(c) for c in msg["hand"])
        gegangen, tpr = [], {0: 0, 1: 0}
        for lead, cards in msg["tricks_played"]:
            ks = [karte(c) for c in cards]
            gegangen.extend(ks)
            tpr[winner(ks, lead, trumpf) % 2] += sum(k.punkte(trumpf) for k in ks)
        ausgespielt = [karte(c) for c in msg["trick"]]
        _, _, _, _, k, _ = agent.act_card(hand, ausgespielt, trumpf, gegangen, {0: 0, 1: 0}, tpr,
                                          msg["seat"] % 2, msg["trick_leader"])
        reply = {"card": index(k)}
    sys.stdout.write(json.dumps(reply) + "\n")
    sys.stdout.flush()
