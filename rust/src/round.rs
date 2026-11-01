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
    /// A 3x3 block has not been named.
    BlockPending,
}

#[derive(Clone, Debug)]
pub struct Round {
    /// The contract the round is counted in; for an ordinary round also the one it is played in.
    pub contract: usize,
    pub trump: i32,
    /// Coiffeur's extra rows: the contract each trick is played in (`schedule.rs`).
    pub schedule: Option<[usize; TRICKS_PER_ROUND]>,
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
            schedule: None,
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

    /// The same round, played trick by trick to `schedule` and counted in its first contract.
    pub fn with_schedule(mut self, schedule: Option<[usize; TRICKS_PER_ROUND]>) -> Self {
        self.schedule = schedule;
        self
    }

    /// The contract the current trick is played in.
    pub fn trick_contract(&self) -> usize {
        match self.schedule {
            Some(s) => {
                let named = s[self.tricks_played.len().min(TRICKS_PER_ROUND - 1)];
                match named {
                    // Tutti: led by now only mid-trick, and then the suit led is trump.
                    crate::schedule::LED => self.trick.first().map_or(self.contract, |&c| card_suit(c)),
                    crate::schedule::UNNAMED => self.contract,
                    _ => named,
                }
            }
            None => self.contract,
        }
    }

    /// A 3x3 is between blocks and the next one has not been named: nobody may play.
    pub fn block_pending(&self) -> bool {
        match self.schedule {
            Some(s) if self.trick.is_empty() && !self.done() => {
                s[self.tricks_played.len()] == crate::schedule::UNNAMED
            }
            _ => false,
        }
    }

    pub fn block_options(&self) -> Vec<usize> {
        match self.schedule {
            Some(s) if self.block_pending() => {
                crate::schedule::block_options(&s, self.tricks_played.len())
            }
            _ => Vec::new(),
        }
    }

    /// The leader names the 3x3's next block. False if it may not be named.
    pub fn set_block(&mut self, contract: usize) -> bool {
        if !self.block_options().contains(&contract) {
            return false;
        }
        let at = self.tricks_played.len();
        if let Some(s) = self.schedule.as_mut() {
            s[at..at + 3].fill(contract);
        }
        true
    }

    pub fn trick_trump(&self) -> i32 {
        let c = self.trick_contract();
        if c < 4 { c as i32 } else { -1 }
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
        let trump = self.trick_trump();
        if trump < 0 || self.trick.is_empty() {
            return -1;
        }
        let strength = &STRENGTH[self.trick_contract()][self.led_suit() as usize];
        let mut best = -1;
        for &c in &self.trick {
            if card_suit(c) as i32 == trump {
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
            self.trick_trump(),
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
        if self.block_pending() {
            return Err(PlayError::BlockPending);
        }
        if self.legal_moves(seat) & (1u64 << card) == 0 {
            return Err(PlayError::Illegal { seat, card });
        }

        if self.trick.is_empty() {
            self.name_by_lead(card);
        }
        self.hands[seat] ^= 1u64 << card;
        self.trick.push(card);
        if self.trick.len() == NUM_SEATS {
            self.resolve_trick();
        }
        Ok(())
    }

    /// Tutti: the suit led is this trick's trump; the first trick's is the round's count.
    fn name_by_lead(&mut self, card: usize) {
        let at = self.tricks_played.len();
        let Some(s) = self.schedule.as_mut() else { return };
        if s[at] != crate::schedule::LED {
            return;
        }
        s[at] = card_suit(card);
        if at == 0 {
            self.contract = card_suit(card);
            self.trump = card_suit(card) as i32;
        }
    }

    fn resolve_trick(&mut self) {
        let values = &CARD_VALUES[self.contract];
        let strength = &STRENGTH[self.trick_contract()][card_suit(self.trick[0])];
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
