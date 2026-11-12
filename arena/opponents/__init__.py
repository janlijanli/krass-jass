"""Other people's Jass bots, seated at our engine's table, one module per opponent.

Nothing in here is imported by `krass_jass/`, and no opponent's code is imported into our
process: each opponent runs in its own process (and usually its own venv, with its own pinned
dependencies) and is reached over HTTP or the JSON stdin/stdout bridge in `bridge.py`. Several
have no licence (all rights reserved: we run them locally as opponents and do nothing else with
them), and none may enter our dependency graph. The server scripts under `servers/` are ours.

Results: one line per run in `arena/opponents/results.jsonl`, the write-up per opponent in
`docs/opponents/<name>.md`.
"""
