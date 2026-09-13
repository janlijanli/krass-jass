//! What the table was *told*, as a filter on the worlds the search imagines.
//!
//! Weis is called in two stages and only the second one was being used. `measurements.md`
//! §5l took the cards the winning Weis **shows** and pinned them to that seat, worth +0.62
//! of a round's card points. Stage one is the other half: every seat calls a *value* as its
//! turn comes round in the first trick, and a value nobody ever proves is still public.
//!
//! The value cannot be turned into a per-card mask, which is why §5l left it — "this seat
//! holds a four-card sequence somewhere" forbids no particular card. It is a predicate over
//! whole hands, so it belongs where whole hands are made: a world is dealt and then tested.
//!
//! # What the calls are actually worth, measured before any of this was built
//!
//! Over 40,000 deals under HOUSE rules:
//!
//! | | |
//! |---|---|
//! | a seat calls nothing | **72.3%** |
//! | calls 20 | 21.1% |
//! | calls 50 | 3.7% |
//! | calls 100 or more | 1.8% |
//! | positive calls per round left unshown after §5l | **0.40** |
//!
//! So the information is overwhelmingly in the **silence**, not in the leftover calls: 2.9
//! of the four seats say nothing in an average round, and 69% of rounds have no unshown
//! positive call at all. That decides the shape of the code. Silence is the cheap test —
//! no run of three, no four of a kind, ten instructions of bitboard — and it is the common
//! one. A positive call needs the full `find_weis` and accepts about one world in five, so
//! it is capped rather than insisted on.
//!
//! # Why a cap instead of exact rejection
//!
//! `krass_jass/bidding.py` rejected exact rejection sampling for the bid because Obenabe
//! costs about thirty-six redraws a world. The same arithmetic applies here and lands in a
//! better place: silence accepts at 0.72 a seat, so a typical move redraws about twice.
//! When a rare call makes the constraint expensive the cap runs out and the last world is
//! used anyway — the search then believes exactly what it believed before this file existed.
//! Degrading to the old behaviour is the property that makes an unaffordable constraint
//! safe, and it is the same property the bounded priors have.

use crate::cards::{NUM_RANKS, NUM_SEATS, NUM_SUITS};
use crate::config::Rules;
use crate::determinize::determinize;
use crate::rng::Rng;
use crate::weis::{find_weis, four_points};

/// Worlds drawn before the search settles for one that contradicts a call.
///
/// Sixteen because silence — the case that is nearly always what is being asked — accepts
/// at better than one in three even with three silent seats, so the cap is never reached
/// there; it exists for the calls rare enough that no budget would be enough.
pub const MAX_DRAWS: usize = 16;

const RANK_FIELD: u64 = (1 << NUM_RANKS) - 1;

/// Ranks where four of a kind is worth something. Four sixes is four sixes — the fast gate
/// has to know that or it reports a meld `find_weis` will not find, and the constraint turns
/// into a filter on hands that were never in question.
const FOUR_RANKS: u64 = {
    let mut m = 0u64;
    let mut rank = 0;
    while rank < NUM_RANKS {
        if four_points(rank) != 0 {
            m |= 1 << rank;
        }
        rank += 1;
    }
    m
};

/// Can this hand hold *any* Weis at all? Exact, and ten instructions.
///
/// Every meld is either a run of three or a four of a kind, so if the hand has neither then
/// `find_weis` is going to return nothing and does not need to be asked. This is the whole
/// test for the 72% of seats that called nothing, which is why it is worth having.
fn no_meld_possible(hand: u64) -> bool {
    let mut fours = FOUR_RANKS;
    for suit in 0..NUM_SUITS {
        let ranks = (hand >> (suit * NUM_RANKS)) & RANK_FIELD;
        // Masked to the suit's own nine bits first: a run must not be allowed to straddle
        // the boundary between two suits.
        if ranks & (ranks >> 1) & (ranks >> 2) != 0 {
            return false;
        }
        fours &= ranks;
    }
    fours == 0
}

/// The value a seat holding this hand would have called.
pub fn weis_total(hand: u64, rules: &Rules, trump: i32) -> i32 {
    if no_meld_possible(hand) {
        return 0;
    }
    find_weis(hand, rules, trump).iter().map(|m| m.points).sum()
}

/// The calls, and what it takes to check a world against them.
#[derive(Clone, Copy, Debug)]
pub struct Announcements {
    /// Per seat, the Weis value that seat called; **-1** for a seat with nothing to check —
    /// the searching seat, or a table that has not finished calling.
    pub called: [i32; NUM_SEATS],
    /// Per seat, the cards it has already played. A call is a statement about the nine cards
    /// that were dealt, so a mid-round world has to be put back together before it can be
    /// tested against one. Forgetting this would reject every world from trick two onwards.
    pub played: [u64; NUM_SEATS],
    pub rules: Rules,
    pub trump: i32,
}

impl Announcements {
    /// Nothing to check: the search behaves exactly as it did before this file.
    pub fn none() -> Self {
        Announcements {
            called: [-1; NUM_SEATS],
            played: [0; NUM_SEATS],
            rules: Rules::default(),
            trump: -1,
        }
    }

    pub fn active(&self) -> bool {
        self.called.iter().any(|&c| c >= 0)
    }

    /// Would every seat with a call to its name have made that call, holding this world?
    pub fn consistent(&self, hands: &[u64; NUM_SEATS]) -> bool {
        for seat in 0..NUM_SEATS {
            let called = self.called[seat];
            if called < 0 {
                continue;
            }
            if weis_total(hands[seat] | self.played[seat], &self.rules, self.trump) != called {
                return false;
            }
        }
        true
    }
}

/// Deal a world, preferring one the calls allow.
///
/// Returns false only when the *void* constraints could not be satisfied, which is the same
/// failure `determinize` has always reported. A world that merely contradicts a call is
/// returned rather than refused — see the note on the cap at the top of this file.
#[allow(clippy::too_many_arguments)]
pub fn determinize_consistent(
    unseen: u64,
    counts: &[usize; NUM_SEATS],
    forbidden: &[u64; NUM_SEATS],
    affinity: &[[i8; 4]; NUM_SEATS],
    rank_bias: &[i8; NUM_SEATS],
    ann: &Announcements,
    seat: usize,
    own_hand: u64,
    out: &mut [u64; NUM_SEATS],
    rng: &mut Rng,
) -> bool {
    let draws = if ann.active() { MAX_DRAWS } else { 1 };
    // The last world that was *legal*, as opposed to the last world that was drawn. A failed
    // `determinize` returns having written only some of the seats, so keeping `out` as the
    // fallback would hand the search a deal with cards in two hands at once — which is not a
    // world the calls merely disagree with, it is not a world at all.
    let mut fallback: Option<[u64; NUM_SEATS]> = None;
    for _ in 0..draws {
        let mut dealt = [0u64; NUM_SEATS];
        if !determinize(unseen, counts, forbidden, affinity, rank_bias, &mut dealt, rng) {
            continue;
        }
        dealt[seat] = own_hand;
        if ann.consistent(&dealt) {
            *out = dealt;
            return true;
        }
        fallback = Some(dealt);
    }
    match fallback {
        Some(dealt) => {
            *out = dealt;
            true
        }
        None => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rules() -> Rules {
        Rules::default()
    }

    /// The fast gate has to be *exactly* the question `find_weis` answers, or it turns a
    /// constraint into a silent filter on hands that were always allowed.
    #[test]
    fn the_fast_gate_never_disagrees_with_find_weis() {
        let mut rng = Rng::new(12345);
        for _ in 0..20_000 {
            let mut hand = 0u64;
            while hand.count_ones() < 9 {
                hand |= 1u64 << rng.below(36);
            }
            let melds = find_weis(hand, &rules(), 0);
            assert_eq!(
                no_meld_possible(hand),
                melds.is_empty(),
                "hand {hand:#x} disagrees"
            );
        }
    }

    #[test]
    fn a_hand_is_tested_together_with_what_it_already_played() {
        // A K Q of diamonds is 20, and it is still 20 once the ace has been played to a
        // trick — the call was made when the hand was whole.
        let full = (1u64 << 0) | (1u64 << 1) | (1u64 << 2) | (1u64 << 9) | (1u64 << 20);
        assert_eq!(weis_total(full, &rules(), 0), 20);

        let mut ann = Announcements::none();
        ann.called[1] = 20;
        ann.played[1] = (1u64 << 0);
        let mut hands = [0u64; NUM_SEATS];
        hands[1] = full & !(1u64 << 0);
        assert!(ann.consistent(&hands));

        ann.played[1] = 0;
        assert!(!ann.consistent(&hands), "without the played card this is a bare pair");
    }

    /// A call the search cannot satisfy must cost it *sampling*, never correctness. This is
    /// the failure that got through review and was caught by whole games: a `determinize`
    /// that gives up partway has written some seats and not others, so keeping the last
    /// *drawn* world rather than the last *legal* one deals the same card to two hands.
    #[test]
    fn an_impossible_call_still_yields_a_real_deal() {
        let mut rng = Rng::new(99);
        let own = (1u64 << 36) - 1 & 0x1FF;        // nine cards
        let unseen = ((1u64 << 36) - 1) & !own;
        let counts = [0usize, 9, 9, 9];
        let mut ann = Announcements::none();
        for seat in 1..NUM_SEATS {
            ann.called[seat] = 999;                // no hand on earth calls this
        }
        for _ in 0..500 {
            let mut out = [0u64; NUM_SEATS];
            assert!(determinize_consistent(
                unseen, &counts, &[0u64; NUM_SEATS], &[[0i8; 4]; NUM_SEATS],
                &[0i8; NUM_SEATS], &ann, 0, own, &mut out, &mut rng,
            ));
            let mut union = 0u64;
            for seat in 0..NUM_SEATS {
                assert_eq!(out[seat].count_ones(), 9, "seat {seat} holds the wrong count");
                assert_eq!(union & out[seat], 0, "a card was dealt to two seats");
                union |= out[seat];
            }
            assert_eq!(union, (1u64 << 36) - 1, "the deck did not come out whole");
        }
    }

    #[test]
    fn silence_rules_out_a_hand_that_would_have_called() {
        let mut ann = Announcements::none();
        ann.called[2] = 0;
        let mut hands = [0u64; NUM_SEATS];
        hands[2] = (1u64 << 0) | (1u64 << 1) | (1u64 << 2);
        assert!(!ann.consistent(&hands));
        hands[2] = (1u64 << 0) | (1u64 << 1) | (1u64 << 3);
        assert!(ann.consistent(&hands));
    }
}
