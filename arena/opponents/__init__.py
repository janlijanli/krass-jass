"""External Jass bots seated at our engine's table, one module per opponent.

Nothing in here is imported by `krass_jass/`, and no opponent's code is imported by these
modules: each opponent runs in its own process (and usually its own venv) and is reached over
HTTP. Results go to `arena/opponents/results.jsonl`; the write-up per opponent is in
`docs/opponents/<name>.md`.
"""
