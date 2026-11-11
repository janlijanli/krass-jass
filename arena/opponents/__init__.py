"""Other people's Jass bots, seated at our engine's table.

Each opponent runs in its own process — usually its own venv, with its own pinned
dependencies — and is talked to over the JSON stdin/stdout bridge in `bridge.py`. Nothing of
theirs is imported into this process: several have no licence (all rights reserved, so we run
them locally as opponents and do nothing else with them) and none may enter our dependency
graph. The server scripts under `servers/` are ours; they put the opponent's checkout on
`sys.path` and translate between the bridge's neutral format and the opponent's own encoding.

`match.py` plays our bot against any of them (double rounds, paired test, resumable).
Results: `docs/opponents/<name>.md`, one line per run in `arena/opponents/results.jsonl`.
"""
