# WebAssembly benchmark

Answers whether the search can run in the browser, so the game could be a static site with
no server and no bot containers.

## Build and run

```bash
cd rust && cargo build --release --target wasm32-unknown-unknown \
    --no-default-features --features wasm
cp target/wasm32-unknown-unknown/release/krass_jass_core.wasm ../bench/
cd ../bench && python3 -m http.server 8123      # then open http://127.0.0.1:8123/wasm.html
```

The wasm target uses plain `extern "C"` exports rather than wasm-bindgen: everything crossing
the boundary is an integer, so no glue has to be generated, and the measurement stays about
the engine rather than the binding layer. Deals are generated *inside* wasm from a seed, so
the timing loop never crosses the boundary — a per-call round trip would dominate a 2μs
rollout and measure the wrong thing.

## Results — 2026-09-10, M2, Chromium

Search budget 40 × 60 = 2,400 iterations, the measured saturation point
(`docs/measurements.md` §3). Thirty fixed seeds per rep, nine reps, median rep.

| | ms per move | iterations/sec |
|---|---|---|
| native (PyO3) | 1.442 | 1,664,246 |
| **wasm, single thread** | **2.010** | **1,194,030** |

**wasm is 1.39× native.** Spread across reps was 2.00–2.11 ms — tight.

**Bundle: 64 KB raw, 23.5 KB gzipped.** Small enough that download time is irrelevant.

## Reading it

A move costs **2 ms in a browser tab**, against a bot pacing floor of 550 ms that exists to
stop bots answering *too* fast. Performance is not the constraint on a client-side build.

This only holds because search saturates at 2,400 iterations. At the literature's 800k the
same engine would need ~670 ms per move in wasm — playable, but no longer free.

## Two traps in measuring this

**Run the benchmarks in isolation.** Measuring DMCTS straight after the endgame solver gave
8.4 ms per move; the same measurement on a fresh page gives 2.01 ms. The endgame solver
allocates heavily and leaves the collector in a state that charges the next benchmark for it.
Every figure above is from a fresh instance with nothing else run first.

**The endgame numbers here are not comparable to `docs/measurements.md`.** This harness builds
positions by keeping the lowest set bits of each hand, which clusters cards into shared suits
and produces much deeper searches than the random positions the native benchmark used. Fixing
the harness to deal randomly is the prerequisite for any endgame comparison; the figures it
currently prints should be ignored.

## What this does not settle

Performance was never the hard part — see the discussion in `docs/webapp-plan.md`. A
client-side build still needs the rest of the rules (bidding, Weis, scoring, the state
machine) moved from Python into Rust so there is one implementation rather than two, and it
gives up the information boundary as a security property, since all four hands would sit in
browser memory.
