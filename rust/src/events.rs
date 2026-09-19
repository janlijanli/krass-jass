//! The game event log. Twin of `krass_jass/events.py`.
//!
//! Ordered, append-only, one stream per game; every client view is a fold over its own
//! filtered slice. Reconnection, replay and the debug viewer all fall out of that.
//!
//! Payloads are a typed enum with a hand-written JSON writer rather than serde. The shapes
//! are few and fixed, and pulling serde_json in would cost more wasm than the whole engine
//! currently weighs.
//!
//! **Filtering is per event and explicit.** Exactly one variant carries hidden cards
//! (`HandDealt`) and it is addressed to a single seat. Anything new carrying card
//! identifiers must set `private_to`.

use crate::cards::format_card;

#[derive(Clone, Debug)]
pub enum Payload {
    GameStarted { target_score: i32 },
    RoundStarted { round: u32, dealer: usize, forehand: usize },
    HandDealt { seat: usize, cards: Vec<usize> },
    Bid { seat: usize, action: String },
    /// Sidi: all four passed, the next seat deals.
    ThrownIn { round: u32, dealer: usize },
    /// Sidi: an opponent's answer after the lead.
    DoubleAnswered { seat: usize, double: bool },
    /// `sidi` carries the bid and the double; `None` in the Schieber, which keeps its shape.
    ContractSet {
        contract: usize,
        declarer: usize,
        multiplier: i32,
        leader: usize,
        sidi: Option<(i32, bool)>,
    },
    WeisAnnounced { seat: usize, points: i32, melds: usize },
    WeisDeclared { seat: usize, kind: String, points: i32, cards: Vec<usize> },
    WeisResolved { seat: usize, team: usize, points: [i32; 2] },
    Stoeck { seat: usize, points: i32, trick: usize },
    CardPlayed { seat: usize, card: usize },
    TrickWon { seat: usize, trick: usize, cards: Vec<usize> },
    RoundScored { round: u32, detail: RoundDetail },
    SidiRoundScored { round: u32, detail: SidiDetail },
    SidiGameOver { winner: i32, scores: [i32; 2] },
    GameOver {
        winner: i32,
        scores: [i32; 2],
        /// Named so a close finish is explicable rather than surprising.
        decided_by: &'static str,
        claim_order: [u8; 3],
    },
}

#[derive(Clone, Copy, Debug)]
pub struct RoundDetail {
    pub trick_points: [i32; 2],
    pub last_trick: [i32; 2],
    pub match_bonus: [i32; 2],
    pub weis: [i32; 2],
    pub stoeck: [i32; 2],
    pub multiplier: i32,
    pub round_total: [i32; 2],
    pub scores: [i32; 2],
}

#[derive(Clone, Copy, Debug)]
pub struct SidiDetail {
    pub trick_points: [i32; 2],
    pub last_trick: [i32; 2],
    pub match_bonus: [i32; 2],
    pub bid: i32,
    pub doubled: bool,
    pub made: bool,
    pub bonus: [i32; 2],
    pub round_total: [i32; 2],
    pub scores: [i32; 2],
}

#[derive(Clone, Debug)]
pub struct Event {
    pub seq: usize,
    pub payload: Payload,
    /// Seat this event is addressed to, or None for public. Public is the default because
    /// forgetting to mark something private should be loud, not silent.
    pub private_to: Option<usize>,
}

fn cards_json(cards: &[usize]) -> String {
    let parts: Vec<String> = cards.iter().map(|&c| format!("\"{}\"", format_card(c))).collect();
    format!("[{}]", parts.join(","))
}

fn claim_name(key: u8) -> &'static str {
    match key {
        crate::config::CLAIM_STOECK => "stoeck",
        crate::config::CLAIM_WEIS => "weis",
        _ => "stich",
    }
}

fn pair(name: &str, v: [i32; 2]) -> String {
    format!("\"{name}\":[{},{}]", v[0], v[1])
}

impl Event {
    pub fn type_name(&self) -> &'static str {
        match self.payload {
            Payload::GameStarted { .. } => "game_started",
            Payload::RoundStarted { .. } => "round_started",
            Payload::HandDealt { .. } => "hand_dealt",
            Payload::Bid { .. } => "bid",
            Payload::ThrownIn { .. } => "thrown_in",
            Payload::DoubleAnswered { .. } => "double_answered",
            Payload::ContractSet { .. } => "contract_set",
            Payload::WeisAnnounced { .. } => "weis_announced",
            Payload::WeisDeclared { .. } => "weis_declared",
            Payload::WeisResolved { .. } => "weis_resolved",
            Payload::Stoeck { .. } => "stoeck",
            Payload::CardPlayed { .. } => "card_played",
            Payload::TrickWon { .. } => "trick_won",
            Payload::RoundScored { .. } | Payload::SidiRoundScored { .. } => "round_scored",
            Payload::GameOver { .. } | Payload::SidiGameOver { .. } => "game_over",
        }
    }

    pub fn visible_to(&self, seat: usize) -> bool {
        self.private_to.map_or(true, |s| s == seat)
    }

    pub fn to_json(&self) -> String {
        let head = format!("{{\"seq\":{},\"type\":\"{}\"", self.seq, self.type_name());
        let body = match &self.payload {
            Payload::GameStarted { target_score } => format!("\"target_score\":{target_score}"),
            Payload::RoundStarted { round, dealer, forehand } => {
                format!("\"round\":{round},\"dealer\":{dealer},\"forehand\":{forehand}")
            }
            Payload::HandDealt { seat, cards } => {
                format!("\"seat\":{seat},\"cards\":{}", cards_json(cards))
            }
            Payload::Bid { seat, action } => format!("\"seat\":{seat},\"action\":\"{action}\""),
            Payload::ThrownIn { round, dealer } => format!("\"round\":{round},\"dealer\":{dealer}"),
            Payload::DoubleAnswered { seat, double } => {
                format!("\"seat\":{seat},\"double\":{double}")
            }
            Payload::ContractSet { contract, declarer, multiplier, leader, sidi } => {
                let mut out = format!(
                    "\"contract\":\"{}\",\"declarer\":{declarer},\"multiplier\":{multiplier},\"leader\":{leader}",
                    crate::tables::contract_name(*contract)
                );
                if let Some((bid, doubled)) = sidi {
                    out.push_str(&format!(",\"bid\":{bid},\"doubled\":{doubled}"));
                }
                out
            }
            Payload::WeisAnnounced { seat, points, melds } => {
                format!("\"seat\":{seat},\"points\":{points},\"melds\":{melds}")
            }
            Payload::WeisDeclared { seat, kind, points, cards } => format!(
                "\"seat\":{seat},\"kind\":\"{kind}\",\"points\":{points},\"cards\":{}",
                cards_json(cards)
            ),
            Payload::WeisResolved { seat, team, points } => {
                format!("\"seat\":{seat},\"team\":{team},{}", pair("points", *points))
            }
            Payload::Stoeck { seat, points, trick } => {
                format!("\"seat\":{seat},\"points\":{points},\"trick\":{trick}")
            }
            Payload::CardPlayed { seat, card } => {
                format!("\"seat\":{seat},\"card\":\"{}\"", format_card(*card))
            }
            Payload::TrickWon { seat, trick, cards } => {
                format!("\"seat\":{seat},\"trick\":{trick},\"cards\":{}", cards_json(cards))
            }
            Payload::RoundScored { round, detail } => format!(
                "\"round\":{round},{},{},{},{},{},\"multiplier\":{},{},{}",
                pair("trick_points", detail.trick_points),
                pair("last_trick", detail.last_trick),
                pair("match", detail.match_bonus),
                pair("weis", detail.weis),
                pair("stoeck", detail.stoeck),
                detail.multiplier,
                pair("round_total", detail.round_total),
                pair("scores", detail.scores),
            ),
            Payload::SidiRoundScored { round, detail } => format!(
                "\"round\":{round},{},{},{},\"bid\":{},\"doubled\":{},\"made\":{},{},{},{}",
                pair("trick_points", detail.trick_points),
                pair("last_trick", detail.last_trick),
                pair("match", detail.match_bonus),
                detail.bid,
                detail.doubled,
                detail.made,
                pair("bonus", detail.bonus),
                pair("round_total", detail.round_total),
                pair("scores", detail.scores),
            ),
            Payload::SidiGameOver { winner, scores } => format!(
                "\"winner\":{winner},{},\"decided_by\":\"score\"",
                pair("scores", *scores)
            ),
            Payload::GameOver { winner, scores, decided_by, claim_order } => {
                let names: Vec<String> = claim_order
                    .iter()
                    .map(|k| format!("\"{}\"", claim_name(*k)))
                    .collect();
                format!(
                    "\"winner\":{winner},{},\"decided_by\":\"{decided_by}\",\"claim_order\":[{}]",
                    pair("scores", *scores),
                    names.join(",")
                )
            }
        };
        format!("{head},{body}}}")
    }
}

#[derive(Default, Debug, Clone)]
pub struct EventLog {
    events: Vec<Event>,
}

impl EventLog {
    pub fn emit(&mut self, payload: Payload, private_to: Option<usize>) {
        self.events.push(Event { seq: self.events.len() + 1, payload, private_to });
    }

    pub fn len(&self) -> usize {
        self.events.len()
    }

    pub fn is_empty(&self) -> bool {
        self.events.is_empty()
    }

    pub fn all(&self) -> &[Event] {
        &self.events
    }

    /// Events this seat may see, from `after` exclusive. A client sends the last `seq` it
    /// received and gets exactly what it missed — that is the whole reconnection story.
    pub fn for_seat(&self, seat: usize, after: usize) -> Vec<&Event> {
        self.events
            .iter()
            .filter(|e| e.seq > after && e.visible_to(seat))
            .collect()
    }
}
