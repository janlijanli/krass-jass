"""What the search is trying to maximise.

Until now: the team's share of the round's card points. That is the right objective for a
round played in isolation and the wrong one for a game, and the difference only shows up near
the finishing line. At 940 chasing 1000 a team needs sixty points, not as many as possible —
a certain sixty beats a gamble on ninety-or-twenty, and the share objective cannot tell those
apart because it is linear in points and the game is not.

So the reward is the projected **game** outcome instead: where this round leaves the two
scores, and how good that is.

    crossed the target, alone      → 1
    the opponents crossed, alone   → 0
    both crossed                   → 1/2, see below
    neither                        → a logistic in the resulting lead

A monotone transform of round points would change nothing — the argmax would be identical.
What does the work is that this one *saturates*: once the line is crossed, more points are
worth nothing, and MCTS averages the reward over determinizations and rollouts rather than
maximising it pointwise. `E[f(X)]` with `f` flat at the top is exactly a preference for the
certain sixty. That is the whole mechanism, and it is why the shape matters more than the
constants.

Two honest gaps:

- **Both teams crossing is scored 1/2.** Who actually wins is decided by the claim order
  (Stöck, Weis, Stich — `rules.claim_order`), which depends on Weis nobody has announced yet
  in the worlds being searched. Half is the least wrong constant; modelling it properly means
  the search carrying the claim sequence, which is a bigger change than this one.
- **Stöck is not in the projection.** It is worth twenty and, unlike Weis, is private until
  the second honour is played, so feeding it to the agent would hand it information the table
  does not have. Weis is public once called and is included.
"""

from __future__ import annotations

import math

#: Roughly what one team takes in an ordinary round — used to turn "points still needed"
#: into "rounds still to play".
ROUND_POINTS = 81.0

#: Standard deviation of one round's *point difference*. `docs/measurements.md` §1 puts the
#: per-deal share at about 8% sd, and a difference is twice a share either side of the 162
#: on the table: 2 x 0.08 x 162 ≈ 26.
ROUND_DIFF_SD = 26.0

#: Where the projection takes over from the round, measured in rounds still to play.
#:
#: Both earlier versions of this weighted the game outcome everywhere and both lost — 44.62%
#: and then 46.88% over a 2500-point game (`docs/measurements.md` §5d). The second attempt
#: fixed the scale and kept losing, which is what finally said the shape was wrong rather
#: than the constants.
#:
#: With twenty-five rounds to play, one round genuinely barely moves the win probability.
#: That is not a miscalibration, it is the truth — and it is fatal, because it means nearly
#: every rollout comes back at ~0.5 and UCT has nothing left to tell the moves apart. A
#: correct objective with no variance is a worse search than a proxy with plenty.
#:
#: So the projection only takes over as the line comes into reach. Far from it the reward is
#: the round's share, bit for bit what the bot did before, which is why this version cannot
#: lose ground where the last two did.
GAME_FROM = 1.0    #: rounds left at which the projection is the whole reward
GAME_UNTIL = 4.0   #: and beyond which it counts for nothing


#: Share below which a round counts as a bad one, for the risk term.
RISK_THRESHOLD = 0.4


def risk_adjust(share: float, lam: float) -> float:
    """Dislike the rounds where you get buried, more than linearly.

    Determinized search is systematically **over-optimistic**: inside every imagined world it
    knows the layout, so it believes it can dodge disasters it cannot actually see coming.
    A risk-averse reward is a deliberate distortion to offset a known one.

    It has to be non-linear or it does nothing at all, and the obvious form is the trap. A
    penalty of `(ours - lam * theirs) / total` expands to `(1 + lam) * share - lam` — an
    *affine* transform of the share — and MCTS picks the child with the highest mean reward,
    so an affine transform cannot change which child that is. It would measure exactly
    nothing. (It does quietly rescale the value against UCT's unscaled exploration term, so
    it is a disguised exploration-constant change, which is a different experiment.)

    What survives is the **kink**: slope `1 + lam` below the threshold and `1` above, which is
    concave, which is risk aversion. The renormalisation afterwards is affine and therefore
    cosmetic — it keeps the reward in [0, 1] for UCT and for the opponent flip, and changes
    no decision.
    """
    if lam <= 0.0:
        return share
    f = share - lam * max(0.0, RISK_THRESHOLD - share)
    lo = -lam * RISK_THRESHOLD
    return (f - lo) / (1.0 - lo)


def reward(
    ours: int,
    theirs: int,
    scores: tuple[int, int],
    bonus: tuple[int, int],
    target: int | None,
    multiplier: int,
    team: int,
    risk_lambda: float = 0.0,
) -> float:
    """Value in [0, 1] of finishing the round with `ours`/`theirs` card points.

    `scores` is the game score before this round, `bonus` the Weis already banked in it, both
    in team order. `target` of `None` or 0 means there is no game to project onto, and the
    objective falls back to the share of the round — which is what the arena's round-level
    matches measure and what every number in `docs/measurements.md` before §5d was taken with.
    """
    total = ours + theirs
    share = risk_adjust(0.5 if total == 0 else ours / total, risk_lambda)
    if not target:
        return share

    mult = max(1, multiplier)
    mine = scores[team] + (ours + bonus[team]) * mult
    yours = scores[1 - team] + (theirs + bonus[1 - team]) * mult

    # How much game is left, and therefore how much the projection is worth saying anything
    # about. A crossed line leaves `remaining` at 1, so the branches below get full weight
    # without needing to special-case themselves.
    remaining = max(1, target - max(mine, yours))
    rounds_left = remaining / (ROUND_POINTS * mult)
    weight = (GAME_UNTIL - rounds_left) / (GAME_UNTIL - GAME_FROM)
    weight = min(1.0, max(0.0, weight))
    if weight == 0.0:
        return share

    def blend(p: float) -> float:
        return weight * p + (1.0 - weight) * share

    if mine >= target and yours < target:
        return blend(1.0)
    if yours >= target and mine < target:
        return blend(0.0)
    if mine >= target and yours >= target:
        # The claim order decides this, and the search cannot see it. See the module note.
        return blend(0.5)

    # How much game is left, and therefore how much a lead is worth. A lead matters relative
    # to what can still happen to it: 400 points ahead is decisive with one round to play and
    # means very little with twenty-five.
    #
    # Getting this wrong is not a small mis-calibration, it is fatal, and it was measured
    # being fatal — see `docs/measurements.md` §5d. A scale of one round's points made the
    # reward saturate on any real lead, so every move scored ~1.0, the search had no gradient
    # left to steer by, and the bot lost 44.62% to 55.38% over a 2500-point game while
    # drawing level over a 1000-point one. The longer the game, the more of it was spent in
    # that dead zone.
    #
    # Points accumulate like a random walk, so the spread of what is still to come grows with
    # the square root of the rounds remaining — which keeps the reward sensitive early, when
    # there is everything to play for, and sharpens it near the line, which is the whole point
    # of having a game objective at all.
    scale = max(1.0, ROUND_DIFF_SD * mult * math.sqrt(max(1.0, rounds_left)))
    return blend(1.0 / (1.0 + math.exp(-(mine - yours) / scale)))
