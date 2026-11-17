#!/usr/bin/env bash
# Build the engine as a native static library and play whole games through the C header.
# Needs cargo and a C compiler; no Xcode, so it runs in CI on Linux too.
#
#   ios/tests/run-ffi-smoke.sh                 # whole games, all three modes
#   ios/tests/run-ffi-smoke.sh --check-views   # short games, every view held against TableState.swift
set -euo pipefail
cd "$(dirname "$0")/../.."
(cd rust && cargo rustc --release --lib --no-default-features --features wasm --crate-type staticlib)
out="$(mktemp -d)"
cc -O1 -Wall -Wextra -Iios/Engine/include ios/tests/ffi_smoke.c \
   rust/target/release/libkrass_jass_core.a -lpthread -ldl -lm -o "$out/ffi_smoke"
if [ "${1:-}" = "--check-views" ]; then
  KJ_DUMP="$out/views.jsonl" "$out/ffi_smoke"
  python3 ios/tests/check_views.py "$out/views.jsonl"
else
  "$out/ffi_smoke"
fi
