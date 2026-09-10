//! Weis and Stöck. The Rust twin of `krass_jass/weis.py`.
//!
//! Sequence order is **always** A K Q J 10 9 8 7 6 regardless of contract, which is
//! independent of the trump order used for trick-taking. Conflating the two is the classic
//! bug and the reason the two orderings live in different tables.

use crate::cards::{
    STOECK_MASK, NUM_RANKS, NUM_SUITS, RANK_9, RANK_A, RANK_J, RANK_K, RANK_Q, RANK_T,
};
use crate::config::Rules;

pub const STOECK_POINTS: i32 = 20;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WeisKind {
    Sequence,
    Four,
}

#[derive(Clone, Copy, Debug)]
pub struct Weis {
    pub kind: WeisKind,
    pub points: i32,
    pub cards: u64,
    pub length: usize,
    /// Strongest rank in the meld, in A-high order (0 = ace).
    pub top_rank: usize,
    /// Sequences only; usize::MAX for four of a kind.
    pub suit: usize,
}

impl Weis {
    /// Ordering used to decide which team scores. Higher wins.
    pub fn sort_key(&self, trump: i32, four_beats_sequence: bool) -> (i32, i32, i32, i32, i32) {
        let four_rank = if four_beats_sequence && self.kind == WeisKind::Four { 1 } else { 0 };
        (
            self.points,
            four_rank,
            self.length as i32,
            (NUM_RANKS - 1 - self.top_rank) as i32,
            if self.suit as i32 == trump { 1 } else { 0 },
        )
    }
}

fn sequence_points(length: usize, rules: &Rules) -> i32 {
    if rules.weis_large {
        match length {
            3 => 20, 4 => 50, 5 => 100, 6 => 150, 7 => 200, 8 => 250, _ => 300,
        }
    } else {
        // Small Weis caps five-and-longer at 100.
        match length {
            3 => 20, 4 => 50, _ => 100,
        }
    }
}

fn four_points(rank: usize) -> i32 {
    match rank {
        RANK_J => 200,
        RANK_9 => 150,
        RANK_A | RANK_K | RANK_Q | RANK_T => 100,
        _ => 0, // 8s, 7s and 6s are not a Weis
    }
}

fn make_sequence(suit: usize, start: usize, length: usize, rules: &Rules) -> Weis {
    let mut cards = 0u64;
    for k in start..start + length {
        cards |= 1u64 << (suit * NUM_RANKS + k);
    }
    Weis {
        kind: WeisKind::Sequence,
        points: sequence_points(length, rules),
        cards,
        length,
        top_rank: start,
        suit,
    }
}

/// Maximal runs of 3+, as `(suit, start_rank, length)`.
fn runs(hand: u64) -> Vec<(usize, usize, usize)> {
    let mut out = Vec::new();
    for suit in 0..NUM_SUITS {
        let mut start: Option<usize> = None;
        for r in 0..=NUM_RANKS {
            let held = r < NUM_RANKS && hand & (1u64 << (suit * NUM_RANKS + r)) != 0;
            if held {
                if start.is_none() {
                    start = Some(r);
                }
                continue;
            }
            if let Some(s) = start {
                if r - s >= 3 {
                    out.push((suit, s, r - s));
                }
                start = None;
            }
        }
    }
    out
}

fn fours(hand: u64, rules: &Rules) -> Vec<Weis> {
    let mut out = Vec::new();
    for rank in 0..NUM_RANKS {
        let points = four_points(rank);
        if points == 0 || (rank == RANK_9 && !rules.weis_four_nines) {
            continue;
        }
        let mut mask = 0u64;
        for suit in 0..NUM_SUITS {
            mask |= 1u64 << (suit * NUM_RANKS + rank);
        }
        if hand & mask == mask {
            out.push(Weis {
                kind: WeisKind::Four,
                points,
                cards: mask,
                length: 4,
                top_rank: rank,
                suit: usize::MAX,
            });
        }
    }
    out
}

/// Every Weis in a hand, already resolved for card-sharing.
///
/// Under **large** Weis a card may count in both a four of a kind and a sequence, so every
/// meld stands. Under **small** Weis each card counts once, so the highest-scoring set of
/// melds with disjoint cards wins — and the best answer is sometimes a *shorter* sub-sequence
/// stepping out of a four of a kind's way. One run yields at most one announced sequence,
/// or a run of nine would "split" into a 4 and a 5 for 150 instead of 100.
///
/// Ties on points are broken by which melds are strongest, not arbitrarily: a run of nine and
/// a run of five both score 100 under small Weis, but only the nine beats an opponent's six.
pub fn find_weis(hand: u64, rules: &Rules, trump: i32) -> Vec<Weis> {
    if !rules.weis_enabled {
        return Vec::new();
    }

    let mut melds: Vec<Weis> = runs(hand)
        .into_iter()
        .map(|(s, start, len)| make_sequence(s, start, len, rules))
        .collect();
    melds.extend(fours(hand, rules));

    if rules.weis_large {
        return melds;
    }

    // Candidate groups: every sub-run of each maximal run (or none), plus each four of a
    // kind (or none). A nine-card hand yields a handful, so brute force is instant.
    let mut groups: Vec<Vec<Option<Weis>>> = Vec::new();
    for (suit, start, length) in runs(hand) {
        let mut options: Vec<Option<Weis>> = vec![None];
        for sub_len in 3..=length {
            for offset in 0..=(length - sub_len) {
                options.push(Some(make_sequence(suit, start + offset, sub_len, rules)));
            }
        }
        groups.push(options);
    }
    for four in fours(hand, rules) {
        groups.push(vec![None, Some(four)]);
    }
    if groups.is_empty() {
        return Vec::new();
    }

    let mut best: Vec<Weis> = Vec::new();
    let mut best_key: Option<(i32, Vec<(i32, i32, i32, i32, i32)>)> = None;
    let mut chosen: Vec<Weis> = Vec::new();

    fn walk(
        groups: &[Vec<Option<Weis>>],
        index: usize,
        used: u64,
        points: i32,
        chosen: &mut Vec<Weis>,
        best: &mut Vec<Weis>,
        best_key: &mut Option<(i32, Vec<(i32, i32, i32, i32, i32)>)>,
        rules: &Rules,
        trump: i32,
    ) {
        if index == groups.len() {
            let mut strengths: Vec<_> = chosen
                .iter()
                .map(|m| m.sort_key(trump, rules.weis_four_beats_sequence))
                .collect();
            strengths.sort_unstable_by(|a, b| b.cmp(a));
            let key = (points, strengths);
            if best_key.as_ref().map_or(true, |b| key > *b) {
                *best_key = Some(key);
                *best = chosen.clone();
            }
            return;
        }
        for option in &groups[index] {
            match option {
                None => walk(groups, index + 1, used, points, chosen, best, best_key, rules, trump),
                Some(meld) => {
                    if used & meld.cards != 0 {
                        continue;
                    }
                    chosen.push(*meld);
                    walk(
                        groups, index + 1, used | meld.cards, points + meld.points,
                        chosen, best, best_key, rules, trump,
                    );
                    chosen.pop();
                }
            }
        }
    }

    walk(&groups, 0, 0, 0, &mut chosen, &mut best, &mut best_key, rules, trump);
    best
}

pub fn best_weis(melds: &[Weis], trump: i32, rules: &Rules) -> Option<Weis> {
    melds
        .iter()
        .copied()
        .max_by_key(|m| m.sort_key(trump, rules.weis_four_beats_sequence))
}

/// Weis points per team, and the seat holding the best Weis (-1 if none).
///
/// The team holding the single best Weis scores all of its Weis; the other scores nothing.
/// Ties go to whoever plays first, counting round from `forehand`.
pub fn score_weis(hands: &[u64; 4], trump: i32, rules: &Rules, forehand: usize) -> ([i32; 2], i32) {
    if !rules.weis_enabled {
        return ([0, 0], -1);
    }
    let per_seat: Vec<Vec<Weis>> = hands.iter().map(|&h| find_weis(h, rules, trump)).collect();

    let mut winner: i32 = -1;
    let mut winner_key: Option<(i32, i32, i32, i32, i32)> = None;
    for i in 0..4 {
        let seat = (forehand + i) % 4; // earlier to play wins ties
        if let Some(best) = best_weis(&per_seat[seat], trump, rules) {
            let key = best.sort_key(trump, rules.weis_four_beats_sequence);
            if winner_key.map_or(true, |w| key > w) {
                winner_key = Some(key);
                winner = seat as i32;
            }
        }
    }
    if winner < 0 {
        return ([0, 0], -1);
    }

    let team = (winner as usize) & 1;
    let mut points = [0i32; 2];
    for seat in (team..4).step_by(2) {
        points[team] += per_seat[seat].iter().map(|m| m.points).sum::<i32>();
    }
    (points, winner)
}

/// King + Queen of trumps in one hand. Not a Weis, cannot be beaten, and there is none in a
/// no-trump contract because there is no trump suit to hold.
pub fn score_stoeck(hands: &[u64; 4], trump: i32, rules: &Rules) -> [i32; 2] {
    let mut points = [0i32; 2];
    if !rules.stoeck_enabled || trump < 0 {
        return points;
    }
    let mask = STOECK_MASK[trump as usize];
    for (seat, &hand) in hands.iter().enumerate() {
        if hand & mask == mask {
            points[seat & 1] += STOECK_POINTS;
        }
    }
    points
}
