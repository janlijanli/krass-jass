# Krass Jass for iOS

A native SwiftUI app over the same Rust engine the server and the browser build run. One human
on seat 0, three bots, no server, no network: Schieber, Sidi Barrani and Coiffeur.

```
ios/
  project.yml                 XcodeGen spec — the .xcodeproj is generated, not committed
  Engine/include/             the engine's C interface (krass_jass_core.h)
  KrassJass/App/              app entry, start screen over table
  KrassJass/Engine/           Engine.swift (FFI + engine thread), TableState.swift (the view),
                              GameController.swift (turn loop, bot pacing, save/resume)
  KrassJass/UI/               the table: card art, card layer, panels, scorecard, settings
  KrassJass/Resources/        strings.json (exported from web/static/i18n.js), asset catalog
  scripts/                    bootstrap.sh, build-rust.sh, make-strings.mjs
  tests/                      C smoke test and the view-model check — run on Linux, in CI
```

## Build

On a Mac with Xcode 16 or newer:

```bash
brew install xcodegen          # once
# rustup from https://rustup.rs, once

ios/scripts/bootstrap.sh       # engine → XCFramework, icon, strings, KrassJass.xcodeproj
open ios/KrassJass.xcodeproj
```

Pick a simulator or a phone and run. For a phone, set your team under *Signing & Capabilities*
(the bundle id is `ch.krassjass.app`; change it in `project.yml` if it is taken).

After changing Rust code, run `ios/scripts/build-rust.sh` again. After adding or removing Swift
files, run `xcodegen generate` in `ios/` (or `bootstrap.sh`).

## How it fits together

**The engine is not ported, it is linked.** `rust/src/wasm_api.rs` already exposes the whole
game as plain C functions for the browser build — integer calls in, one JSON view out.
`build-rust.sh` compiles the crate with the same features (`--no-default-features --features
wasm`) as a static library for device and simulator. Rules, Weis, scoring, the phase machine,
ISMCTS at 153,600 iterations, the play model, the conventions, the Sidi bidder, the Coiffeur
row choice: all the same code, so the standing rule that the rules exist exactly twice (Python
and Rust) still holds. There is no third implementation in Swift.

**One thread owns the engine.** The crate keeps its games in a thread-local registry (wasm has
one thread). `Engine.swift` therefore runs every call on a single dedicated thread — not a
dispatch queue, which may hop threads — with a 16 MB stack for the search. The UI awaits it.

**The information boundary holds.** The app only ever asks for seat 0's view
(`game_view(handle, 0, …)`), which is `build_observation`'s shape: own hand, public history,
legal moves. No other hand reaches Swift. As in the browser build, all four hands are in the
process's memory; that is the accepted trade for single-player without a server.

**`GameController` is `site-src/solo.js` in Swift**: the turn loop, bot pacing (the pause is what
is left of the target after the search), the Sidi knock, advice from a fourth bot on the
player's seat, and resume — the game is saved as seed + settings + every move, and replayed on
launch, which lands on the same position bit for bit.

**The wording is the web UI's.** `make-strings.mjs` exports `web/static/i18n.js` to
`strings.json` (en, de, fr, it). Edit `i18n.js`, re-run; CI fails if the JSON is stale.

**Cards are drawn in code** (`CardArt.swift`), a port of `web/static/cards.js` on the same
100 × 140 grid: suits as paths, standard pips, the three court figures. No image assets.

## Feel

- A card keeps its identity from the fan to the table, so playing it is one view flying — tap
  to lift, tap again to play, or drag / flick it up. A card that may not be played shakes.
- The bots' cards arrive from their seats; a cleared trick leaves towards whoever took it.
- The hand is dealt in card by card; scores roll; the contract badge springs in; a game won
  rains confetti.
- Haptics (`Haptics.swift`) use one vocabulary: a tick for a card lifted, a firm tap for a card
  played, a soft thud for someone else's card, a ripple for the deal and for a match, the
  system's error for an illegal card. Off in the settings.

## Tests

```bash
ios/tests/run-ffi-smoke.sh                 # whole games through the C header, all three modes
ios/tests/run-ffi-smoke.sh --check-views   # every view checked against TableState.swift
```

Both need only cargo, a C compiler and python3, so they run in the Linux CI job. The second
reads the struct declarations out of the Swift source and holds 1,500 real views against them:
a field Swift calls non-optional that the engine sends as null is caught there, not on a phone.
`.github/workflows/ios.yml` compiles the app itself on a Mac runner, launches it in a simulator
and uploads screenshots of the start screen and each game as the `ios-screenshots` artifact
(debug builds take `-kj.autostart <mode>` and `-kj.autoplay <n>` for that).

## Not here yet

- The belief overlay and panel (test mode), the bots' Jass sayings, AI mode's names, the
  walkthrough, and the long-form pages (how it works, report).
- Sounds.
- `tree_policy` stays off, as in the browser build, until it is measured on a phone
  (`docs/measurements.md` §5p: ~11× a move natively).
- A second look at iPad and landscape layout: it scales, it was not designed.
- App Store plumbing: signing team, an icon without an alpha channel, screenshots.
