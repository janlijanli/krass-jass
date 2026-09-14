//! Game orchestration: bidding, Weis, nine tricks, scoring, repeat to the target.
//! Twin of `krass_jass/game.py`.
//!
//! Holds no agents and no transport. The caller drives it — asking whose turn it is, feeding
//! a decision in, reading the events that resulted — which keeps the same object usable from
//! a web service, a test, or a browser with no server behind it.

use crate::cards::{card_list, NUM_SEATS, RANK_J, STOECK_MASK};
use crate::config::{team_of, Rules};
use crate::deal::deal;
use crate::events::{EventLog, Payload, RoundDetail};
use crate::round::{PlayError, Round};
use crate::scoring::claim_sequence;
use crate::tables::NUM_CONTRACTS;
use crate::trump::SHOVE;
use crate::weis::{best_weis, find_weis, score_stoeck, score_weis, WeisKind, STOECK_POINTS};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Phase {
    Bidding,
    Weis,
    Playing,
    RoundOver,
    GameOver,
}

impl Phase {
    pub fn as_str(&self) -> &'static str {
        match self {
            Phase::Bidding => "bidding",
            Phase::Weis => "weis",
            Phase::Playing => "playing",
            Phase::RoundOver => "round_over",
            Phase::GameOver => "game_over",
        }
    }
}

#[derive(Debug)]
pub enum GameError {
    WrongPhase(&'static str),
    NotYourTurn(usize),
    UnknownBid,
    AlreadyShoved,
    NoWeisToAnnounce(usize),
    Play(PlayError),
}

/// Ecken 10 — the card that decides who opens the first round of a game.
/// Suit-major indexing: diamonds is suit 0, the ten is rank 4.
const ECKEN_TEN: usize = 4;

#[derive(Clone, Debug)]
pub struct WeisEntry {
    pub seat: usize,
    pub points: i32,
    /// Only the single best Weis at the table shows cards. A partner's holding stays private.
    pub cards: Option<Vec<usize>>,
    pub winner: bool,
    pub best: bool,
}

pub struct Game {
    pub rules: Rules,
    pub seed: u64,
    pub scores: [i32; 2],
    pub round_index: u32,
    pub dealer: usize,
    pub phase: Phase,
    pub log: EventLog,
    pub round: Option<Round>,
    pub contract: Option<usize>,
    pub declarer: usize,
    pub forehand: usize,
    pub shoved: bool,

    dealt: [u64; NUM_SEATS],
    weis_points: [i32; 2],
    stoeck_points: [i32; 2],
    stoeck_holders: [bool; NUM_SEATS],
    pub weis_summary: Vec<WeisEntry>,
    pub stoeck_announced: Vec<(usize, i32, usize)>,
    pub weis_offers: [i32; NUM_SEATS],
    weis_choices: [Option<bool>; NUM_SEATS],
    weis_resolved: bool,
    pub last_score: Option<RoundDetail>,
    pub first_across: i32,
}

impl Game {
    pub fn new(rules: Rules, seed: u64) -> Self {
        let mut game = Game {
            rules,
            seed,
            scores: [0, 0],
            round_index: 0,
            dealer: 0,
            phase: Phase::Bidding,
            log: EventLog::default(),
            round: None,
            contract: None,
            declarer: 0,
            forehand: 0,
            shoved: false,
            dealt: [0; NUM_SEATS],
            weis_points: [0, 0],
            stoeck_points: [0, 0],
            stoeck_holders: [false; NUM_SEATS],
            weis_summary: Vec::new(),
            stoeck_announced: Vec::new(),
            weis_offers: [0; NUM_SEATS],
            weis_choices: [None; NUM_SEATS],
            weis_resolved: false,
            last_score: None,
            first_across: -1,
        };
        game.log.emit(
            Payload::GameStarted { target_score: rules.target_score },
            None,
        );
        game.start_round();
        game
    }

    pub fn start_round(&mut self) {
        let hands = deal(self.seed, self.round_index);
        self.dealt = hands;
        // Who opens the very first round is decided by the cards, not by the seat numbering:
        // whoever was dealt the Ecken 10 starts, which is how a table settles it when nobody
        // has dealt yet. `dealer` is set backwards from that seat so the usual rotation
        // carries on untouched. Mirrors `krass_jass/game.py`.
        if self.round_index == 0 {
            for seat in 0..NUM_SEATS {
                if self.dealt[seat] & (1u64 << ECKEN_TEN) != 0 {
                    self.dealer = (seat + NUM_SEATS - 1) % NUM_SEATS;
                    break;
                }
            }
        }
        self.forehand = (self.dealer + 1) % NUM_SEATS;
        self.declarer = self.forehand;
        self.shoved = false;
        self.contract = None;
        self.round = None;
        self.phase = Phase::Bidding;
        self.weis_summary.clear();
        self.stoeck_announced.clear();
        self.weis_offers = [0; NUM_SEATS];
        self.weis_choices = [None; NUM_SEATS];
        self.weis_resolved = false;
        self.weis_points = [0, 0];
        self.stoeck_holders = [false; NUM_SEATS];

        self.log.emit(
            Payload::RoundStarted {
                round: self.round_index,
                dealer: self.dealer,
                forehand: self.forehand,
            },
            None,
        );
        for seat in 0..NUM_SEATS {
            self.log.emit(
                Payload::HandDealt { seat, cards: card_list(hands[seat]) },
                Some(seat),
            );
        }
    }

    /// Weis awarded this round, per team.
    ///
    /// Public from the moment the table has finished calling — which is the only moment it
    /// is non-zero, so handing it to the search leaks nothing. Stöck has no equivalent: it
    /// is held privately until the second honour goes down, and stays out of the projection.
    pub fn weis_points_public(&self, team: usize) -> i32 {
        self.weis_points[team]
    }

    pub fn to_act(&self) -> Option<usize> {
        match self.phase {
            // The question belongs to whoever is about to play: it is asked on their turn
            // in the first trick, not to the whole table before a card is down.
            Phase::Weis => self.round.as_ref().map(|r| r.to_play()),
            Phase::Bidding => Some(self.declarer),
            Phase::Playing => self.round.as_ref().map(|r| r.to_play()),
            _ => None,
        }
    }

    pub fn hand_of(&self, seat: usize) -> u64 {
        self.round.as_ref().map_or(self.dealt[seat], |r| r.hands[seat])
    }

    // -- actions ------------------------------------------------------------

    /// `contract` is an index, or `SHOVE`.
    pub fn bid(&mut self, seat: usize, action: usize) -> Result<(), GameError> {
        if self.phase != Phase::Bidding {
            return Err(GameError::WrongPhase("not bidding"));
        }
        if seat != self.declarer {
            return Err(GameError::NotYourTurn(seat));
        }
        if action == SHOVE {
            if self.shoved {
                return Err(GameError::AlreadyShoved);
            }
            if seat != self.forehand && !self.rules.allow_zurueckschieben {
                return Err(GameError::WrongPhase("only forehand may shove"));
            }
            self.shoved = true;
            self.declarer = (seat + 2) % NUM_SEATS;
            self.log.emit(Payload::Bid { seat, action: "SHOVE".into() }, None);
            return Ok(());
        }
        if action >= NUM_CONTRACTS {
            return Err(GameError::UnknownBid);
        }

        self.contract = Some(action);
        self.log.emit(
            Payload::Bid { seat, action: crate::tables::contract_name(action).into() },
            None,
        );
        self.begin_play();
        Ok(())
    }

    fn begin_play(&mut self) {
        let contract = self.contract.expect("contract set");
        self.round = Some(Round::new(contract, self.dealt, self.forehand, self.rules));
        self.log.emit(
            Payload::ContractSet {
                contract,
                declarer: self.declarer,
                multiplier: self.rules.multiplier(contract),
                leader: self.forehand,
            },
            None,
        );

        let trump = if contract < 4 { contract as i32 } else { -1 };

        // Stöck is settled now whatever happens to the Weis: a King/Queen of trumps can go
        // down on the first trick, before the last player has answered.
        self.note_stoeck();

        if self.rules.weis_enabled && self.rules.weis_manual {
            let mut any = false;
            for seat in 0..NUM_SEATS {
                let total: i32 =
                    find_weis(self.dealt[seat], &self.rules, trump).iter().map(|m| m.points).sum();
                self.weis_offers[seat] = total;
                any |= total > 0;
            }
            if any {
                // Nobody is asked yet. Each seat answers when its turn comes round in the
                // first trick, which is when a player calls a Weis at the table.
                self.phase = Phase::Playing;
                self.ask_weis_if_due();
                return;
            }
        }

        self.phase = Phase::Playing;
        for seat in 0..NUM_SEATS {
            self.announce_weis(seat);
        }
        self.resolve_weis();
    }

    /// Put the question to the seat about to play, if it still owes an answer. Only in the
    /// first trick: that is the whole window in which a Weis may be called.
    fn ask_weis_if_due(&mut self) {
        let seat = match self.round.as_ref() {
            Some(r) if r.tricks_played.is_empty() => r.to_play(),
            _ => return,
        };
        if self.weis_offers[seat] > 0 && self.weis_choices[seat].is_none() {
            self.phase = Phase::Weis;
        }
    }

    pub fn choose_weis(&mut self, seat: usize, announce: bool) -> Result<(), GameError> {
        if self.phase != Phase::Weis {
            return Err(GameError::WrongPhase("not choosing Weis"));
        }
        if self.to_act() != Some(seat) {
            return Err(GameError::NotYourTurn(seat));
        }
        if self.weis_offers[seat] == 0 {
            return Err(GameError::NoWeisToAnnounce(seat));
        }
        self.weis_choices[seat] = Some(announce);
        self.announce_weis(seat);
        // The seat that just answered now plays its card; the comparison waits until the
        // whole table has called, at the end of the first trick.
        self.phase = Phase::Playing;
        Ok(())
    }

    /// The seat's melds — nothing at all if it declined.
    ///
    /// A declined Weis is not merely hidden: it leaves the contest, so it cannot win the
    /// comparison for its team either.
    fn weis_of(&self, seat: usize) -> Vec<crate::weis::Weis> {
        if !self.rules.weis_enabled || self.weis_choices[seat] == Some(false) {
            return Vec::new();
        }
        let trump = match self.contract {
            Some(c) if c < 4 => c as i32,
            _ => -1,
        };
        find_weis(self.dealt[seat], &self.rules, trump)
    }

    /// Stage one: the seat calls a *value*. Public, and carries no cards.
    ///
    /// At the table everyone calls the value of their best Weis as their turn comes round in
    /// the first trick; only the team holding the best one then shows the actual cards. That
    /// staging is what keeps a losing team's holding secret.
    fn announce_weis(&mut self, seat: usize) {
        let melds = self.weis_of(seat);
        let total: i32 = melds.iter().map(|m| m.points).sum();
        if total == 0 {
            return;
        }
        self.log
            .emit(Payload::WeisAnnounced { seat, points: total, melds: melds.len() }, None);
        self.weis_summary.push(WeisEntry {
            seat,
            points: total,
            cards: None,
            winner: false,
            best: false,
        });
    }

    /// Stage two: everyone has called, so the single best one shows what it holds.
    fn resolve_weis(&mut self) {
        if self.weis_resolved {
            return;
        }
        self.weis_resolved = true;

        let contract = self.contract.expect("contract set");
        let trump = if contract < 4 { contract as i32 } else { -1 };
        if !self.rules.weis_enabled {
            self.weis_points = [0, 0];
            return;
        }

        let mut hands = self.dealt;
        for seat in 0..NUM_SEATS {
            if self.weis_choices[seat] == Some(false) {
                hands[seat] = 0;
            }
        }
        let (points, winner) = score_weis(&hands, trump, &self.rules, self.forehand);
        let per_seat: Vec<Vec<_>> =
            hands.iter().map(|&h| find_weis(h, &self.rules, trump)).collect();

        if winner >= 0 {
            let winner = winner as usize;
            let best = best_weis(&per_seat[winner], trump, &self.rules);
            for seat in 0..NUM_SEATS {
                if team_of(seat) != team_of(winner) {
                    continue;
                }
                for meld in &per_seat[seat] {
                    self.log.emit(
                        Payload::WeisDeclared {
                            seat,
                            kind: match meld.kind {
                                WeisKind::Sequence => "sequence".into(),
                                WeisKind::Four => "four".into(),
                            },
                            points: meld.points,
                            cards: card_list(meld.cards),
                        },
                        None,
                    );
                }
            }
            self.log.emit(
                Payload::WeisResolved { seat: winner, team: team_of(winner), points },
                None,
            );
            for entry in self.weis_summary.iter_mut() {
                if team_of(entry.seat) == team_of(winner) {
                    entry.winner = true;
                }
                if entry.seat == winner {
                    if let Some(m) = best {
                        entry.best = true;
                        entry.cards = Some(card_list(m.cards));
                    }
                }
            }
        }
        self.weis_points = points;
    }

    /// Have the calls been made? Before they have, a seat that has said nothing has not
    /// said "nothing" — it has not spoken yet, and reading silence as a claim would be a
    /// constraint the table never heard.
    pub fn weis_calls_are_in(&self) -> bool {
        self.weis_resolved
    }

    /// Stöck is *held* now but announced later, when the second of King/Queen is played.
    fn note_stoeck(&mut self) {
        let contract = self.contract.expect("contract set");
        let trump = if contract < 4 { contract as i32 } else { -1 };
        self.stoeck_points = score_stoeck(&self.dealt, trump, &self.rules);
        if trump >= 0 {
            let mask = STOECK_MASK[trump as usize];
            for seat in 0..NUM_SEATS {
                self.stoeck_holders[seat] = self.dealt[seat] & mask == mask;
            }
        }
        let _ = RANK_J;
    }

    pub fn play(&mut self, seat: usize, card: usize) -> Result<(), GameError> {
        if self.phase != Phase::Playing {
            return Err(GameError::WrongPhase("not playing"));
        }
        {
            let round = self.round.as_ref().ok_or(GameError::WrongPhase("no round"))?;
            if seat != round.to_play() {
                return Err(GameError::NotYourTurn(seat));
            }
        }
        let tricks_before = self.round.as_ref().unwrap().tricks_played.len();
        self.round
            .as_mut()
            .unwrap()
            .play(card)
            .map_err(GameError::Play)?;
        self.log.emit(Payload::CardPlayed { seat, card }, None);
        self.check_stoeck(seat, tricks_before);

        let round = self.round.as_ref().unwrap();
        if round.tricks_played.len() > tricks_before {
            let (_, cards) = round.tricks_played.last().unwrap().clone();
            let winner = round.last_trick_winner as usize;
            let index = round.tricks_played.len();
            self.log.emit(Payload::TrickWon { seat: winner, trick: index, cards }, None);
        }
        if self.round.as_ref().unwrap().tricks_played.is_empty() {
            self.ask_weis_if_due();
        } else {
            // Everyone has had a turn, so everyone has called: the comparison can happen and
            // the best holding shows its cards.
            self.resolve_weis();
        }

        if self.round.as_ref().unwrap().done() {
            self.score_round();
        }
        Ok(())
    }

    /// Announce Stöck at the moment the second of King/Queen of trumps goes down — the
    /// timing is information a player would rather choose to reveal themselves.
    fn check_stoeck(&mut self, seat: usize, trick_index: usize) {
        if !self.stoeck_holders[seat] {
            return;
        }
        let contract = match self.contract {
            Some(c) if c < 4 => c,
            _ => return,
        };
        let mask = STOECK_MASK[contract];
        if self.round.as_ref().map_or(false, |r| r.hands[seat] & mask == 0) {
            self.stoeck_holders[seat] = false;
            self.log.emit(
                Payload::Stoeck { seat, points: STOECK_POINTS, trick: trick_index },
                None,
            );
            self.stoeck_announced.push((seat, STOECK_POINTS, trick_index));
        }
    }

    fn score_round(&mut self) {
        let round = self.round.as_ref().expect("round");
        let score = round.score(self.weis_points, self.stoeck_points);
        let totals = score.total();
        let sequence = claim_sequence(&score, &round.trick_results, &self.rules);

        // Apply claim by claim, so a simultaneous finish is decided by who reaches the
        // target first rather than by who ends up with more.
        let mut claimed = [0i32; 2];
        for &(team, points) in &sequence {
            claimed[team] += points;
        }
        debug_assert_eq!(claimed, totals, "claim sequence must reproduce the round total");

        self.first_across = -1;
        for &(team, points) in &sequence {
            self.scores[team] += points;
            if self.rules.target_score > 0
                && self.first_across < 0
                && self.scores[team] >= self.rules.target_score
            {
                self.first_across = team as i32;
            }
        }

        let detail = RoundDetail {
            trick_points: score.trick_points,
            last_trick: score.last_trick,
            match_bonus: score.match_bonus,
            weis: score.weis,
            stoeck: score.stoeck,
            multiplier: score.multiplier,
            round_total: totals,
            scores: self.scores,
        };
        self.last_score = Some(detail);
        self.log.emit(Payload::RoundScored { round: self.round_index, detail }, None);

        if self.rules.target_score > 0 && self.scores.iter().any(|&s| s >= self.rules.target_score)
        {
            self.phase = Phase::GameOver;
            self.log.emit(
                Payload::GameOver {
                    winner: self.first_across,
                    scores: self.scores,
                    decided_by: if self.first_across >= 0 { "claim_order" } else { "score" },
                    claim_order: self.rules.claim_order,
                },
                None,
            );
        } else {
            self.phase = Phase::RoundOver;
        }
    }

    pub fn next_round(&mut self) -> Result<(), GameError> {
        if self.phase != Phase::RoundOver {
            return Err(GameError::WrongPhase("round is not over"));
        }
        self.round_index += 1;
        self.dealer = (self.dealer + 1) % NUM_SEATS;
        self.start_round();
        Ok(())
    }
}
