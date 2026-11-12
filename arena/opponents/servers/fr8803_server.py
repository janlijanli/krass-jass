"""Bridge server for FR8803/JassOpenAIGym's DQN (TF-Agents, bachelor thesis 2021). No licence.

    <venv>/bin/python -I fr8803_server.py <checkout> [Game|Round|Trick|Hybrid|Hybrid random]

What the trained policy actually is (read from their `gym_Jass/envs/Jass_env.py` and `Jass_RL.ipynb`):

- The Q-network has **8 outputs** (`action_space = Discrete(8)`, no action mask), but the env's card
  action IDs are 0–35 and its trump action IDs 36–42. Their `_decode_action` plays the action if it
  is a legal ID and otherwise **a uniformly random legal action**. So the net can only ever name deck
  cards 0–7: Schellen A K Q J 10 9 8 7, which are our ♦A…♦7 (their deck order is ours, with
  D/H/S/C = Schellen/Rosen/Schilten/Eichel). Any other move, and every trump choice, is random.
- Trump: uniformly random among their legal trump actions. From forehand that is seven (the six
  contracts and "Gschobe", the shove); from the shoved-to partner, six.

That is reproduced here exactly: argmax over the 8 Q-values; play it if it is a legal card, else a
random legal card; random trump. Legality is ours (the bridge's `legal`): it is what their
`legal_ids` test would see, apart from the rule details our engine settles authoritatively anyway.

The network is run from its checkpoint variables
(`Data_BA/<model>/rl_jass/variables/variables`, fetched from Git LFS) as the standard TF-Agents
`QNetwork` it was built as: flatten the 5×4×9 observation (180) → Dense 128 ReLU → Dense 36 ReLU →
Dense 8. Their `saved_model.pb` cannot be loaded without tf-agents' type registrations, and
the variables are the same weights. The observation is built with their own `encode_cards` /
`encode_stich`, as their `_extract_observation` builds it: the hand, the current trick, the
round's earlier tricks, the legal cards, and the trump plane. `random` and numpy are seeded from
the request.
"""

import hashlib
import json
import random
import sys
import types
from pathlib import Path

import numpy as np

checkout = Path(sys.argv[1])
model = sys.argv[2] if len(sys.argv) > 2 else "Game"
sys.path.insert(0, str(checkout))
# `gym_Jass/__init__.py` imports gym to register the env; only the card encoding is needed here.
for name, sub in (("gym_Jass", ""), ("gym_Jass.Schieber", "Schieber")):
    pkg = types.ModuleType(name)
    pkg.__path__ = [str(checkout / "gym_Jass" / sub)]
    sys.modules[name] = pkg

import tensorflow as tf  # noqa: E402

from gym_Jass.Schieber.card import JassCard, init_swiss_deck  # noqa: E402
from gym_Jass.Schieber.util import encode_cards, encode_stich  # noqa: E402

DECK = init_swiss_deck()  # their action ID i is DECK[i]; the same order as our card indices
TRUMP = {0: "Trumps.SCHELLE", 1: "Trumps.ROSE", 2: "Trumps.SCHILTE", 3: "Trumps.EICHEL",
         4: "Trumps.OBENABE", 5: "Trumps.UNDENUFE"}

reader = tf.train.load_checkpoint(str(checkout / "Data_BA" / model / "rl_jass" / "variables" / "variables"))
W = [reader.get_tensor(f"model_variables/{i}/.ATTRIBUTES/VARIABLE_VALUE") for i in range(6)]
print(f"fr8803: model {model}, layers {[w.shape for w in W[::2]]}", file=sys.stderr, flush=True)


def q_values(obs: np.ndarray) -> np.ndarray:
    x = obs.astype(np.float32).reshape(-1)
    x = np.maximum(x @ W[0] + W[1], 0)
    x = np.maximum(x @ W[2] + W[3], 0)
    return x @ W[4] + W[5]


def strs(cards):
    return [str(DECK[c]) for c in cards]


def observation(msg) -> np.ndarray:
    obs = np.zeros((9, 4, 9), dtype=int)
    encode_cards(obs[:2], strs(msg["hand"]), "hand")
    encode_cards(obs[2:4], strs(msg["trick"]), "hand")
    encode_cards(obs[4:6], strs([c for _, cards in msg["tricks_played"] for c in cards]))
    encode_cards(obs[6:8], strs(msg["legal"]))
    encode_stich(obs[8], TRUMP[msg["contract"]])
    return np.delete(obs, [0, 2, 4, 6], 0)


assert all(isinstance(c, JassCard) for c in DECK) and len(DECK) == 36

for line in sys.stdin:
    msg = json.loads(line)
    rng = random.Random(int.from_bytes(hashlib.sha256(line.encode()).digest()[:8], "little"))
    try:
        if msg["op"] == "trump":
            options = [0, 1, 2, 3, 4, 5] + (["shove"] if msg["forehand"] else [])
            reply = {"trump": rng.choice(options)}
        else:
            a = int(np.argmax(q_values(observation(msg))))
            reply = {"card": a if a in msg["legal"] else rng.choice(msg["legal"]), "net": a}
    except Exception as e:  # reported to the bridge, which logs it and falls back
        reply = {"error": repr(e)}
    sys.stdout.write(json.dumps(reply) + "\n")
    sys.stdout.flush()
