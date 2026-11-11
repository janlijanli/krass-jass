"""A stand-in opponent for testing the bridge: random legal card, shoves a third of the time.

Ours, stdlib only, so `python -m arena.opponents.match standin` exercises every part of the
plumbing (process per worker, wire format, legality check, records, report) without running any
external code. Seeded from the message, so a rerun plays the same cards.
"""

import json
import random
import sys

for line in sys.stdin:
    msg = json.loads(line)
    rng = random.Random(line)
    if msg["op"] == "trump":
        reply = {"trump": "shove" if msg["forehand"] and rng.random() < 1 / 3 else rng.randrange(6)}
    else:
        reply = {"card": rng.choice(msg["legal"])}
    sys.stdout.write(json.dumps(reply) + "\n")
    sys.stdout.flush()
