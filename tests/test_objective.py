"""What the search maximises.

The shape is the point. A monotone transform of round points would change nothing — the
argmax would be identical — so what makes this objective different from a share is that it
**saturates**: past the target, more points are worth nothing. MCTS averages the reward over
determinizations rather than maximising it pointwise, and it is that flat top which turns
`E[f(X)]` into a preference for the certain sixty over the gamble on ninety.
"""

import pytest

from krass_jass.objective import GAME_UNTIL, ROUND_POINTS, reward

core = pytest.importorskip("krass_jass_core", reason="Rust core not built")

NONE = (0, 0)


def r(ours, theirs, scores=NONE, target=1000, multiplier=1, team=0, weis=NONE):
    return reward(ours, theirs, scores, weis, target, multiplier, team)


def test_without_a_target_it_is_the_old_share_objective():
    """Every figure in docs/measurements.md before §5d was taken this way, and EVAL still is:
    no target, so no game to project onto."""
    assert r(100, 62, target=None) == pytest.approx(100 / 162)
    assert r(81, 81, target=0) == pytest.approx(0.5)
    assert r(0, 0, target=None) == pytest.approx(0.5)


def test_crossing_the_line_alone_is_a_win():
    """A crossed line leaves no game to play, so the projection carries the whole reward."""
    assert r(60, 102, scores=(940, 500)) == 1.0
    assert r(10, 152, scores=(500, 940)) == 0.0


def test_both_crossing_is_a_half_because_the_claim_order_decides_it():
    """Honest placeholder rather than a guess: who wins depends on the Stöck-Weis-Stich
    ordering, which the search cannot see."""
    assert r(80, 82, scores=(940, 940)) == pytest.approx(0.5)


def test_it_saturates_past_the_line():
    """The property the whole change rests on: once sixty was enough, a hundred is not worth
    more. Not *exactly* equal — a tenth of the reward is raw share, deliberately, so that a
    decided position still has a gradient — but the win part is flat and the difference is
    bounded by that tenth."""
    sixty = r(60, 102, scores=(940, 0))
    hundred = r(100, 62, scores=(940, 0))
    assert hundred == sixty == 1.0

    # With the line far away the same two outcomes are worth plenty apart, which is what
    # "saturates" is being contrasted with.
    far = r(100, 62, scores=(0, 0), target=2500) - r(60, 102, scores=(0, 0), target=2500)
    assert far > 0.2


def test_the_certain_sixty_beats_the_gamble():
    """Spelled out as the search sees it: an average over worlds, not a single outcome.

    Both teams sit on 940, so the gamble can actually lose the game — which is the only kind
    of position where the property means anything. An earlier version of this test used
    (940, 0), where *both* branches of the gamble win and the assertion passed by 2e-5 for
    entirely the wrong reason.
    """
    safe = [r(60, 102, scores=(940, 940))] * 2                     # sixty, every time
    gamble = [r(100, 62, scores=(940, 940)), r(20, 142, scores=(940, 940))]
    assert sum(safe) / 2 > sum(gamble) / 2 + 0.1, "and not by a hair"

    # Far from the line it is exactly *indifferent* between the two, because there the reward
    # is the round's share and share is linear — a mean-preserving gamble has the same mean.
    # That is the point: the objective takes no view on risk until there is a game reason to.
    safe_far = [r(60, 102, scores=(0, 0), target=2500)] * 2
    gamble_far = [r(100, 62, scores=(0, 0), target=2500),
                  r(20, 142, scores=(0, 0), target=2500)]
    assert sum(gamble_far) / 2 == pytest.approx(sum(safe_far) / 2)


def test_it_is_monotone_in_our_points():
    """Below the line it must still want points: a reward that flattened early would leave
    the search with no gradient and no idea what to play."""
    values = [r(p, 162 - p, scores=(200, 200)) for p in range(0, 163, 10)]
    assert values == sorted(values)
    assert values[-1] > values[0]


def test_a_bigger_multiplier_makes_the_same_round_more_decisive():
    """Under Undenufe every point counts four times, so winning a round by forty moves the
    game four times as far — and there are four times fewer rounds left in which to answer it.

    An earlier version of this test asserted the opposite, that the multiplier cancels. It
    did cancel under the first scale, which measured a lead in rounds and nothing else. It
    should not: a x4 contract really is more decisive, and a reward that shrugged at one was
    part of what the 2500-point measurement caught.
    """
    close = r(100, 62, scores=(0, 0), multiplier=1)
    quad = r(100, 62, scores=(0, 0), multiplier=4)
    assert quad > close + 0.05


def test_weis_counts_towards_the_line():
    """A hundred in Weis is most of a round, and near the target it decides who crosses."""
    without = r(40, 122, scores=(800, 0), weis=(0, 0))
    with_weis = r(40, 122, scores=(800, 0), weis=(160, 0))
    assert with_weis == 1.0
    assert without < with_weis


@pytest.mark.parametrize("ours,theirs,scores,target,mult", [
    (100, 62, (0, 0), 1000, 1),
    (60, 102, (940, 500), 1000, 2),
    (81, 81, (940, 940), 1000, 3),
    (0, 162, (0, 0), 2500, 4),
    (157, 5, (100, 2400), 2500, 1),
    (50, 112, (0, 0), 0, 1),
])
def test_both_implementations_agree(ours, theirs, scores, target, mult):
    mine = reward(ours, theirs, scores, (0, 0), target, mult, 0)
    theirs_ = core.rs_reward(ours, theirs, 0, scores, (0, 0), target, mult)
    assert mine == pytest.approx(theirs_, abs=1e-12)


def test_a_lead_is_worth_less_when_more_game_is_left():
    """The recalibration, and the thing whose absence cost a game.

    The same 200-point lead is nearly decisive with one round to play and close to nothing
    with twenty-five. A scale fixed at one round's points made both of them ~1.0, every move
    then scored the same, and the search had no gradient left — measured at 44.62% over a
    2500-point game (docs/measurements.md §5d).
    """
    nearly_over = r(81, 81, scores=(800, 600), target=1000)
    just_begun = r(81, 81, scores=(200, 0), target=2500)
    assert nearly_over > 0.9, "200 up with two rounds to play is nearly over"
    assert just_begun == pytest.approx(0.5), "and with a whole game to play it is just a round"


def test_far_from_the_line_it_is_exactly_the_old_objective():
    """The property that makes this version safe where the last two were not.

    Weighting the game outcome everywhere lost 44.62% and then 46.88% over a 2500-point game,
    because early on one round barely moves the win probability and the search was left with
    a reward that hardly varied. Beyond `GAME_UNTIL` rounds this returns the round's share
    and nothing else — bit for bit what the bot did before — so it cannot give ground there.
    """
    for points in (0, 40, 100, 162):
        share = points / 162
        assert r(points, 162 - points, scores=(0, 0), target=2500) == pytest.approx(share)
        assert r(points, 162 - points, scores=(0, 0), target=1000) == pytest.approx(share)

    # And the switch-over is where it says it is: inside GAME_UNTIL rounds of the line, the
    # projection starts to count.
    near = int(1000 - GAME_UNTIL * ROUND_POINTS) + 40
    assert r(81, 81, scores=(near, 0), target=1000) != pytest.approx(0.5, abs=1e-9)
