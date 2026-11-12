# Opponents from the Zühlke Jass Challenge era — triage

Checked 2026-11-11 on branch `claude/opponent-challenge`. Clones live outside the repo in
`/home/user/ext/<owner>_<repo>` (`GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 ...`); nothing of theirs
is in this repository. Harness: `arena/opponents/common.py` (logged double round, resumable per-deal
file, `--report` with a per-contract / declaring-side breakdown).

Running the cloned code needed the owner's permission (the session's auto-mode classifier refuses it
otherwise); granted 2026-11-11 for DonaldTrumpf and pyschieber. Opponents run sandboxed: no network
namespace, and for Node the permission model's read-only grant to its own checkout.

| Repo | Licence | What it is | Verdict |
|---|---|---|---|
| edualc/DonaldTrumpf | MIT | Hand-written rule bot, JS, 4th Zühlke 2017 | **Measured: we take 66.95% ± 12.48%, n = 400, p < 1e-300.** See `donald_trumpf.md`. |
| Murthy10/pyschieber | MIT | Python Schieber engine; players: random, greedy, `ChallengePlayer` (rule-based, card counter, per-mode strategies, shoves when no mode scores > 54) | **Measured: we take 62.39% ± 11.35%, n = 400, p < 1e-300.** See `pyschieber.md`. `ChallengePlayer` is a real strategy; greedy/random are floor rungs only. Generator-based (`yield card`, then `allowed`), stateful via `move_made`; drive it from a replayed history in its own Python process as the JS bridge does. |
| Xavier0301/JassMCTS | **none** (all rights reserved: run locally only) | EPFL CS-108 "Javass" + MCTS players (`MctsPlayer`, `ImprovedMctsPlayer`, root/leaf-parallel), default 10,000 iterations, Java, no build file (Eclipse zip) | Runnable in principle (`javac` over `src/`), but **Javass is not Schieber**: trump is drawn at random among the four suits, there is no Obenabe/Undenufe and no shoving. Only its card play in suit contracts can be measured; it needs a table with suit contracts only on both sides, which our engine has no flag for. Lower priority. |
| urbanetter/jassy | MIT (composer.json; no LICENSE file) | PHP card-play strategies (`Simple`, `Bock`, `TeamMate`, `Trump`) with knowledge modules (voids, Bock, team-mate signals); still active (2026-04) | Needs PHP ≥ 8.5, container has 8.3. No trump-selection code found: card play only. Measure after pyschieber, with our selector bidding for it. |
| edualc/schieber | GPL-3.0 | Python Schieber, 225 lines | **No strategy**: `choose_trumpf` and `choose_card` are `random.choice` (marked TODO). Skip. |
| jakeret/elbotto | GPL-3.0 | Python challenge client: `stochastic.Bot` (random card, fixed trump) and a DQN `rlagent` | **No trained weights** in the repo; the DQN would have to be trained first. The stochastic bot is random. Skip. |
| stefanjaeger/javascript-jass-bot | none | Client *library* for the challenge server; examples play random cards | No strategy. Skip. |
| nioe/jassBot | none | 60 lines on the library above: trump = suit with most cards (+Nell, +Buur), card = random from the whole hand (may be illegal) | No real strategy. Skip. |
| nicolaszy/jassBot | MIT | README and LICENSE only | Empty. Skip. |
| webplatformz/challenge | MIT | The challenge server (protocol reference) | Used as the protocol reference for the bridge, not run. |

Protocol notes (from `webplatformz/challenge`, `server/game` and `shared/messages`): cards are
`{number: 6..14, color}` with 11 = Jack, 14 = Ace; game types `{mode: TRUMPF|OBEABE|UNDEUFE|SCHIEBE,
trumpfColor}`. A client never sees a seat number: it gets `PLAYED_CARDS` (the trick so far) after every
card, `BROADCAST_STICH` with the winner's *name* after every trick, and `REQUEST_CARD` with the trick on
the table. Both bots of a team share a name. On a shove the server broadcasts `SCHIEBE` and then asks
the partner with `REQUEST_TRUMPF(true)`.
