#!/usr/bin/env bash
# Build the Rust engine as a static library for iOS and wrap it in an XCFramework.
#
#   ios/scripts/build-rust.sh          # device + simulator (arm64 and x86_64)
#
# Output: ios/Engine/KrassJassCore.xcframework, which project.yml links. Not in git — it is a
# build product, like site/krass_jass_core.wasm.
#
# The crate is built exactly as for the browser (`--no-default-features --features wasm`): the
# same C functions, the same search, no Python. `--crate-type staticlib` is given here rather
# than in Cargo.toml so that the Python and wasm builds do not grow an archive nobody links.
set -euo pipefail
cd "$(dirname "$0")/../.."

TARGETS=(aarch64-apple-ios aarch64-apple-ios-sim x86_64-apple-ios)
OUT=ios/Engine/KrassJassCore.xcframework
LIB=libkrass_jass_core.a

if ! command -v rustup >/dev/null; then
  echo "rustup not found — install Rust from https://rustup.rs first" >&2
  exit 1
fi
rustup target add "${TARGETS[@]}"

# The deployment target the app is built for (project.yml); without it rustc picks its own
# minimum and the linker warns about every object file.
export IPHONEOS_DEPLOYMENT_TARGET=17.0

for target in "${TARGETS[@]}"; do
  echo "building ${target}"
  (cd rust && cargo rustc --release --lib --target "$target" \
      --no-default-features --features wasm --crate-type staticlib)
done

# One fat library for the simulator: Apple Silicon and Intel Macs.
SIM=rust/target/ios-sim-universal
mkdir -p "$SIM"
lipo -create \
  "rust/target/aarch64-apple-ios-sim/release/$LIB" \
  "rust/target/x86_64-apple-ios/release/$LIB" \
  -output "$SIM/$LIB"

rm -rf "$OUT"
xcodebuild -create-xcframework \
  -library "rust/target/aarch64-apple-ios/release/$LIB" \
  -library "$SIM/$LIB" \
  -output "$OUT"

echo "$OUT ready"
