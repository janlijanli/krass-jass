# The serverless build

A whole game of Schieber Jass in one browser tab. No server, no API calls after load, works
offline. The bots are the same Rust DMCTS the hosted version runs, compiled to wasm.

## Try it

```bash
./scripts/build-site.sh
python3 -m http.server 8124 --directory site
# http://127.0.0.1:8124
```

These are plain static files — GitHub Pages, or anything that serves a directory.

## What is here

| | |
|---|---|
| `krass_jass_core.wasm` | the whole engine: rules, Weis, scoring, phase machine, DMCTS |
| `engine.js` | the wasm boundary — integer calls in, one JSON view out |
| `solo.js` | the turn loop and bot pacing that the web service used to do |
| `render.js`, `cards.js`, `table.css` | generated from `web/`, unchanged |

`render.js` and `index.html` are **generated** by `scripts/make_site.py` from the hosted UI,
not maintained separately. Only the transport differs between the two builds; a hand-kept
second copy would drift.

## The honest caveat

All four hands are in this tab's memory. The engine only ever *reports* your own, so the
bots cannot cheat and the per-seat filtering is the same code the server runs — but a
determined human can read the other hands out of devtools.

That is a fair trade for single-player with no server, and it is precisely why multiplayer
stays server-side: there, the boundary is a security property rather than a convention.

## Measured

`bench/wasm.md`: 2.01 ms per move at the serve budget, 1.39× native. The pacing floor is
550 ms, so the search is not what you are waiting for.
