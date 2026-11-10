//! Table conventions — the ordering applied to moves the search rated the same.
//!
//! Mirror of `krass_jass/convention.py`; the Python module carries the reasoning. The rule
//! that matters in both: this never takes a move the search preferred, only reorders the ones
//! it could not separate.

use crate::cards::{card_list, card_suit, NUM_RANKS, NUM_SEATS, RANK_9, RANK_J, SUIT_MASK};
use crate::search::Candidate;
use crate::tables::{CARD_VALUES, OBENABE, STRENGTH, UNDENUFE};

/// A visit slack of 1 lifts the visit condition, leaving the score slack as a pure price.
const PRICE_ONLY: f64 = 1.0;
const SCORE_SLACK: f64 = 0.01;
/// Mirror of `MIN_VISIT_SHARE` in Python: nothing barely explored is ever eligible.
const MIN_VISIT_SHARE: f64 = 0.005;

/// The other suit of the same colour — `♦0 ↔ ♥1`, `♠2 ↔ ♣3`.
pub fn sister(suit: usize) -> usize {
    suit ^ 1
}

/// How much a seat's discards have said, in `Signal::strength`. Mirror of the Python constants.
pub const NO_SIGNAL: u8 = 0;
pub const SCHMIER_ONLY: u8 = 1;
pub const SIGNALLED: u8 = 2;
pub const CONFIRMED: u8 = 3;

/// The suit a discard of `suit` asks for under the colour-pair convention: the sister, unless
/// the sister is trump — then the suit itself. Mirror of `signal_target` in Python.
pub fn signal_target(suit: usize, trump: i32) -> usize {
    if trump >= 0 && sister(suit) == trump as usize { suit } else { sister(suit) }
}

/// What one seat's discards have said this round. Mirror of `Signal` in `convention.py`,
/// which carries the reasoning.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Signal {
    pub wanted: i32,
    pub strength: u8,
    pub thrown: u8,
}

impl Default for Signal {
    fn default() -> Self {
        Signal { wanted: -1, strength: NO_SIGNAL, thrown: 0 }
    }
}

impl Signal {
    /// The suit asked for if the evidence is more than a schmier, else -1.
    pub fn asked(&self) -> i32 {
        if self.strength >= SIGNALLED { self.wanted } else { -1 }
    }

    /// Suits thrown that were not the one asked for.
    pub fn avoid(&self) -> u8 {
        if self.wanted >= 0 { self.thrown & !(1u8 << self.wanted) } else { self.thrown }
    }

    pub fn observe(self, suit: usize, trump: i32, schmier: bool) -> Signal {
        let target = signal_target(suit, trump) as i32;
        let thrown = self.thrown | 1u8 << suit;
        if self.strength == NO_SIGNAL || (self.strength == SCHMIER_ONLY && !schmier) {
            return Signal { wanted: target, strength: if schmier { SCHMIER_ONLY } else { SIGNALLED }, thrown };
        }
        if suit as i32 == self.wanted && target != self.wanted {
            return Signal { strength: SCHMIER_ONLY, thrown, ..self };
        }
        if schmier {
            return Signal { thrown, ..self };
        }
        Signal { strength: CONFIRMED, thrown, ..self }
    }
}

/// Reads the signals play by play — for a caller replaying a round, like the belief weighting.
#[derive(Clone, Debug)]
pub struct SignalTracker {
    pub seats: [Signal; NUM_SEATS],
    trump: i32,
    contract: usize,
    leader: usize,
    trick: Vec<usize>,
    best: usize,
}

impl SignalTracker {
    pub fn new(contract: usize) -> Self {
        SignalTracker {
            seats: [Signal::default(); NUM_SEATS],
            trump: if contract < 4 { contract as i32 } else { -1 },
            contract,
            leader: 0,
            trick: Vec::with_capacity(NUM_SEATS),
            best: 0,
        }
    }

    pub fn play(&mut self, seat: usize, card: usize) {
        if self.trick.is_empty() {
            self.leader = seat;
            self.best = 0;
        } else {
            let led = card_suit(self.trick[0]);
            let suit = card_suit(card);
            if suit != led && suit as i32 != self.trump {
                let winner = (self.leader + self.best) % NUM_SEATS;
                let schmier = winner % 2 == seat % 2 && CARD_VALUES[self.contract][card] >= 10;
                self.seats[seat] = self.seats[seat].observe(suit, self.trump, schmier);
            }
            let by_led = &STRENGTH[self.contract][led];
            if by_led[card] > by_led[self.trick[self.best]] {
                self.best = self.trick.len();
            }
        }
        self.trick.push(card);
        if self.trick.len() == NUM_SEATS {
            self.trick.clear();
        }
    }
}

/// Every seat's signal from a `(seat, card)` history in play order, tricks of four.
pub fn read_signals(history: &[(usize, usize)], contract: usize) -> [Signal; NUM_SEATS] {
    let mut t = SignalTracker::new(contract);
    for &(s, c) in history {
        t.play(s, c);
    }
    t.seats
}

/// The same, from the round's tricks and the one in play.
pub fn read_signals_tricks(
    tricks_played: &[(usize, Vec<usize>)],
    trick: &[usize],
    trick_leader: usize,
    contract: usize,
) -> [Signal; NUM_SEATS] {
    let mut t = SignalTracker::new(contract);
    let current = (trick_leader, trick.to_vec());
    for (leader, cards) in tricks_played.iter().chain(std::iter::once(&current)) {
        for (i, &c) in cards.iter().enumerate() {
            t.play((leader + i) % NUM_SEATS, c);
        }
    }
    t.seats
}

/// The table's discard convention and what it has said, as `choose` reads it. `sister` off is
/// the default "throw the weakest" convention, read through `discarded` alone.
#[derive(Clone, Copy, Debug, Default)]
pub struct Signals {
    pub sister: bool,
    pub seats: [Signal; NUM_SEATS],
    /// The partner's thrown suits, for the default convention (`partner_discards`).
    pub discarded: u8,
}

/// The strongest card of `suit` not yet played, as a single-bit mask. Strength, not rank:
/// Undenufe runs the other way.
fn top_live(live: u64, suit: usize, contract: usize) -> u64 {
    let cards = live & SUIT_MASK[suit];
    if cards == 0 {
        return 0;
    }
    let strength = &STRENGTH[contract][suit];
    let best = card_list(cards)
        .into_iter()
        .max_by_key(|&c| strength[c])
        .expect("non-empty");
    1u64 << best
}

/// The side suit this hand would like led to it.
pub fn wanted_suit(hand: u64, unseen: u64, trump: i32, contract: usize) -> i32 {
    let live = hand | unseen;
    let mut best: i32 = -1;
    let mut best_score = -1.0f64;
    for suit in 0..4usize {
        if trump >= 0 && suit == trump as usize {
            continue;
        }
        let mine = hand & SUIT_MASK[suit];
        if mine == 0 {
            continue;
        }
        let mut score = 0.1 * mine.count_ones() as f64;
        if top_live(live, suit, contract) & hand != 0 {
            score += 2.0;
        }
        if score > best_score {
            best = suit as i32;
            best_score = score;
        }
    }
    best
}

/// Whether both opponents are *proven* to hold no trump.
pub fn opponents_out_of_trump(
    forbidden: &[u64; NUM_SEATS],
    seen: u64,
    seat: usize,
    trump: i32,
) -> bool {
    if trump < 0 {
        return false;
    }
    let unseen_trumps = SUIT_MASK[trump as usize] & !seen;
    (0..NUM_SEATS)
        .filter(|other| (other + NUM_SEATS - seat) % 2 == 1)
        .all(|other| unseen_trumps & !forbidden[other] == 0)
}

/// What a convention may cost in the shipped bots: no visit condition beyond the floor, and at
/// most `SCORE_SLACK` of a round's share by the search's own estimate — a price rather than a
/// tie window. In step with `DmctsAgent.convention_slack`, which carries the measurement.
pub const DEFAULT_SLACK: (f64, f64) = (PRICE_ONLY, SCORE_SLACK);

/// Suits the partner has thrown away, as a 4-bit mask. Mirror of `partner_discards` in Python.
pub fn partner_discards(
    tricks_played: &[(usize, Vec<usize>)],
    trick: &[usize],
    trick_leader: usize,
    seat: usize,
    trump: i32,
) -> u8 {
    let partner = seat ^ 2;
    let mut mask = 0u8;
    let current = (trick_leader, trick.to_vec());
    for (leader, cards) in tricks_played.iter().chain(std::iter::once(&current)) {
        let Some(&first) = cards.first() else { continue };
        let led = card_suit(first);
        for (i, &c) in cards.iter().enumerate() {
            let suit = card_suit(c);
            if (leader + i) % NUM_SEATS == partner && suit != led && suit as i32 != trump {
                mask |= 1 << suit;
            }
        }
    }
    mask
}

fn suit_strength(hand: u64, live: u64, suit: usize, contract: usize) -> f64 {
    let mine = hand & SUIT_MASK[suit];
    if mine == 0 {
        return -1.0;
    }
    let values = &CARD_VALUES[contract];
    let points: i32 = card_list(mine).iter().map(|&c| values[c]).sum();
    let mut score = 0.1 * mine.count_ones() as f64 + points as f64 / 11.0;
    if top_live(live, suit, contract) & hand != 0 {
        score += 2.0;
    }
    score
}

/// First card with the smallest key — Python's `min` keeps the first of equals, and so must this.
fn first_min<K: PartialOrd>(cards: &[usize], key: impl Fn(usize) -> K) -> Option<usize> {
    let mut best: Option<(usize, K)> = None;
    for &c in cards {
        let k = key(c);
        if best.as_ref().map_or(true, |(_, b)| k < *b) {
            best = Some((c, k));
        }
    }
    best.map(|(c, _)| c)
}

fn first_max<K: PartialOrd>(cards: &[usize], key: impl Fn(usize) -> K) -> Option<usize> {
    let mut best: Option<(usize, K)> = None;
    for &c in cards {
        let k = key(c);
        if best.as_ref().map_or(true, |(_, b)| k > *b) {
            best = Some((c, k));
        }
    }
    best.map(|(c, _)| c)
}

fn lowest(cards: &[usize], contract: usize) -> Option<usize> {
    let values = &CARD_VALUES[contract];
    first_min(cards, |c| (values[c], STRENGTH[contract][card_suit(c)][c]))
}

/// The card to play, given what the search returned. Mirror of `choose` in
/// `krass_jass/convention.py`, which carries the reasoning; `declaring` is whether this seat's
/// team declared, `signals` what the table's discards have said.
#[allow(clippy::too_many_arguments)]
pub fn choose(
    candidates: &[Candidate],
    hand: u64,
    unseen: u64,
    seen: u64,
    trick: &[usize],
    seat: usize,
    trump: i32,
    contract: usize,
    forbidden: &[u64; NUM_SEATS],
    declaring: bool,
    slack: (f64, f64),
    signals: &Signals,
) -> Option<usize> {
    let best = candidates.first()?;
    let fallback = best.card;
    let (vote_slack, score_slack) = slack;

    // Every determinization votes for exactly one move, so the votes sum to the budget.
    let total: u32 = candidates.iter().map(|c| c.determinizations_selecting).sum();
    let slack = ((vote_slack * total.max(1) as f64).round() as u32).max(1);
    let floor = MIN_VISIT_SHARE * total as f64;
    let cards: Vec<usize> = candidates
        .iter()
        .enumerate()
        .filter(|(i, c)| {
            c.determinizations_selecting + slack >= best.determinizations_selecting
                && c.mean_score >= best.mean_score - score_slack
                && (*i == 0 || c.determinizations_selecting as f64 >= floor)
        })
        .map(|(_, c)| c)
        .map(|c| c.card)
        .collect();
    if cards.len() < 2 {
        return Some(fallback);
    }

    let live = hand | unseen;
    let is_boss = |c: usize| top_live(live, card_suit(c), contract) == 1u64 << c;
    let pick = if trick.is_empty() {
        let partner = signals.sister.then(|| signals.seats[seat ^ 2]);
        lead(&cards, hand, live, seen, seat, trump, contract, forbidden, declaring, signals.discarded,
             partner, &is_boss)
    } else {
        let mine = signals.sister.then(|| signals.seats[seat]);
        follow(&cards, hand, unseen, live, trick, seat, trump, contract, mine, &is_boss)
    };
    Some(pick.unwrap_or(fallback))
}

#[allow(clippy::too_many_arguments)]
fn lead(
    cards: &[usize],
    hand: u64,
    live: u64,
    seen: u64,
    seat: usize,
    trump: i32,
    contract: usize,
    forbidden: &[u64; NUM_SEATS],
    declaring: bool,
    discarded: u8,
    partner: Option<Signal>,
    is_boss: &dyn Fn(usize) -> bool,
) -> Option<usize> {
    let discarded = partner.map_or(discarded, |p| p.avoid());
    let values = &CARD_VALUES[contract];
    let out_of_trump = opponents_out_of_trump(forbidden, seen, seat, trump);
    let boss: Vec<usize> = cards.iter().copied().filter(|&c| is_boss(c)).collect();
    let highest = |cs: &[usize]| first_max(cs, |c| (values[c], -(c as i64)));

    // 1. The opponents are out of trump: the best card left in a side suit is a trick.
    if out_of_trump && !boss.is_empty() {
        return highest(&boss);
    }

    let mut held: Vec<usize> = Vec::new();
    let bauer = if trump >= 0 { trump as usize * NUM_RANKS + RANK_J } else { usize::MAX };
    if trump >= 0 {
        let strength = &STRENGTH[contract][trump as usize];
        held = card_list(hand & SUIT_MASK[trump as usize]);
        held.sort_by_key(|&c| -strength[c]);
    }

    // 2. Trumpf ziehen, by the Swiss rules.
    if declaring && !held.is_empty() && !out_of_trump {
        let n = held.len();
        let target = if held.contains(&bauer) {
            if n == 2 { Some(held[1]) } else if n >= 3 { Some(bauer) } else { None }
        } else if top_live(live, trump as usize, contract) == 1u64 << held[0] {
            if n >= 2 { Some(held[0]) } else { None }
        } else if n >= 3 {
            Some(held[1])
        } else {
            None
        };
        if let Some(t) = target {
            if cards.contains(&t) {
                return Some(t);
            }
        }
    }

    // 3. The Bauer "blutt": show it with a Brettli of the strongest side suit.
    if declaring && held.len() == 1 && held[0] == bauer {
        let brettli: Vec<usize> = cards
            .iter()
            .copied()
            .filter(|&c| card_suit(c) as i32 != trump && c % NUM_RANKS >= RANK_9)
            .collect();
        if !brettli.is_empty() {
            let suits: Vec<usize> = (0..4).collect();
            let best = first_max(&suits, |s| {
                if s as i32 == trump { 0.0 } else { suit_strength(hand, live, s, contract) + 10.0 }
            })
            .unwrap_or(0);
            return first_min(&brettli, |c| (card_suit(c) != best, values[c], -(c as i64)));
        }
    }

    // 3b. Farbpaar — bring the suit the partner asked for: its best card if held, else the lowest.
    if let Some(p) = partner {
        let asked = p.asked();
        if asked >= 0 && asked != trump {
            let in_suit: Vec<usize> =
                cards.iter().copied().filter(|&c| card_suit(c) as i32 == asked).collect();
            if !in_suit.is_empty() {
                let mine: Vec<usize> = in_suit.iter().copied().filter(|c| boss.contains(c)).collect();
                return if mine.is_empty() { lowest(&in_suit, contract) } else { highest(&mine) };
            }
        }
    }

    // 4. Cash from the top, avoiding a suit the partner threw away.
    let side: Vec<usize> = boss.iter().copied().filter(|&c| card_suit(c) as i32 != trump).collect();
    if !side.is_empty() {
        let wanted: Vec<usize> =
            side.iter().copied().filter(|&c| discarded >> card_suit(c) & 1 == 0).collect();
        return highest(if wanted.is_empty() { &side } else { &wanted });
    }

    // 5. Anziehen — in the strongest suit without its best card, lead the lowest.
    let suits: Vec<usize> = (0..4)
        .filter(|&s| {
            s as i32 != trump
                && discarded >> s & 1 == 0
                && (hand & SUIT_MASK[s]).count_ones() >= 2
                && top_live(live, s, contract) & hand == 0
                && cards.iter().any(|&c| card_suit(c) == s)
        })
        .collect();
    if let Some(strong) = first_max(&suits, |s| suit_strength(hand, live, s, contract)) {
        let in_suit: Vec<usize> = cards.iter().copied().filter(|&c| card_suit(c) == strong).collect();
        return lowest(&in_suit, contract);
    }
    None
}

#[allow(clippy::too_many_arguments)]
fn follow(
    cards: &[usize],
    hand: u64,
    unseen: u64,
    live: u64,
    trick: &[usize],
    seat: usize,
    trump: i32,
    contract: usize,
    mine: Option<Signal>,
    is_boss: &dyn Fn(usize) -> bool,
) -> Option<usize> {
    let values = &CARD_VALUES[contract];
    let led = card_suit(trick[0]);
    let by_led = &STRENGTH[contract][led];
    let trick_leader = (seat + NUM_SEATS - trick.len()) % NUM_SEATS;
    let positions: Vec<usize> = (0..trick.len()).collect();
    let best_i = first_max(&positions, |i| by_led[trick[i]]).unwrap_or(0);
    let winner = (trick_leader + best_i) % NUM_SEATS;
    let partner = seat ^ 2;
    let best_strength = by_led[trick[best_i]];
    let is_trump = |c: usize| trump >= 0 && card_suit(c) == trump as usize;

    // 1. Obenabe/Undenufe: drop the next card under the partner's best one.
    if (contract == OBENABE || contract == UNDENUFE) && trick_leader == partner {
        let top = trick[0];
        let in_suit: Vec<usize> = (led * NUM_RANKS..(led + 1) * NUM_RANKS).collect();
        if first_max(&in_suit, |c| by_led[c]) == Some(top) {
            let rest: Vec<usize> = in_suit.iter().copied().filter(|&c| c != top).collect();
            if let Some(next) = first_max(&rest, |c| by_led[c]) {
                if cards.contains(&next) {
                    return Some(next);
                }
            }
        }
    }

    if winner == partner {
        // 2. Schmieren, last to play; and never trump the partner's trick.
        if trick.len() == 3 {
            let gifts: Vec<usize> =
                cards.iter().copied().filter(|&c| !is_trump(c) && !is_boss(c)).collect();
            if !gifts.is_empty() {
                return first_max(&gifts, |c| (values[c], -(c as i64)));
            }
        }
        let plain: Vec<usize> = cards.iter().copied().filter(|&c| !is_trump(c)).collect();
        if !plain.is_empty() && plain.len() < cards.len() {
            return lowest(&plain, contract);
        }
    }

    // 3. Verwerfen — throw from the weakest side suit, lowest first, never the best left.
    let throws: Vec<usize> = cards
        .iter()
        .copied()
        .filter(|&c| card_suit(c) != led && !is_trump(c) && !is_boss(c))
        .collect();
    if !throws.is_empty() {
        // Farbpaar: signal given, throw anything but the suit asked for; not yet, ask for the
        // suit this hand wants by throwing its target.
        let mut keep: i32 = -1;
        if let Some(m) = mine {
            keep = if m.asked() >= 0 { m.asked() } else { wanted_suit(hand, unseen, trump, contract) };
            if m.asked() < 0 && keep >= 0 {
                let target = signal_target(keep as usize, trump);
                let ask: Vec<usize> = throws.iter().copied().filter(|&c| card_suit(c) == target).collect();
                if !ask.is_empty() {
                    return lowest(&ask, contract);
                }
            }
        }
        let rest: Vec<usize> = throws.iter().copied().filter(|&c| card_suit(c) as i32 != keep).collect();
        let rest = if rest.is_empty() { throws } else { rest };
        let mut suits: Vec<usize> = rest.iter().map(|&c| card_suit(c)).collect();
        suits.sort_unstable();
        suits.dedup();
        let weakest = first_min(&suits, |s| suit_strength(hand, live, s, contract)).unwrap_or(0);
        let in_suit: Vec<usize> = rest.iter().copied().filter(|&c| card_suit(c) == weakest).collect();
        return lowest(&in_suit, contract);
    }

    // 4. An opponent takes the trick and nothing tied can beat it: spend the least.
    if winner != partner && cards.iter().all(|&c| by_led[c] <= best_strength) {
        return lowest(cards, contract);
    }
    None
}
