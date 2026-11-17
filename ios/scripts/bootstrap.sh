#!/usr/bin/env bash
# Everything between a fresh checkout and "open the project in Xcode", on a Mac:
#
#   ios/scripts/bootstrap.sh
#
# 1. the Rust engine, as Engine/KrassJassCore.xcframework   (needs rustup)
# 2. the app icon, drawn by scripts/make_icon.py            (needs python3)
# 3. the strings, exported from web/static/i18n.js          (needs node; skipped without it —
#    the exported file is in git)
# 4. KrassJass.xcodeproj, from project.yml                  (needs xcodegen)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$here/../.."

"$here/build-rust.sh"

echo "drawing the icon…"
python3 - "$root" <<'PY'
import pathlib, sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "scripts"))
import make_icon
out = root / "ios/KrassJass/Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png"
out.write_bytes(make_icon.render(1024))
print(out)
PY

if command -v node >/dev/null; then
  node "$here/make-strings.mjs"
else
  echo "node not found — keeping the strings.json that is in git"
fi

if command -v xcodegen >/dev/null; then
  (cd "$here/.." && xcodegen generate)
  echo "open ios/KrassJass.xcodeproj"
else
  echo "xcodegen not found — 'brew install xcodegen', then run 'xcodegen generate' in ios/" >&2
  exit 1
fi
