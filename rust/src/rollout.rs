//! The rollout kernel and trick resolution.
//!
//! This is the code the whole Rust port exists for. `docs/plan-review.md` §1 measured the
//! Python version at ~72k rollouts/sec; the search on top of it ran at 35k iterations/sec,
//! with 73% of time in here. Note that porting *only* this would have been worth ~2.4x —
//! the tree in `search.rs` had to come with it.

use crate::cards::*;
use crate::legal::legal_moves;
use crate::tables::{CARD_VALUES, STRENGTH};
use crate::rng::Rng;

/// Everything the kernel needs, flattened once outside the loop.
///
/// `contract` and `trump` are the order the *current trick* is played in; `count` the contract
/// cards are valued in. They differ only for the Coiffeur's extra rows (`schedule.rs`), where the
/// order changes from trick to trick: take the kernel for a trick with `at` or `at_trick`, and
/// read card values from `count`. For every other round all three are one contract, so code that
/// asks for the kernel of a trick it is already in gets back exactly what it had.
///
/// A Tutti names each trick by its lead card, so `at` takes the trick's cards; and before the
/// round's first card `count` is a placeholder with `count_open` set, until `on_card` fixes it.
#[derive(Clone, Copy)]
pub struct Kernel {
    pub contract: usize,
    pub trump: i32,
    pub count: usize,
    /// Tutti before its first card: `count` is a placeholder until `on_card` sees the lead.
    pub count_open: bool,
    pub schedule: Option<[u8; TRICKS_PER_ROUND]>,
    pub strict_undertrump: bool,
    pub puur_exempt: bool,
    pub last_trick_bonus: i32,
    pub match_bonus: i32,
}

impl Kernel {
    pub fn new(
        contract: usize,
        strict_undertrump: bool,
        puur_exempt: bool,
        last_trick_bonus: i32,
        match_bonus: i32,
    ) -> Self {
        Kernel {
            contract,
            trump: if contract < 4 { contract as i32 } else { -1 },
            count: contract,
            count_open: false,
            schedule: None,
            strict_undertrump,
            puur_exempt,
            last_trick_bonus,
            match_bonus,
        }
    }
}

/// A 3x3 block not yet named, in the packed schedule.
const OPEN: u8 = u8::MAX;
/// A Tutti trick, named by its lead card, in the packed schedule.
const LED: u8 = u8::MAX - 1;

impl Kernel {
    /// The same kernel, played trick by trick to `schedule` (each trick's contract) and counted
    /// in the round's first trick's. Positioned at the first trick; use `at` to move it.
    pub fn with_schedule(mut self, schedule: Option<[usize; TRICKS_PER_ROUND]>) -> Self {
        if let Some(s) = schedule {
            let mut packed = [0u8; TRICKS_PER_ROUND];
            for (p, &c) in packed.iter_mut().zip(&s) {
                *p = match c {
                    crate::schedule::UNNAMED => OPEN,
                    crate::schedule::LED => LED,
                    _ => c as u8,
                };
            }
            self.schedule = Some(packed);
            self.count_open = s[0] == crate::schedule::LED;
            self.count = if self.count_open { crate::schedule::TUTTI_PLACEHOLDER } else { s[0] };
            self = self.at_trick(0);
        }
        self
    }

    /// The same kernel with every 3x3 block still to be named drawn at random from what its
    /// leader may name. The search does this once per iteration: who leads trick 4 or 7 is not
    /// known yet, and neither is what they will pick, so it is treated as chance — like the cards
    /// in the other hands, and with the same caveat that a real player chooses.
    pub fn sample_open(&self, rng: &mut Rng) -> Kernel {
        let Some(s) = self.schedule else { return *self };
        if !s.contains(&OPEN) {
            return *self;
        }
        let mut full = s.map(|c| match c {
            OPEN => crate::schedule::UNNAMED,
            LED => crate::schedule::LED,
            _ => c as usize,
        });
        for &b in &crate::schedule::TRIO_BLOCKS[1..] {
            if full[b] == crate::schedule::UNNAMED {
                let options = crate::schedule::block_options(&full, b);
                let c = options[rng.below(options.len() as u32) as usize];
                full[b..b + 3].fill(c);
            }
        }
        Kernel {
            schedule: Some(full.map(|c| match c {
                crate::schedule::UNNAMED => OPEN,
                crate::schedule::LED => LED,
                _ => c as u8,
            })),
            ..*self
        }
    }

    /// The kernel for trick `t` (0-based) of the round. A block not named (only before
    /// `sample_open`) and a Tutti trick not led read as the counting contract.
    #[inline(always)]
    pub fn at_trick(&self, t: usize) -> Kernel {
        self.at_trick_led(t, None)
    }

    /// The kernel for trick `t` whose first card, if it has been played, is `lead`.
    #[inline(always)]
    pub fn at_trick_led(&self, t: usize, lead: Option<usize>) -> Kernel {
        match self.schedule {
            None => *self,
            Some(s) => {
                let named = s[t.min(TRICKS_PER_ROUND - 1)];
                let c = match named {
                    OPEN => self.count,
                    LED => lead.map_or(self.count, card_suit),
                    _ => named as usize,
                };
                Kernel { contract: c, trump: if c < 4 { c as i32 } else { -1 }, ..*self }
            }
        }
    }

    /// The kernel for the trick in progress, given every hand still held and the cards already
    /// on the table in this trick.
    #[inline(always)]
    pub fn at(&self, hands: &[u64; NUM_SEATS], trick: &[usize]) -> Kernel {
        if self.schedule.is_none() {
            return *self;
        }
        let held: usize = hands.iter().map(|h| h.count_ones() as usize).sum();
        self.at_trick_led((NUM_CARDS - held - trick.len()) / NUM_SEATS, trick.first().copied())
    }

    /// Note a card about to be played, `leads` if it starts a trick. A Tutti's first card fixes
    /// what the round is counted in; nothing else changes.
    #[inline(always)]
    pub fn on_card(&mut self, card: usize, leads: bool) {
        if self.count_open && leads {
            self.count = card_suit(card);
            self.count_open = false;
        }
    }
}

/// Uniform pick over the set bits of `mask`. Returns the card index.
#[inline(always)]
pub fn pick_random(mask: u64, rng: &mut Rng) -> usize {
    let n = mask.count_ones();
    let mut m = mask;
    let skip = rng.below(n);
    for _ in 0..skip {
        m &= m - 1;
    }
    m.trailing_zeros() as usize
}

/// Play out at random until the hands are empty. Returns team points.
///
/// Precondition, as in the Python kernel: the position is at a trick boundary, so every
/// hand holds the same number of cards. The match bonus is only awarded when the playout
/// covered a whole round — from a partial position the kernel cannot know who took the
/// earlier tricks.
pub fn play_out(hands: &mut [u64; NUM_SEATS], mut leader: usize, k: &Kernel, rng: &mut Rng) -> (i32, i32) {
    let mut base = *k;
    let mut values = &CARD_VALUES[base.count];

    let n_tricks = hands[leader].count_ones() as usize;
    if n_tricks == 0 {
        return (0, 0);
    }

    let mut pts = [0i32; 2];
    let mut tricks = [0usize; 2];
    let first = TRICKS_PER_ROUND - n_tricks;

    for t in 0..n_tricks {
        let mut k = base.at_trick(first + t);
        let mut strength_by_led = &STRENGTH[k.contract];
        let mut led: i32 = -1;
        let mut best_trump: i32 = -1;
        let mut strength: &[i32; NUM_CARDS] = &strength_by_led[0];
        let mut trick_pts = 0i32;
        let mut best_seat = leader;
        let mut best_str = -1i32;

        for i in 0..NUM_SEATS {
            let seat = (leader + i) & 3;
            let hand = hands[seat];
            let legal = legal_moves(
                hand,
                k.trump,
                led,
                best_trump,
                k.strict_undertrump,
                k.puur_exempt,
            );
            let c = pick_random(legal, rng);

            if i == 0 && k.schedule.is_some() {
                // Tutti: the lead names the trick, and the round's first card its count.
                base.on_card(c, true);
                values = &CARD_VALUES[base.count];
                k = base.at_trick_led(first + t, Some(c));
                strength_by_led = &STRENGTH[k.contract];
            }
            hands[seat] = hand ^ (1u64 << c);
            trick_pts += values[c];

            if i == 0 {
                led = card_suit(c) as i32;
                strength = &strength_by_led[led as usize];
                best_str = strength[c];
            } else {
                let s = strength[c];
                if s > best_str {
                    best_str = s;
                    best_seat = seat;
                }
            }
            if k.trump >= 0 && card_suit(c) as i32 == k.trump {
                let ts = strength[c] - 100;
                if ts > best_trump {
                    best_trump = ts;
                }
            }
        }

        let team = best_seat & 1;
        pts[team] += trick_pts;
        tricks[team] += 1;
        leader = best_seat;
    }

    pts[leader & 1] += k.last_trick_bonus;
    if k.match_bonus != 0 && n_tricks == TRICKS_PER_ROUND {
        for t in 0..2 {
            if tricks[t] == TRICKS_PER_ROUND {
                pts[t] += k.match_bonus;
            }
        }
    }
    (pts[0], pts[1])
}
