//! Authoritative round state. Twin of `krass_jass/state.py`.
//!
//! Bookkeeping over the pieces that already existed — legal moves, trick resolution, card
//! values, scoring. Having it here rather than only in Python is what makes the crate a
//! complete engine, which is the prerequisite for running the game without a server.
//!
//! Like the Python original, it validates: `play` refuses anything not in `legal_moves`,
//! whoever is calling.

use crate::cards::{card_suit, NUM_SEATS};
use crate::config::{team_of, Rules};
use crate::legal::legal_moves;
use crate::scoring::{score_round, RoundScore, TRICKS_PER_ROUND};
use crate::tables::{CARD_VALUES, STRENGTH};

#[derive(Debug)]
pub enum PlayError {
    OutOfRange(usize),
    Illegal { seat: usize, card: usize },
    RoundOver,
}

#[derive(Clone, Debug)]
pub struct Round {
    pub contract: usize,
    pub trump: i32,
    pub hands: [u64; NUM_SEATS],
    pub leader: usize,
    pub trick: Vec<usize>,
    pub tricks_played: Vec<(usize, Vec<usize>)>,
    /// `(winning seat, card points)` per trick, in the order taken — the Stöck-Weis-Stich
    /// ruling needs tricks one at a time.
    pub trick_results: Vec<(usize, i32)>,
    pub trick_points: [i32; 2],
    pub tricks_won: [usize; 2],
    pub last_trick_winner: i32,
    rules: Rules,
}

impl Round {
    pub fn new(contract: usize, hands: [u64; NUM_SEATS], leader: usize, rules: Rules) -> Self {
        Round {
            contract,
            trump: if contract < 4 { contract as i32 } else { -1 },
            hands,
            leader,
            trick: Vec::with_capacity(NUM_SEATS),
            tricks_played: Vec::with_capacity(TRICKS_PER_ROUND),
            trick_results: Vec::with_capacity(TRICKS_PER_ROUND),
            trick_points: [0; 2],
            tricks_won: [0; 2],
            last_trick_winner: -1,
            rules,
        }
    }

    pub fn to_play(&self) -> usize {
        (self.leader + self.trick.len()) % NUM_SEATS
    }

    pub fn led_suit(&self) -> i32 {
        self.trick.first().map_or(-1, |&c| card_suit(c) as i32)
    }

    pub fn done(&self) -> bool {
        self.tricks_played.len() == TRICKS_PER_ROUND
    }

    /// Strength of the highest trump in the current trick, or -1. Only consulted where the
    /// undertrump rule applies.
    pub fn best_trump_strength(&self) -> i32 {
        if self.trump < 0 || self.trick.is_empty() {
            return -1;
        }
        let strength = &STRENGTH[self.contract][self.led_suit() as usize];
        let mut best = -1;
        for &c in &self.trick {
            if card_suit(c) as i32 == self.trump {
                let ts = strength[c] - 100;
                if ts > best {
                    best = ts;
                }
            }
        }
        best
    }

    pub fn legal_moves(&self, seat: usize) -> u64 {
        legal_moves(
            self.hands[seat],
            self.trump,
            self.led_suit(),
            self.best_trump_strength(),
            self.rules.strict_undertrump,
            self.rules.puur_exempt,
        )
    }

    /// Play one card for the seat on turn. Never trusts the caller.
    pub fn play(&mut self, card: usize) -> Result<(), PlayError> {
        if self.done() {
            return Err(PlayError::RoundOver);
        }
        if card >= 36 {
            return Err(PlayError::OutOfRange(card));
        }
        let seat = self.to_play();
        if self.legal_moves(seat) & (1u64 << card) == 0 {
            return Err(PlayError::Illegal { seat, card });
        }

        self.hands[seat] ^= 1u64 << card;
        self.trick.push(card);
        if self.trick.len() == NUM_SEATS {
            self.resolve_trick();
        }
        Ok(())
    }

    fn resolve_trick(&mut self) {
        let values = &CARD_VALUES[self.contract];
        let strength = &STRENGTH[self.contract][card_suit(self.trick[0])];
        // Strengths are banded (trump 100+, led suit 10+, else 0) so one max decides it.
        let mut best = 0usize;
        for i in 1..self.trick.len() {
            if strength[self.trick[i]] > strength[self.trick[best]] {
                best = i;
            }
        }
        let winner = (self.leader + best) % NUM_SEATS;
        let team = team_of(winner);
        let points: i32 = self.trick.iter().map(|&c| values[c]).sum();

        self.trick_points[team] += points;
        self.tricks_won[team] += 1;
        self.trick_results.push((winner, points));
        self.tricks_played.push((self.leader, std::mem::take(&mut self.trick)));
        self.last_trick_winner = winner as i32;
        self.leader = winner;
    }

    pub fn score(&self, weis: [i32; 2], stoeck: [i32; 2]) -> RoundScore {
        score_round(
            self.trick_points,
            self.tricks_won,
            self.last_trick_winner.max(0) as usize,
            self.contract,
            &self.rules,
            weis,
            stoeck,
        )
    }
}
