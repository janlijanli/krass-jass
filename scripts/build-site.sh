#!/usr/bin/env bash
# Build the serverless site into site/.
#
# Everything runs in the browser: the Rust engine compiled to wasm, the same rendering code
# the hosted version uses, and no network calls after load. Output is plain static files —
# GitHub Pages, or any file server.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "building wasm…"
(cd rust && cargo build --release --target wasm32-unknown-unknown \
    --no-default-features --features wasm)

mkdir -p site
cp rust/target/wasm32-unknown-unknown/release/krass_jass_core.wasm site/
cp web/static/table.css web/static/cards.js site/
python3 scripts/make_site.py

wasm=site/krass_jass_core.wasm
echo "site/ ready — $(wc -c < "$wasm" | tr -d ' ') bytes wasm, $(gzip -9 -c "$wasm" | wc -c | tr -d ' ') gzipped"
echo "serve it:  python3 -m http.server 8124 --directory site"
