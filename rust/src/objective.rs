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
    /// Risk aversion, offsetting determinized search's optimism. 0 is off. See the Python
    /// module: the *kink* is what does the work, an affine penalty would do nothing.
    pub risk_lambda: f64,
    /// Sidi Barrani: the bid the declarers must reach, 0 in the Schieber. With a bid the reward
    /// is the hand's whole swing — the cards and the stake — instead of a share of the cards.
    pub sidi_bid: i32,
    /// Sidi: the declaring team.
    pub sidi_declarers: usize,
    /// Sidi: the bid was doubled, so the stake is twice the bid.
    pub sidi_doubled: bool,
}

/// The card points in a Sidi hand, and what Match makes of them.
const HAND_POINTS: f64 = 157.0;
const MATCH_BONUS: f64 = 100.0;

/// Sidi Barrani: value in [0, 1] of a hand that ends `ours`/`theirs` in card points.
///
/// Both teams write their cards, and the bid goes to the declarers if their points reach it,
/// otherwise to the defenders. So what the hand is worth to `team` is the difference of what the
/// two teams write, scaled into [0, 1] by the largest difference this bid allows. The threshold
/// is the point: a declarer two points short of the bid loses the stake, and the search should
/// see that cliff — a share of the cards cannot.
///
/// The search does not track tricks through a playout, so Match is read off the points: all 157
/// to one side and nothing to the other. A zero-point trick taken by the other side is the one
/// case that reads wrong, and it only matters to a bid of 257.
fn sidi_reward(ours: f64, theirs: f64, team: usize, s: &Stakes) -> f64 {
    let (mut ours, mut theirs) = (ours, theirs);
    if theirs <= 0.0 && ours >= HAND_POINTS {
        ours += MATCH_BONUS;
    } else if ours <= 0.0 && theirs >= HAND_POINTS {
        theirs += MATCH_BONUS;
    }
    let stake = s.sidi_bid as f64 * if s.sidi_doubled { 2.0 } else { 1.0 };
    let declaring = team == s.sidi_declarers;
    let declarer_points = if declaring { ours } else { theirs };
    let made = declarer_points >= s.sidi_bid as f64;
    let swing = ours - theirs + if made == declaring { stake } else { -stake };
    let most = HAND_POINTS + MATCH_BONUS + stake;
    (0.5 + swing / (2.0 * most)).clamp(0.0, 1.0)
}

const RISK_THRESHOLD: f64 = 0.4;

/// Dislike bad rounds more than linearly. Slope `1 + lam` below the threshold, `1` above.
fn risk_adjust(share: f64, lam: f64) -> f64 {
    if lam <= 0.0 {
        return share;
    }
    let f = share - lam * (RISK_THRESHOLD - share).max(0.0);
    let lo = -lam * RISK_THRESHOLD;
    (f - lo) / (1.0 - lo)
}

/// Value in [0, 1] of finishing the round with `ours`/`theirs` card points.
pub fn reward(ours: i32, theirs: i32, team: usize, s: &Stakes) -> f64 {
    reward_f(ours as f64, theirs as f64, team, s)
}

/// `reward` for expected points, which a value network produces. Identical for whole numbers.
pub fn reward_f(ours: f64, theirs: f64, team: usize, s: &Stakes) -> f64 {
    if s.sidi_bid > 0 {
        return sidi_reward(ours, theirs, team, s);
    }
    let total = ours + theirs;
    let share = risk_adjust(if total <= 0.0 { 0.5 } else { ours / total }, s.risk_lambda);
    if s.target <= 0 {
        return share;
    }
    let mult = s.multiplier.max(1) as f64;
    let mine = s.scores[team] as f64 + (ours + s.bonus[team] as f64) * mult;
    let yours = s.scores[1 - team] as f64 + (theirs + s.bonus[1 - team] as f64) * mult;
    let target = s.target as f64;

    // How much game is left, and therefore how much the projection is worth saying anything
    // about. A crossed line leaves `remaining` at 1, so the branches below get full weight
    // without special-casing themselves.
    let remaining = (target - mine.max(yours)).max(1.0);
    let rounds_left = remaining / (ROUND_POINTS * mult);
    let weight = ((GAME_UNTIL - rounds_left) / (GAME_UNTIL - GAME_FROM)).clamp(0.0, 1.0);
    if weight == 0.0 {
        return share;
    }
    let blend = |p: f64| weight * p + (1.0 - weight) * share;

    match (mine >= target, yours >= target) {
        (true, false) => blend(1.0),
        (false, true) => blend(0.0),
        // Decided by the claim order, which the search cannot see. See the Python note.
        (true, true) => blend(0.5),
        (false, false) => {
            // A lead is worth what is left to happen to it, and points accumulate like a
            // random walk — so the spread of the remainder grows with the square root of the
            // rounds still to play.
            let scale = (ROUND_DIFF_SD * mult * rounds_left.max(1.0).sqrt()).max(1.0);
            blend(1.0 / (1.0 + (-(mine - yours) / scale).exp()))
        }
    }
}

#[cfg(test)]
mod sidi_tests {
    use super::*;

    fn stakes(bid: i32, declarers: usize, doubled: bool) -> Stakes {
        Stakes { sidi_bid: bid, sidi_declarers: declarers, sidi_doubled: doubled, ..Default::default() }
    }

    #[test]
    fn the_bid_is_a_cliff() {
        let s = stakes(100, 0, false);
        let short = reward(99, 58, 0, &s);
        let made = reward(100, 57, 0, &s);
        // One point of cards, a whole stake of swing.
        assert!(made - short > 0.25, "{short} -> {made}");
        // And the defenders see the same hand the other way round.
        assert!((reward(58, 99, 1, &s) - (1.0 - short)).abs() < 1e-9);
    }

    #[test]
    fn a_double_doubles_the_stake() {
        let plain = reward(120, 37, 0, &stakes(120, 0, false));
        let doubled = reward(120, 37, 0, &stakes(120, 0, true));
        assert!(doubled > plain);
    }

    #[test]
    fn match_is_read_off_the_points() {
        let s = stakes(257, 0, false);
        assert!(reward(157, 0, 0, &s) > 0.99);
        assert!(reward(152, 5, 0, &s) < 0.5, "all but the last trick is not a match");
    }
}
