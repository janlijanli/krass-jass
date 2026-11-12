"""Bridge server for AlessioVerardo/jass-reinforcement-learning's PIMC agent (MIT).

    <venv>/bin/python -I verardo_pimc_server.py <checkout> [K] [n_sims]

Their `PIMC` (jass/agents/pimc.py): K sampled worlds (default 20), plain UCB1 MCTS with random
rollouts in each (n_sims = 50, c = 1.41), Q-values averaged over worlds, argmax. Trump: every legal
option scored by the same search over K worlds (4K for a shove, whose partner is modelled by their
heuristic). Needs no trained weights. Their defaults are the defaults here.

**Their engine has suit trumps only — no Obenabe, no Undenufe** — so this server answers an
Obenabe/Undenufe round with an error (the bridge logs it and plays our lowest legal card). Measure it
on the suit-only table (`match.py --cfg suits`), where neither side can name one.

Translation. Their seats play in the order seat+1 with teams P0&P2 / P1&P3, as ours, so seats are
the same numbers. Their `Card` index is `color * 9 + height` with heights A K Q J 10 9 8 7 6 (the same
order as our ranks) and colors SPADE HEART CLUB DIAMOND; our suits D H S C map to 3 1 0 2. Their
`JassEngine` state is rebuilt for each request by replaying the round's public tricks through their
own `play_card` / `resolve_trick` (which is also how their void flags and scores arise); the other
seats' unseen cards start as filler of the right count, which their `sample_world` redeals in
every world. Their worker pool is replaced by an in-process `map`: our match already runs one server
per core. `random` is seeded from the request, so a rerun plays the same cards.
"""

import hashlib
import json
import random
import sys
import types
from pathlib import Path

checkout = Path(sys.argv[1])
K = int(sys.argv[2]) if len(sys.argv) > 2 else 20
N_SIMS = int(sys.argv[3]) if len(sys.argv) > 3 else 50
sys.path.insert(0, str(checkout))

# `jass/agents/__init__.py` imports their DQN (pydantic, torchrl, ...). PIMC needs none of it, so
# register the package empty and import only the module.
_pkg = types.ModuleType("jass.agents")
_pkg.__path__ = [str(checkout / "jass" / "agents")]
sys.modules["jass.agents"] = _pkg

import torch  # noqa: E402

torch.set_num_threads(1)

from jass.agents.pimc import PIMC  # noqa: E402
from jass.constant import Color, Phase  # noqa: E402
from jass.environment.engine import JassEngine  # noqa: E402

COLOR = {0: 3, 1: 1, 2: 0, 3: 2}            # our suit -> their Color value
SUIT = {v: k for k, v in COLOR.items()}     # their Color value -> our suit


def theirs(c: int):
    return JassEngine.idx_to_card(COLOR[c // 9] * 9 + c % 9)


def ours(card) -> int:
    return SUIT[int(card.color)] * 9 + int(card.height)


class _Inline:
    def map(self, fn, tasks):
        return map(fn, tasks)


class _Env:  # the three attributes PIMC reads from its JassEnv
    def __init__(self, first_player, trump_chooser, current_player):
        self.first_player, self.trump_chooser, self.current_player = first_player, trump_chooser, current_player


def _engine(seat, hand, played_by, trump, chooser, forehand):
    """A JassEngine dealt so that replaying the public tricks reaches the current position."""
    eng = JassEngine()
    seen = set(hand) | {c for cs in played_by.values() for c in cs}
    pool = [c for c in range(36) if c not in seen]
    for p in range(4):
        cards = list(played_by.get(p, []))
        if p == seat:
            cards += hand
        else:
            need = 9 - len(cards)
            cards += pool[:need]
            pool = pool[need:]
        eng.hands[p] = [theirs(c) for c in cards]
    eng.set_trump(Color(COLOR[trump]), first_player=forehand, trump_chooser=chooser)
    return eng


agent = PIMC(env=None, K=K, n_sims=N_SIMS, c=1.41)
agent._pool = _Inline()
print(f"verardo-pimc: K={K} n_sims={N_SIMS}", file=sys.stderr, flush=True)

for line in sys.stdin:
    msg = json.loads(line)
    random.seed(int.from_bytes(hashlib.sha256(line.encode()).digest()[:8], "little"))
    try:
        if msg["op"] == "trump":
            # Seat the chooser as forehand at 0, or as the shoved-to partner at 2 with forehand 0.
            seat, phase = (0, Phase.TRUMP_0A) if msg["forehand"] else (2, Phase.TRUMP_0B)
            eng = _engine(seat, msg["hand"], {}, 0, 0, 0)
            eng.trump = None
            agent.env = _Env(0, 0, seat)
            mask = torch.zeros(5)
            mask[: 5 if msg["forehand"] else 4] = 1
            action = agent.trump_action(eng, seat, mask, phase)
            reply = {"trump": "shove" if action == 4 else SUIT[action]}
        else:
            if msg["contract"] > 3:
                raise ValueError("their engine has no Obenabe/Undenufe")
            seat, trump = msg["seat"], msg["contract"]
            tricks = [(lead, cards) for lead, cards in msg["tricks_played"]]
            current = (msg["trick_leader"], msg["trick"])
            forehand = tricks[0][0] if tricks else current[0]
            played_by = {}
            for lead, cards in tricks + [current]:
                for i, c in enumerate(cards):
                    played_by.setdefault((lead + i) % 4, []).append(c)
            eng = _engine(seat, msg["hand"], played_by, trump, msg["declarer"], forehand)
            eng.schieben = msg["declarer"] != forehand
            for lead, cards in tricks:
                eng.current_player = lead
                for c in cards:
                    eng.play_card(eng.current_player, theirs(c))
                eng.resolve_trick()
            eng.current_player = current[0]
            for c in current[1]:
                eng.play_card(eng.current_player, theirs(c))
            assert eng.current_player == seat, (eng.current_player, seat)
            assert sorted(ours(k) for k in eng.hands[seat]) == sorted(msg["hand"])
            idx = agent.card_action(eng, seat, eng.get_valid_move_mask(seat))
            reply = {"card": ours(JassEngine.idx_to_card(idx))}
    except Exception as e:  # reported to the bridge, which logs it as an error and falls back
        reply = {"error": repr(e)}
    sys.stdout.write(json.dumps(reply) + "\n")
    sys.stdout.flush()
