//! What the search is trying to maximise.
//!
//! Mirror of `krass_jass/objective.py`; the Python module carries the reasoning. In short: a
//! share of the round's card points is the right objective for a round and the wrong one for
//! a game, and the reward below saturates once the target is crossed so that MCTS — which
//! averages the reward rather than maximising it pointwise — prefers a certain sixty to a
//! gamble on ninety-or-twenty.

/// Roughly what one team takes in an ordinary round.
const ROUND_POINTS: f64 = 81.0;
/// Standard deviation of one round's point difference — see the Python module.
const ROUND_DIFF_SD: f64 = 26.0;
/// Where the projection takes over from the round, in rounds still to play. See the Python
/// module: weighting the game outcome everywhere lost twice, because early in a long game one
/// round barely moves the win probability and the search is left with no variance to work on.
const GAME_FROM: f64 = 1.0;
const GAME_UNTIL: f64 = 4.0;

/// Everything about the game outside this round that the reward depends on.
#[derive(Clone, Copy, Debug, Default)]
pub struct Stakes {
    /// Game score before this round, in team order.
    pub scores: [i32; 2],
    /// Weis already banked in this round, in team order. Stöck is deliberately absent — it
    /// is private until the second honour is played.
    pub bonus: [i32; 2],
    /// 0 means no game to project onto: fall back to the share of the round.
    pub target: i32,
    pub multiplier: i32,
}

/// Value in [0, 1] of finishing the round with `ours`/`theirs` card points.
pub fn reward(ours: i32, theirs: i32, team: usize, s: &Stakes) -> f64 {
    let total = ours + theirs;
    let share = if total == 0 { 0.5 } else { ours as f64 / total as f64 };
    if s.target <= 0 {
        return share;
    }
    let mult = s.multiplier.max(1);
    let mine = s.scores[team] + (ours + s.bonus[team]) * mult;
    let yours = s.scores[1 - team] + (theirs + s.bonus[1 - team]) * mult;

    // How much game is left, and therefore how much the projection is worth saying anything
    // about. A crossed line leaves `remaining` at 1, so the branches below get full weight
    // without special-casing themselves.
    let remaining = (s.target - mine.max(yours)).max(1) as f64;
    let rounds_left = remaining / (ROUND_POINTS * mult as f64);
    let weight = ((GAME_UNTIL - rounds_left) / (GAME_UNTIL - GAME_FROM)).clamp(0.0, 1.0);
    if weight == 0.0 {
        return share;
    }
    let blend = |p: f64| weight * p + (1.0 - weight) * share;

    match (mine >= s.target, yours >= s.target) {
        (true, false) => blend(1.0),
        (false, true) => blend(0.0),
        // Decided by the claim order, which the search cannot see. See the Python note.
        (true, true) => blend(0.5),
        (false, false) => {
            // A lead is worth what is left to happen to it, and points accumulate like a
            // random walk — so the spread of the remainder grows with the square root of the
            // rounds still to play.
            let scale = (ROUND_DIFF_SD * mult as f64 * rounds_left.max(1.0).sqrt()).max(1.0);
            blend(1.0 / (1.0 + (-((mine - yours) as f64) / scale).exp()))
        }
    }
}
