//! Round scoring and the Stöck-Weis-Stich claim ordering. Twin of `krass_jass/scoring.py`
//! and the claim sequence in `krass_jass/game.py`.

use crate::config::{team_of, Rules, CLAIM_STICH, CLAIM_STOECK, CLAIM_WEIS};

pub const TRICKS_PER_ROUND: usize = 9;

#[derive(Clone, Copy, Debug, Default)]
pub struct RoundScore {
    pub trick_points: [i32; 2],
    pub last_trick: [i32; 2],
    pub match_bonus: [i32; 2],
    pub weis: [i32; 2],
    pub stoeck: [i32; 2],
    pub multiplier: i32,
}

impl RoundScore {
    pub fn total(&self) -> [i32; 2] {
        let mut out = [0i32; 2];
        for t in 0..2 {
            out[t] = (self.trick_points[t]
                + self.last_trick[t]
                + self.match_bonus[t]
                + self.weis[t]
                + self.stoeck[t])
                * self.multiplier;
        }
        out
    }
}

pub fn score_round(
    trick_points: [i32; 2],
    tricks_won: [usize; 2],
    last_trick_winner: usize,
    contract: usize,
    rules: &Rules,
    weis: [i32; 2],
    stoeck: [i32; 2],
) -> RoundScore {
    let mut last = [0i32; 2];
    last[team_of(last_trick_winner)] = rules.last_trick_bonus;

    let mut match_bonus = [0i32; 2];
    if rules.match_bonus != 0 {
        for t in 0..2 {
            if tricks_won[t] == TRICKS_PER_ROUND {
                match_bonus[t] = rules.match_bonus;
            }
        }
    }

    RoundScore {
        trick_points,
        last_trick: last,
        match_bonus,
        weis: if rules.weis_enabled { weis } else { [0, 0] },
        stoeck: if rules.stoeck_enabled { stoeck } else { [0, 0] },
        multiplier: rules.multiplier(contract),
    }
}

/// Points in the order they are claimed: **Stöck, Weis, Stich**.
///
/// Only matters when both teams would cross the target in the same round — then whoever gets
/// there first in this order wins, whatever the final totals say. Counting the round in one
/// go produces the right totals and can name the wrong winner.
///
/// `trick_results` is `(winning seat, card points)` per trick, in the order taken.
pub fn claim_sequence(
    score: &RoundScore,
    trick_results: &[(usize, i32)],
    rules: &Rules,
) -> Vec<(usize, i32)> {
    let m = score.multiplier;
    let mut stoeck = Vec::new();
    let mut weis = Vec::new();
    let mut stich = Vec::new();

    for team in 0..2 {
        if score.stoeck[team] != 0 {
            stoeck.push((team, score.stoeck[team] * m));
        }
        if score.weis[team] != 0 {
            weis.push((team, score.weis[team] * m));
        }
    }

    let last = trick_results.len().saturating_sub(1);
    for (index, &(winner, points)) in trick_results.iter().enumerate() {
        let mut p = points;
        if index == last {
            p += rules.last_trick_bonus;
        }
        if p != 0 {
            stich.push((team_of(winner), p * m));
        }
    }
    for team in 0..2 {
        if score.match_bonus[team] != 0 {
            stich.push((team, score.match_bonus[team] * m));
        }
    }

    let mut out = Vec::new();
    for key in rules.claim_order {
        match key {
            CLAIM_STOECK => out.extend(stoeck.iter().copied()),
            CLAIM_WEIS => out.extend(weis.iter().copied()),
            CLAIM_STICH => out.extend(stich.iter().copied()),
            _ => {}
        }
    }
    out
}
