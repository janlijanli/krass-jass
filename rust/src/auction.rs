//! The Sidi Barrani auction. Twin of `krass_jass/auction.py`; rules in
//! `docs/rules-config.md`, "Sidi Barrani".
//!
//! A pure state machine over calls. It knows nothing about cards, which is what makes the
//! whole auction public.

use crate::cards::NUM_SEATS;
use crate::config::Rules;
use crate::tables::{contract_name, CONTRACT_NAMES, NUM_CONTRACTS};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Call {
    Pass,
    Double,
    Bid { contract: usize, value: i32 },
}

impl Call {
    /// The wire form: `PASS`, `DOUBLE`, or `HEARTS 100`.
    pub fn name(&self) -> String {
        match self {
            Call::Pass => "PASS".into(),
            Call::Double => "DOUBLE".into(),
            Call::Bid { contract, value } => format!("{} {value}", contract_name(*contract)),
        }
    }

    pub fn parse(text: &str) -> Option<Call> {
        let upper = text.trim().to_ascii_uppercase();
        let words: Vec<&str> = upper.split_whitespace().collect();
        match words.as_slice() {
            ["PASS"] => Some(Call::Pass),
            ["DOUBLE"] => Some(Call::Double),
            [name, value] => {
                let contract = CONTRACT_NAMES.iter().position(|n| n == name)?;
                if !value.bytes().all(|b| b.is_ascii_digit()) {
                    return None;
                }
                Some(Call::Bid {
                    contract,
                    value: value.parse().ok()?,
                })
            }
            _ => None,
        }
    }
}

#[derive(Debug, PartialEq, Eq)]
pub enum AuctionError {
    Over,
    NotYourTurn(usize),
    MayNotDouble,
    NotOnLadder(i32),
    TooLow(i32),
}

#[derive(Clone, Debug)]
pub struct Auction {
    pub opener: usize,
    pub calls: Vec<(usize, Call)>,
    /// (seat, contract, value) of the standing bid.
    pub high: Option<(usize, usize, i32)>,
    pub doubled: bool,
    /// Passes in a row since the last bid, or since the start.
    pub passes: usize,
    rules: Rules,
}

impl Auction {
    pub fn new(opener: usize, rules: Rules) -> Self {
        Auction {
            opener,
            calls: Vec::new(),
            high: None,
            doubled: false,
            passes: 0,
            rules,
        }
    }

    pub fn done(&self) -> bool {
        if self.doubled && self.rules.sidi_double_ends_auction {
            return true;
        }
        match self.high {
            None => self.passes >= NUM_SEATS,
            Some((_, _, value)) => {
                self.passes >= NUM_SEATS - 1 || value >= *self.rules.sidi_bids.last().unwrap()
            }
        }
    }

    /// All four passed before anyone bid.
    pub fn thrown_in(&self) -> bool {
        self.done() && self.high.is_none()
    }

    pub fn to_act(&self) -> Option<usize> {
        if self.done() {
            None
        } else {
            Some((self.opener + self.calls.len()) % NUM_SEATS)
        }
    }

    pub fn may_double(&self, seat: usize) -> bool {
        match self.high {
            Some((bidder, _, _)) => !self.doubled && (seat + NUM_SEATS - bidder) % 2 == 1,
            None => false,
        }
    }

    /// Every call the seat may make now, lowest bid first. Same order as Python's.
    pub fn legal_calls(&self, seat: usize) -> Vec<Call> {
        if self.to_act() != Some(seat) {
            return Vec::new();
        }
        let floor = self.high.map_or(0, |h| h.2);
        let mut out = vec![Call::Pass];
        if self.may_double(seat) {
            out.push(Call::Double);
        }
        for &value in self.rules.sidi_bids.iter().filter(|&&v| v > floor) {
            for contract in 0..NUM_CONTRACTS {
                out.push(Call::Bid { contract, value });
            }
        }
        out
    }

    pub fn call(&mut self, seat: usize, call: Call) -> Result<(), AuctionError> {
        if self.done() {
            return Err(AuctionError::Over);
        }
        if self.to_act() != Some(seat) {
            return Err(AuctionError::NotYourTurn(seat));
        }
        match call {
            Call::Pass => self.passes += 1,
            Call::Double => {
                if !self.may_double(seat) {
                    return Err(AuctionError::MayNotDouble);
                }
                self.doubled = true;
            }
            Call::Bid { contract, value } => {
                if contract >= NUM_CONTRACTS || !self.rules.sidi_bids.contains(&value) {
                    return Err(AuctionError::NotOnLadder(value));
                }
                if let Some((_, _, high)) = self.high {
                    if value <= high {
                        return Err(AuctionError::TooLow(high));
                    }
                }
                self.high = Some((seat, contract, value));
                self.passes = 0;
                // A double that did not end the auction was a double of the bid it named.
                self.doubled = false;
            }
        }
        self.calls.push((seat, call));
        Ok(())
    }
}

/// What the bid is worth to whichever team it goes to.
pub fn bonus(value: i32, doubled: bool) -> i32 {
    value * if doubled { 2 } else { 1 }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn three_passes_after_a_bid_end_it() {
        let mut a = Auction::new(1, Rules::sidi());
        a.call(
            1,
            Call::Bid {
                contract: 1,
                value: 60,
            },
        )
        .unwrap();
        for seat in [2, 3] {
            a.call(seat, Call::Pass).unwrap();
        }
        assert!(!a.done());
        a.call(0, Call::Pass).unwrap();
        assert!(a.done() && !a.thrown_in());
    }

    #[test]
    fn only_opponents_double() {
        let mut a = Auction::new(0, Rules::sidi());
        a.call(
            0,
            Call::Bid {
                contract: 3,
                value: 70,
            },
        )
        .unwrap();
        a.call(1, Call::Pass).unwrap();
        assert_eq!(a.call(2, Call::Double), Err(AuctionError::MayNotDouble));
        a.call(2, Call::Pass).unwrap();
        a.call(3, Call::Double).unwrap();
        assert!(a.done() && a.doubled);
    }

    #[test]
    fn calls_round_trip() {
        for text in ["PASS", "DOUBLE", "HEARTS 100", "UNDENUFE 257"] {
            assert_eq!(Call::parse(text).unwrap().name(), text);
        }
        assert!(Call::parse("HEARTS 1x").is_none());
    }
}
