//! Browser API. Lets a page drive a whole game with no server behind it.
//!
//! Plain `extern "C"` rather than wasm-bindgen: arguments are all small integers, and the
//! only thing coming back is a JSON view, which is written into a static buffer the page
//! reads directly out of `memory`. That keeps the toolchain to `cargo build` alone — no
//! bindgen, no npm, no generated glue to keep in sync.
//!
//! Games live in a registry keyed by handle. wasm is single-threaded, so a thread-local is
//! all the synchronisation there is to do.

use std::cell::RefCell;
use std::collections::HashMap;

use crate::announce::Announcements;
use crate::auction::Call;
use crate::sidi_estimate::{make_probability, Question};
use crate::sidi_read::Bid;
use crate::awareness::trick_taker;
use crate::cards::{card_list, card_suit, format_card, NUM_SEATS};
use crate::config::Rules;
use crate::convention;
use crate::game::{Game, Phase};
use crate::objective::Stakes;
use crate::bidding::infer_from_bid;
use crate::reading::infer_affinity;
use crate::rng::Rng;
use crate::rollout::Kernel;
use crate::search::{dmcts, Candidate, Position};
use crate::tables::{contract_name, CARD_VALUES};
use crate::trump::{select_trump, SHOVE};
use crate::voids::{infer_forbidden, infer_forbidden_per_trick};
use crate::coiffeur::{ROW_NAMES, ALL_ROWS};

thread_local! {
    static GAMES: RefCell<HashMap<u32, Game>> = RefCell::new(HashMap::new());
    static NEXT_HANDLE: RefCell<u32> = const { RefCell::new(1) };
    static BUFFER: RefCell<Vec<u8>> = const { RefCell::new(Vec::new()) };
}

fn publish(json: String) -> usize {
    BUFFER.with(|b| {
        let mut buf = b.borrow_mut();
        buf.clear();
        buf.extend_from_slice(json.as_bytes());
        buf.len()
    })
}

/// Pointer to the buffer the last call wrote. Valid until the next call that writes.
#[no_mangle]
pub extern "C" fn view_ptr() -> *const u8 {
    BUFFER.with(|b| b.borrow().as_ptr())
}

#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub extern "C" fn game_new(
    seed_lo: u32,
    seed_hi: u32,
    target_score: i32,
    weis_enabled: u32,
    weis_manual: u32,
    m0: i32, m1: i32, m2: i32, m3: i32, m4: i32, m5: i32,
    mode: u32,
    extra_rows: u32,
) -> u32 {
    // Sidi Barrani (mode 1) brings its own scoring — every contract x1, no Weis, no Stöck — so
    // the Schieber's multipliers and Weis switch from the settings do not apply to it. Nor to
    // the Coiffeur (mode 2), which ends with the sheet; `extra_rows` has bit i set for each of
    // `schedule::EXTRA_ROWS` played, as the server's form ticks them.
    let rules = if mode == 1 {
        Rules { target_score, weis_manual: weis_manual != 0, ..Rules::sidi() }
    } else if mode == 2 {
        Rules {
            coiffeur_extra_rows: std::array::from_fn(|i| extra_rows & (1 << i) != 0),
            ..Rules::coiffeur()
        }
    } else {
        Rules {
            target_score,
            weis_enabled: weis_enabled != 0,
            weis_manual: weis_manual != 0,
            multipliers: [m0, m1, m2, m3, m4, m5],
            ..Rules::default()
        }
    };
    let seed = ((seed_hi as u64) << 32) | seed_lo as u64;
    let handle = NEXT_HANDLE.with(|h| {
        let mut n = h.borrow_mut();
        let v = *n;
        *n += 1;
        v
    });
    GAMES.with(|g| g.borrow_mut().insert(handle, Game::new(rules, seed)));
    handle
}

#[no_mangle]
pub extern "C" fn game_free(handle: u32) {
    GAMES.with(|g| g.borrow_mut().remove(&handle));
}

/// 0 = ok, 1 = rejected. Rejection is normal — a stale click, or a client that got ahead.
#[no_mangle]
pub extern "C" fn game_bid(handle: u32, seat: u32, action: i32) -> u32 {
    GAMES.with(|g| {
        let mut games = g.borrow_mut();
        let Some(game) = games.get_mut(&handle) else { return 1 };
        let a = if action < 0 { SHOVE } else { action as usize };
        u32::from(game.bid(seat as usize, a).is_err())
    })
}

#[no_mangle]
pub extern "C" fn game_choose_weis(handle: u32, seat: u32, announce: u32) -> u32 {
    GAMES.with(|g| {
        let mut games = g.borrow_mut();
        let Some(game) = games.get_mut(&handle) else { return 1 };
        u32::from(game.choose_weis(seat as usize, announce != 0).is_err())
    })
}

#[no_mangle]
pub extern "C" fn game_play(handle: u32, seat: u32, card: u32) -> u32 {
    GAMES.with(|g| {
        let mut games = g.borrow_mut();
        let Some(game) = games.get_mut(&handle) else { return 1 };
        u32::from(game.play(seat as usize, card as usize).is_err())
    })
}

#[no_mangle]
pub extern "C" fn game_next_round(handle: u32) -> u32 {
    GAMES.with(|g| {
        let mut games = g.borrow_mut();
        let Some(game) = games.get_mut(&handle) else { return 1 };
        u32::from(game.next_round().is_err())
    })
}

// -- Coiffeur -----------------------------------------------------------------------------------
// A choice crosses as its index in `Game::legal_choices`, -1 for a shove; the view lists them by
// name in the same order, so the page maps one onto the other. A 3x3 block crosses as its contract.

/// Coiffeur: choose a row, or shove. 0 = ok, 1 = rejected.
#[no_mangle]
pub extern "C" fn game_choose(handle: u32, seat: u32, index: i32) -> u32 {
    GAMES.with(|g| {
        let mut games = g.borrow_mut();
        let Some(game) = games.get_mut(&handle) else { return 1 };
        let choice = if index < 0 {
            None
        } else {
            match game.legal_choices().0.get(index as usize) {
                Some(&c) => Some(c),
                None => return 1,
            }
        };
        u32::from(game.choose(seat as usize, choice).is_err())
    })
}

/// Coiffeur 3x3: name the next block. 0 = ok, 1 = rejected.
#[no_mangle]
pub extern "C" fn game_block(handle: u32, seat: u32, contract: u32) -> u32 {
    GAMES.with(|g| {
        let mut games = g.borrow_mut();
        let Some(game) = games.get_mut(&handle) else { return 1 };
        u32::from(game.choose_block(seat as usize, contract as usize).is_err())
    })
}

/// Coiffeur: the rule bot's row (`coiffeur_select.rs`), as for `game_choose`; -2 when there is
/// nothing to choose.
#[no_mangle]
pub extern "C" fn bot_choose(handle: u32, seat: u32) -> i32 {
    GAMES.with(|g| {
        let games = g.borrow();
        let Some(game) = games.get(&handle) else { return -2 };
        let (choices, can_shove) = game.legal_choices();
        if choices.is_empty() {
            return -2;
        }
        let hand = game.hand_of(seat as usize);
        match crate::coiffeur_select::choose(hand, &choices, can_shove, &game.row_multipliers) {
            None => -1,
            Some(c) => choices.iter().position(|&x| x == c).map_or(-2, |i| i as i32),
        }
    })
}

/// Coiffeur 3x3: the block the bot names; -1 when there is none to name.
#[no_mangle]
pub extern "C" fn bot_block(handle: u32, seat: u32) -> i32 {
    GAMES.with(|g| {
        let games = g.borrow();
        let Some(game) = games.get(&handle) else { return -1 };
        let options = game.legal_blocks();
        if options.is_empty() {
            return -1;
        }
        crate::coiffeur_select::choose_block(game.hand_of(seat as usize), &options) as i32
    })
}

// -- Sidi Barrani --------------------------------------------------------------------------
//
// A call crosses the boundary as one integer: -1 pass, -2 double, contract × 1000 + value.

fn call_code(call: Call) -> i32 {
    match call {
        Call::Pass => -1,
        Call::Double => -2,
        Call::Bid { contract, value } => contract as i32 * 1000 + value,
    }
}

fn call_from(code: i32) -> Option<Call> {
    match code {
        -1 => Some(Call::Pass),
        -2 => Some(Call::Double),
        c if c >= 0 => Some(Call::Bid { contract: (c / 1000) as usize, value: c % 1000 }),
        _ => None,
    }
}

/// The auction's bids, for reading into imagined hands (`sidi_read.rs`).
fn sidi_bids(game: &Game) -> Vec<Bid> {
    game.auction.as_ref().map_or(Vec::new(), |a| {
        a.calls
            .iter()
            .filter_map(|&(seat, c)| match c {
                Call::Bid { contract, value } => Some(Bid { seat, contract, value }),
                _ => None,
            })
            .collect()
    })
}

/// In step with `DmctsAgent` in `agent.py` (measurements.md §5v): the auction read at weight 1
/// (+32 points a hand), the hand played for a share of the cards rather than for the bid (playing
/// for the bid lost 5.1), and a double when the declarers make their bid in fewer than 35% of 400
/// imagined deals (`sidi_estimate.rs`; null against the stopper count, kept — and 0.25 rather than
/// a third, which cost 4.93 and 7.14 points a hand, §5v).
const SIDI_ALPHA: f32 = 1.0;
const SIDI_OBJECTIVE: bool = false;
const SIDI_DOUBLE_BELOW: f64 = 0.25;
const SIDI_DOUBLE_SAMPLES: usize = 1200;

fn declarers_make(
    game: &Game, seat: usize, hand: u64, history: &[(usize, usize)],
    contract: usize, declarer: usize, bid: i32,
) -> f64 {
    let bids = sidi_bids(game);
    let q = Question {
        seat, hand, history, leader: declarer, contract, declarer, bid,
        auction: &bids, alpha: SIDI_ALPHA,
    };
    // A seed from the game's own, the hand and the moment, so a replay doubles the same way.
    let mut rng = Rng::new(
        game.seed ^ (game.round_index as u64) << 40 ^ (seat as u64) << 32
            ^ (history.len() as u64) << 24 ^ bids.len() as u64,
    );
    make_probability(&q, SIDI_DOUBLE_SAMPLES, rng.next_u64()).0
}

/// Sidi: one call. 0 = ok, 1 = rejected.
#[no_mangle]
pub extern "C" fn game_call(handle: u32, seat: u32, code: i32) -> u32 {
    GAMES.with(|g| {
        let mut games = g.borrow_mut();
        let Some(game) = games.get_mut(&handle) else { return 1 };
        let Some(call) = call_from(code) else { return 1 };
        u32::from(game.call(seat as usize, call).is_err())
    })
}

/// Sidi: the answer to "double?" after the lead. 0 = ok, 1 = rejected.
#[no_mangle]
pub extern "C" fn game_double(handle: u32, seat: u32, double: u32) -> u32 {
    GAMES.with(|g| {
        let mut games = g.borrow_mut();
        let Some(game) = games.get_mut(&handle) else { return 1 };
        u32::from(game.double(seat as usize, double != 0).is_err())
    })
}

/// Sidi: a bot's call, encoded as for `game_call`. The language of `sidi_bidding.rs`, doubling
/// on the estimate rather than the stopper count.
#[no_mangle]
pub extern "C" fn bot_call(handle: u32, seat: u32) -> i32 {
    GAMES.with(|g| {
        let games = g.borrow();
        let Some(game) = games.get(&handle) else { return -1 };
        let Some(auction) = game.auction.as_ref() else { return -1 };
        let seat = seat as usize;
        let hand = game.hand_of(seat);
        let high = auction.high;
        let double = high
            .filter(|&(bidder, _, _)| (bidder + NUM_SEATS - seat) % 2 == 1 && !auction.doubled)
            .map(|(bidder, contract, value)| {
                declarers_make(game, seat, hand, &[], contract, bidder, value) < SIDI_DOUBLE_BELOW
            });
        call_code(crate::sidi_bidding::choose_call(hand, &auction.calls, seat, double))
    })
}

/// Sidi: does this bot knock on the standing bid, without waiting for its turn? 1 = double.
///
/// A double may come out of turn (`auction.rs`) and the page asks the player that way, so the
/// bots are asked the same: every opponent of the bidder, the moment the bid is made.
#[no_mangle]
pub extern "C" fn bot_knock(handle: u32, seat: u32) -> u32 {
    GAMES.with(|g| {
        let games = g.borrow();
        let Some(game) = games.get(&handle) else { return 0 };
        let Some(auction) = game.auction.as_ref() else { return 0 };
        let seat = seat as usize;
        let Some((bidder, contract, value)) = auction.high else { return 0 };
        if !auction.may_double(seat) {
            return 0;
        }
        let hand = game.hand_of(seat);
        u32::from(declarers_make(game, seat, hand, &[], contract, bidder, value) < SIDI_DOUBLE_BELOW)
    })
}

/// Sidi: a bot's answer to "double?" after the lead. 1 = double.
#[no_mangle]
pub extern "C" fn bot_double(handle: u32, seat: u32) -> u32 {
    GAMES.with(|g| {
        let games = g.borrow();
        let Some(game) = games.get(&handle) else { return 0 };
        let Some(round) = game.round.as_ref() else { return 0 };
        let Some(contract) = game.contract else { return 0 };
        let seat = seat as usize;
        let history: Vec<(usize, usize)> = round
            .trick
            .iter()
            .enumerate()
            .map(|(i, &c)| ((round.leader + i) & 3, c))
            .collect();
        let p = declarers_make(
            game, seat, round.hands[seat], &history, contract, game.declarer, game.bid_value,
        );
        u32::from(p < SIDI_DOUBLE_BELOW)
    })
}

/// A bot's bid. Returns the contract index, or -1 to shove.
#[no_mangle]
pub extern "C" fn bot_bid(handle: u32, seat: u32) -> i32 {
    GAMES.with(|g| {
        let games = g.borrow();
        let Some(game) = games.get(&handle) else { return 0 };
        let action = select_trump(
            game.hand_of(seat as usize),
            game.may_shove(seat as usize),
            &game.rules,
        );
        if action == SHOVE { -1 } else { action as i32 }
    })
}

/// What the search thinks of every legal move, best first.
///
/// `bot_play` and `bot_rank` are the same decision seen twice — one plays it, the other
/// shows it — so they share this rather than running two searches that could disagree.
/// `Forced` keeps "there is only one card" distinct from "the search picked one", because
/// recommending a card the player has no choice about is noise.
enum Thought {
    None,
    Forced(usize),
    Ranked(Vec<Candidate>, usize),
}

/// Everything the search needs about one seat's position, and the pool's per-seat card counts.
///
/// Shared by `think` (which plays it) and `belief_marginals` (which shows what it believes), so a
/// player looking at the test mode sees the search's own beliefs and not a second opinion.
fn position_for(game: &Game, seat: usize) -> Option<(Position, Kernel, [usize; NUM_SEATS])> {
let round = game.round.as_ref()?;
let contract = round.contract;
    let mut seen = 0u64;
    for (_, cards) in &round.tricks_played {
        for &c in cards {
            seen |= 1u64 << c;
        }
    }
    for &c in &round.trick {
        seen |= 1u64 << c;
    }
    let unseen = ((1u64 << 36) - 1) & !round.hands[seat] & !seen;

    // A Coiffeur schedule reads each trick under the trump it was played in; a 3x3 block not
    // named and a Tutti trick not led prove nothing (`infer_forbidden` in `voids.py`).
    let mut forbidden = match round.schedule {
        Some(s) => {
            let trumps = s.map(|c| if c < 4 { c as i32 } else { -1 });
            infer_forbidden_per_trick(&round.tricks_played, &round.trick, round.leader, &trumps, &game.rules)
        }
        None => infer_forbidden(&round.tricks_played, &round.trick, round.leader, round.trump, &game.rules),
    };

    // What the Weis stage published, which the browser bot was throwing away entirely.
    // `measurements.md` §5l measured the shown half at +0.62 of a round's card points
    // and it reached only the Python agent; §5m adds the called half. Both are read off
    // `weis_summary`, which is exactly what every player at the table saw and heard.
    let mut announcements = Announcements::none();
    if game.weis_calls_are_in() && game.rules.weis_enabled {
        let mut played = [0u64; NUM_SEATS];
        for (leader, cards) in &round.tricks_played {
            for (i, &c) in cards.iter().enumerate() {
                played[(leader + i) & 3] |= 1u64 << c;
            }
        }
        for (i, &c) in round.trick.iter().enumerate() {
            played[(round.leader + i) & 3] |= 1u64 << c;
        }
        // Silence is a claim too, and it is the common one — see announce.rs.
        announcements = Announcements {
            called: [0; NUM_SEATS],
            played,
            rules: game.rules,
            trump: round.trump,
            draws: crate::announce::MAX_DRAWS,
        };
        for entry in &game.weis_summary {
            announcements.called[entry.seat] = entry.points;
            // The winning Weis is turned face up to prove it. Nobody else can hold those
            // cards, which is the strongest claim there is about a specific hand.
            for &card in entry.cards.iter().flatten() {
                if seen & (1u64 << card) != 0 {
                    continue;
                }
                for other in 0..NUM_SEATS {
                    if other != entry.seat {
                        forbidden[other] |= 1u64 << card;
                    }
                }
            }
        }
        announcements.called[seat] = -1;
    }
    let kernel = Kernel::new(
        contract,
        game.rules.strict_undertrump,
        game.rules.puur_exempt,
        game.rules.last_trick_bonus,
        0,
    )
    .with_schedule(round.schedule)
    .mitte_at(contract, round.tricks_played.len() * NUM_SEATS + round.trick.len(), &round.trick);
    // What the discards suggest, alongside what they prove. Off, and the constant is
    // here rather than the code being deleted because the decision is a measurement —
    // `docs/measurements.md` §5c — and the next person to try it should re-run the match
    // rather than rebuild the machinery. Flipping this alone changes how the browser bot
    // plays, so it stays in step with the Python default in `agent.py`.
    const READ_SIGNALS: bool = false;
    // Beliefs from the other seats' plays and the bid. A measured decision like the one
    // above: +1.31 and +1.32 of a round's share on two seeds at 153,600 iterations
    // (measurements.md §5o). In step with `belief_alpha` / `bid_alpha` in `agent.py`.
    const BELIEFS: bool = true;
    let read = if READ_SIGNALS {
        infer_affinity(&round.tricks_played, &round.trick, round.leader, round.trump)
    } else {
        [[0i8; 4]; NUM_SEATS]
    };
    // The Schieber's bid model reads choose-or-shove; a Sidi auction is another language,
    // read by `sidi_read.rs` into the belief pool below instead.
    // Nor does a Coiffeur choice, which depends on the sheet as much as on the hand.
    let sidi = game.rules.sidi;
    let coiffeur = game.rules.coiffeur;
    let (bid_suits, bid_ranks) = if sidi || coiffeur {
        ([[0i8; 4]; NUM_SEATS], [0i8; NUM_SEATS])
    } else {
        infer_from_bid(game.forehand, game.declarer, contract, seat)
    };
    let mut affinity = read;
    for s in 0..NUM_SEATS {
        for suit in 0..4 {
            affinity[s][suit] = (affinity[s][suit] + bid_suits[s][suit]).clamp(-2, 2);
        }
    }
    let position = Position {
        seat,
        hand: round.hands[seat],
        unseen,
        trick: round.trick.clone(),
        trick_leader: round.leader,
        forbidden,
        affinity,
        // What the bidding said about the other hands — the loudest information in the
        // round, and until now the search ignored all of it. See krass_jass/bidding.py.
        rank_bias: bid_ranks,
        // Where this round leaves the game, which is what the search is playing for.
        // Weis is public once called; Stöck is not, and is left out. See objective.rs.
        // In the Sidi there is no game projection, as in `agent.py`; the bid objective is
        // behind SIDI_OBJECTIVE, off since it measured a loss.
        // The Coiffeur plays for the round's share, as `agent.py` does with no target; in a
        // Misère the choosing team must take a trick (`coiffeur_match_stroke`).
        stakes: if coiffeur {
            let misere = game.schedule.is_some_and(|s| s.misere());
            Stakes {
                scores: [game.scores[0], game.scores[1]],
                multiplier: 1,
                misere,
                misere_declarers: (misere && game.rules.coiffeur_match_stroke.is_some())
                    .then_some(game.declarer & 1),
                ..Default::default()
            }
        } else if sidi && !SIDI_OBJECTIVE {
            Stakes::default()
        } else if sidi {
            Stakes {
                sidi_bid: game.bid_value,
                sidi_declarers: game.declarer & 1,
                sidi_doubled: game.doubled,
                ..Default::default()
            }
        } else {
            Stakes {
                scores: [game.scores[0], game.scores[1]],
                bonus: [game.weis_points_public(0), game.weis_points_public(1)],
                target: game.rules.target_score,
                multiplier: game.rules.multiplier(contract),
                risk_lambda: 0.0,
                ..Default::default()
            }
        },
        adversarial: true,
        leaf_weights: Vec::new(),
        announcements,
        // Beliefs from behaviour — see belief.rs and measurements.md §5o. Weight each imagined
        // deal by how likely the other seats' plays and the bid were, holding it. Kept in step
        // with the Python defaults in `agent.py`.
        play: {
            let mut history = Vec::with_capacity(36);
            for (leader, cards) in &round.tricks_played {
                for (i, &c) in cards.iter().enumerate() {
                    history.push(((leader + i) & 3, c));
                }
            }
            for (i, &c) in round.trick.iter().enumerate() {
                history.push(((round.leader + i) & 3, c));
            }
            let mut info = crate::belief::PlayInfo::off();
            info.declarer = game.declarer;
            info.history = history;
            if BELIEFS {
                info.belief_alpha = 1.0;
                info.bid_alpha = if sidi || coiffeur { 0.0 } else { 1.0 };
                info.belief_pool = 4096;
            }
            if sidi {
                info.sidi_auction = sidi_bids(game);
                info.sidi_alpha = SIDI_ALPHA;
            }
            info
        },
    };

// Hand sizes are public — everyone at a table watches a fan shrink.
let mut counts = [0usize; NUM_SEATS];
for s in 0..NUM_SEATS {
    counts[s] = if s == seat { 0 } else { round.hands[s].count_ones() as usize };
}
Some((position, kernel, counts))
}

fn think(handle: u32, seat: u32, determinizations: u32, iterations: u32, seed: u32) -> Thought {
    GAMES.with(|g| {
        let games = g.borrow();
        let Some(game) = games.get(&handle) else { return Thought::None };
        let Some(round) = game.round.as_ref() else { return Thought::None };
        let seat = seat as usize;

        let legal = round.legal_moves(seat);
        if legal == 0 {
            return Thought::None;
        }
        if legal.count_ones() == 1 {
            return Thought::Forced(legal.trailing_zeros() as usize);
        }

        let contract = round.contract;
        let (position, kernel, counts) = match position_for(game, seat) {
            Some(p) => p,
            None => return Thought::None,
        };
        let _ = counts;
        let unseen = position.unseen;
        let seen = ((1u64 << 36) - 1) & !unseen & !round.hands[seat];
        // The browser plays the same search the measurements were taken with. ISMCTS above
        // the endgame threshold, the exact solve below it — see measurements.md §5h.
        // ISMCTS all the way to the last card. The exact endgame solver used to take over
        // at five each; `docs/measurements.md` §3e measured that costing **1.71** of a
        // round's share over 4,000 deals, at every budget tried. A double-dummy solve is
        // perfect information inside one imagined world, so a vote between several of them
        // is the strategy fusion §5h built the shared tree to avoid — the solver replaced
        // the one part of the design that handles hidden information with the one that
        // does not. It was written before ISMCTS existed and was never re-measured after.
        let total = (determinizations * iterations) as usize;
        let out = crate::ismcts::ismcts(
            &position, &kernel, total, 1.5, seed as u64 | 1, 4, false, 0.0, &[],
            &[0u64; NUM_SEATS], 0.0,
        );
        let _ = dmcts;   // still reachable from the Python bridge, where the flag lives
        // The search has spoken; this only orders the moves it rated the same. See
        // krass_jass/convention.py for why that restriction is the whole design.
        // A Coiffeur schedule changes the card order trick by trick; the conventions read this
        // trick's, as in `agent.py`.
        let (trump, contract) = if round.schedule.is_some() {
            let c = round.trick_contract();
            (if c < 4 { c as i32 } else { -1 }, c)
        } else {
            (round.trump, contract)
        };
        let pick = convention::choose(
            &out,
            round.hands[seat],
            unseen,
            seen | round.hands[seat],
            &round.trick,
            seat,
            trump,
            contract,
            &position.forbidden,
            (game.declarer & 1) == (seat & 1),
            convention::DEFAULT_SLACK,
            convention::partner_discards(&round.tricks_played, &round.trick, round.leader, seat, trump),
        );
        match pick {
            Some(card) => Thought::Ranked(out, card),
            None => Thought::None,
        }
    })
}

/// A bot's card, by DMCTS with void-consistent determinization. Returns a card index.
#[no_mangle]
pub extern "C" fn bot_play(handle: u32, seat: u32, determinizations: u32, iterations: u32, seed: u32) -> i32 {
    match think(handle, seat, determinizations, iterations, seed) {
        Thought::None => -1,
        Thought::Forced(card) => card as i32,
        Thought::Ranked(_, card) => card as i32,
    }
}

/// The same decision, published instead of played — the advice mode in the app.
///
/// Returns the JSON length, with the payload in the shared view buffer: an array of
/// `{card, visits, share}` best first, plus `forced` when the player has no choice.
///
/// It runs a **fourth bot on the human's own seat**, so it is subject to exactly the limits
/// the other three are: it cannot see anyone's hand, and it is guessing like they are. What
/// it is not is an oracle, and the app says so rather than implying the top card is right.
#[no_mangle]
pub extern "C" fn bot_rank(handle: u32, seat: u32, determinizations: u32, iterations: u32, seed: u32) -> usize {
    let json = match think(handle, seat, determinizations, iterations, seed) {
        Thought::None => "{\"moves\":[]}".to_string(),
        Thought::Forced(card) => {
            format!("{{\"forced\":\"{}\",\"moves\":[]}}", format_card(card))
        }
        Thought::Ranked(out, pick) => {
            // Visits, normalised over the candidates — the same quantity the Nerd-Doc's
            // "share of visits" figure shows, so the number in the app and the number in
            // the documentation mean the same thing.
            let total: u64 = out.iter().map(|c| c.visits).sum::<u64>().max(1);
            // The convention layer may re-order moves the search rated equal, so the card
            // it actually plays leads the list even when another has a visit or two more.
            let mut rows: Vec<&Candidate> = out.iter().collect();
            rows.sort_by_key(|c| (if c.card == pick { 0 } else { 1 }, u64::MAX - c.visits));
            let parts: Vec<String> = rows
                .iter()
                .take(3)
                .map(|c| {
                    format!(
                        "{{\"card\":\"{}\",\"visits\":{},\"share\":{:.4}}}",
                        format_card(c.card), c.visits, c.visits as f64 / total as f64
                    )
                })
                .collect();
            format!("{{\"moves\":[{}]}}", parts.join(","))
        }
    };
    publish(json)
}

fn cards_json(cards: &[usize]) -> String {
    let parts: Vec<String> = cards.iter().map(|&c| format!("\"{}\"", format_card(c))).collect();
    format!("[{}]", parts.join(","))
}

/// Test mode: what a bot on `seat` believes about the other three hands, as JSON.
///
/// `{"ess": n, "cards": [{"card": "HA", "seats": [p_next, p_partner, p_previous]}]}` — the search's
/// own belief pool (`belief.rs`), summarised rather than sampled. Built from this seat's hand and
/// the public history only, so it shows what the bot reasons from without revealing a card.
#[no_mangle]
pub extern "C" fn belief_marginals(handle: u32, seat: u32) -> usize {
    GAMES.with(|g| {
        let games = g.borrow();
        let Some(game) = games.get(&handle) else { return publish("null".into()) };
        let seat = seat as usize;
        let Some(position) = position_for(game, seat) else { return publish("null".into()) };
        let (position, kernel, counts) = position;
        let mut rng = Rng::new(game.seed ^ ((game.round_index as u64) << 32) ^ seat as u64 | 1);
        let Some(pool) = crate::belief::Pool::build(&position, &kernel, &counts, &mut rng) else {
            return publish("null".into());
        };
        let m = pool.marginals();
        let mut parts: Vec<String> = Vec::new();
        let mut rest = position.unseen;
        while rest != 0 {
            let card = rest.trailing_zeros() as usize;
            rest &= rest - 1;
            parts.push(format!(
                "{{\"card\":\"{}\",\"seats\":[{:.4},{:.4},{:.4}]}}",
                format_card(card),
                m[(seat + 1) & 3][card],
                m[(seat + 2) & 3][card],
                m[(seat + 3) & 3][card],
            ));
        }
        publish(format!("{{\"ess\":{:.1},\"cards\":[{}]}}", pool.ess, parts.join(",")))
    })
}

/// Everything one seat may see, as JSON. `acked_tricks` is how many completed tricks the
/// player has cleared, so a finished trick can stay on the table until tapped.
///
/// This mirrors `web/app.py::view` deliberately: the page renders the same shape whether the
/// state came from a server or from here.
#[no_mangle]
pub extern "C" fn game_view(handle: u32, seat: u32, acked_tricks: u32) -> usize {
    GAMES.with(|g| {
        let games = g.borrow();
        let Some(game) = games.get(&handle) else { return publish("{}".into()) };
        let seat = seat as usize;
        let mut out = String::with_capacity(1024);

        let played = game.round.as_ref().map_or(0, |r| r.tricks_played.len());
        let awaiting = played > acked_tricks as usize;

        out.push_str(&format!(
            "{{\"phase\":\"{}\",\"seat\":{seat},\"round\":{},\"target\":{}",
            game.phase.as_str(),
            game.round_index,
            game.rules.target_score
        ));
        match game.to_act() {
            Some(s) => out.push_str(&format!(",\"to_act\":{s}")),
            None => out.push_str(",\"to_act\":null"),
        }
        out.push_str(&format!(",\"hand\":{}", cards_json(&sorted_hand(game.hand_of(seat)))));

        // No legal moves are offered while a finished trick is still on the table.
        let legal = match (&game.round, game.phase) {
            (Some(r), Phase::Playing) if r.to_play() == seat && !awaiting => r.legal_moves(seat),
            _ => 0,
        };
        out.push_str(&format!(",\"legal\":{}", cards_json(&card_list(legal))));

        // Current trick, or the finished one still being shown.
        let mut trick = String::from("[");
        let mut winner = String::from("null");
        let mut shown: Vec<usize> = Vec::new();
        let mut shown_leader = 0usize;
        if let Some(round) = &game.round {
            let (leader, cards) = if awaiting {
                let (l, c) = round.tricks_played.last().unwrap();
                winner = round.last_trick_winner.to_string();
                (*l, c.clone())
            } else {
                (round.leader, round.trick.clone())
            };
            shown = cards.clone();
            shown_leader = leader;
            let parts: Vec<String> = cards
                .iter()
                .enumerate()
                .map(|(i, &c)| {
                    format!(
                        "{{\"seat\":{},\"card\":\"{}\"}}",
                        (leader + i) % NUM_SEATS,
                        format_card(c)
                    )
                })
                .collect();
            trick.push_str(&parts.join(","));
        }
        trick.push(']');
        out.push_str(&format!(
            ",\"trick\":{trick},\"trick_complete\":{},\"trick_winner\":{winner}",
            awaiting
        ));

        // The contract the trick on the table is played in. One per round, except in the
        // Coiffeur's extra rows, where it changes trick by trick; `None` for a 3x3 block not
        // named or a Tutti trick not led. As `playing` in `web/app.py::view`.
        let playing = match game.round.as_ref().and_then(|r| r.schedule) {
            Some(s) => Some(s[played.saturating_sub(usize::from(awaiting)).min(8)])
                .filter(|&c| c < crate::tables::NUM_ORDERS),
            None => game.contract,
        };
        // Which way the cards on the table are going, and what the other three still hold in
        // trump. Public both ways — see krass_jass/awareness.py and its Rust mirror.
        match game.round.as_ref().zip(playing).and_then(|(_, c)| trick_taker(&shown, shown_leader, c)) {
            Some(s) => out.push_str(&format!(",\"trick_taker\":{s}")),
            None => out.push_str(",\"trick_taker\":null"),
        }


        match game.contract {
            Some(c) => out.push_str(&format!(
                ",\"contract\":{},\"multiplier\":{}",
                playing.map_or("null".to_string(), |p| format!("\"{}\"", contract_name(p))),
                match game.row {
                    Some(row) if game.rules.coiffeur => game.row_multipliers[row],
                    _ => game.rules.multiplier(c),
                }
            )),
            None => out.push_str(",\"contract\":null,\"multiplier\":null"),
        }
        // How many cards each seat still holds. Public — everyone at a real table can see a
        // fan shrink — and the only thing the covered cards in the UI need. Deliberately a
        // count and never a hand: `krass_jass/observation.py` is the boundary this mirrors.
        if let Some(round) = game.round.as_ref() {
            let counts: Vec<String> = (0..NUM_SEATS)
                .map(|s| round.hands[s].count_ones().to_string())
                .collect();
            out.push_str(&format!(",\"hand_sizes\":[{}]", counts.join(",")));
        } else {
            out.push_str(",\"hand_sizes\":null");
        }
        out.push_str(&format!(",\"declarer\":{}", game.declarer));
        out.push_str(&format!(",\"scores\":[{},{}]", game.scores[0], game.scores[1]));
        let sidi = game.rules.sidi;
        out.push_str(&format!(
            ",\"can_shove\":{}",
            !sidi && !game.rules.coiffeur && game.may_shove(seat)
        ));
        // The first round's Müessi, as `web/app.py::view`.
        out.push_str(&format!(",\"muessi\":{}", game.phase == Phase::Bidding && game.muss()));
        // Sidi Barrani, in the shape `web/app.py::view` sends: the auction (public — every
        // call was said aloud), the calls this seat may make, the bid and the double.
        let mode = if sidi { "sidi" } else if game.rules.coiffeur { "coiffeur" } else { "schieber" };
        out.push_str(&format!(",\"mode\":\"{mode}\""));
        out.push_str(",\"coiffeur\":");
        out.push_str(&coiffeur_json(game, seat, played, awaiting));
        let calls: Vec<String> = game.auction.as_ref().map_or(Vec::new(), |a| {
            a.calls
                .iter()
                .map(|(s, c)| format!("{{\"seat\":{s},\"call\":\"{}\"}}", c.name()))
                .collect()
        });
        out.push_str(&format!(",\"auction\":[{}]", calls.join(",")));
        let legal_calls: Vec<String> = match &game.auction {
            Some(a) if game.phase == Phase::Bidding && game.to_act() == Some(seat) => a
                .legal_calls(seat)
                .iter()
                .map(|c| format!("\"{}\"", c.name()))
                .collect(),
            _ => Vec::new(),
        };
        out.push_str(&format!(",\"legal_calls\":[{}]", legal_calls.join(",")));
        if game.bid_value > 0 {
            out.push_str(&format!(",\"bid\":{}", game.bid_value));
        } else {
            out.push_str(",\"bid\":null");
        }
        out.push_str(&format!(
            ",\"doubled\":{},\"double_pending\":{}",
            game.doubled,
            game.phase == Phase::Doubling && game.to_act() == Some(seat)
        ));
        let won = game.round.as_ref().map(|r| r.tricks_won).unwrap_or([0, 0]);
        out.push_str(&format!(",\"tricks_won\":[{},{}]", won[0], won[1]));

        // The trump Jack, so the page does not have to work out what trump means.
        match playing {
            Some(c) if c < 4 => {
                out.push_str(&format!(",\"puur\":\"{}\"", format_card(c * 9 + 3)))
            }
            _ => out.push_str(",\"puur\":null"),
        }

        // Weis: called in turn order through the first trick, then the best one is shown.
        out.push_str(",\"weis\":");
        out.push_str(&weis_json(game, awaiting, played));
        out.push_str(",\"stoeck\":");
        out.push_str(&stoeck_json(game, awaiting, played));

        let offer = if game.phase == Phase::Weis { game.weis_offers[seat] } else { 0 };
        out.push_str(&format!(
            ",\"weis_offer\":{},\"weis_pending\":{}",
            if offer > 0 { offer.to_string() } else { "null".into() },
            game.phase == Phase::Weis
        ));

        // Not until the last trick has been acknowledged — it stays on the table like any
        // other, and the scorecard waits for the tap.
        out.push_str(",\"scorecard\":");
        if sidi {
            match (game.last_sidi, game.phase) {
                (Some(d), Phase::RoundOver | Phase::GameOver) if !awaiting => out.push_str(&format!(
                    "{{\"round\":{},\"contract\":\"{}\",\"trick_points\":[{},{}],\
                     \"last_trick\":[{},{}],\"match\":[{},{}],\"bid\":{},\"doubled\":{},\
                     \"made\":{},\"bonus\":[{},{}],\"round_total\":[{},{}],\"scores\":[{},{}]}}",
                    game.round_index,
                    game.contract.map(contract_name).unwrap_or(""),
                    d.trick_points[0], d.trick_points[1],
                    d.last_trick[0], d.last_trick[1],
                    d.match_bonus[0], d.match_bonus[1],
                    d.bid, d.doubled, d.made,
                    d.bonus[0], d.bonus[1],
                    d.round_total[0], d.round_total[1],
                    d.scores[0], d.scores[1],
                )),
                _ => out.push_str("null"),
            }
            out.push('}');
            return publish(out);
        }
        if game.rules.coiffeur {
            match (game.last_coiffeur, game.phase) {
                (Some(d), Phase::RoundOver | Phase::GameOver) if !awaiting => out.push_str(&format!(
                    "{{\"contract\":\"{}\",\"round\":{},\"trick_points\":[{},{}],\"last_trick\":[{},{}],\
                     \"match\":[{},{}],\"team\":{},\"row\":\"{}\",\"multiplier\":{},\
                     \"round_total\":[{},{}],\"strokes\":[{},{}],\"written\":[{},{}],\"scores\":[{},{}]}}",
                    game.contract.map(contract_name).unwrap_or(""),
                    game.round_index,
                    d.trick_points[0], d.trick_points[1],
                    d.last_trick[0], d.last_trick[1],
                    d.match_bonus[0], d.match_bonus[1],
                    d.team, ROW_NAMES[d.row], d.multiplier,
                    d.round_total[0], d.round_total[1],
                    d.strokes[0], d.strokes[1],
                    d.written[0], d.written[1],
                    d.scores[0], d.scores[1],
                )),
                _ => out.push_str("null"),
            }
            out.push('}');
            return publish(out);
        }
        match (game.last_score, game.phase) {
            (Some(d), Phase::RoundOver | Phase::GameOver) if !awaiting => out.push_str(&format!(
                "{{\"round\":{},\"contract\":\"{}\",\"multiplier\":{},\"trick_points\":[{},{}],\
                 \"last_trick\":[{},{}],\"match\":[{},{}],\"weis\":[{},{}],\"stoeck\":[{},{}],\
                 \"round_total\":[{},{}],\"scores\":[{},{}]}}",
                game.round_index,
                game.contract.map(contract_name).unwrap_or(""),
                d.multiplier,
                d.trick_points[0], d.trick_points[1],
                d.last_trick[0], d.last_trick[1],
                d.match_bonus[0], d.match_bonus[1],
                d.weis[0], d.weis[1],
                d.stoeck[0], d.stoeck[1],
                d.round_total[0], d.round_total[1],
                d.scores[0], d.scores[1],
            )),
            _ => out.push_str("null"),
        }
        out.push('}');
        publish(out)
    })
}

/// The Coiffeur sheet and what the seat may choose, in the shape `coiffeur_view` in `web/app.py`
/// sends; `null` in the other games. The sheet is public, and the choices are the engine's.
fn coiffeur_json(game: &Game, seat: usize, played: usize, awaiting: bool) -> String {
    if !game.rules.coiffeur {
        return "null".into();
    }
    let choosing = game.phase == Phase::Bidding;
    let rows: Vec<usize> = (0..ALL_ROWS).filter(|&r| game.sheet.rows[r]).collect();
    let quoted = |s: &str| format!("\"{s}\"");
    let list = |items: Vec<String>| format!("[{}]", items.join(","));
    let slot = |c: usize| if c < crate::tables::NUM_ORDERS { quoted(contract_name(c)) } else { "null".into() };
    let column = |team: usize| {
        list(rows.iter().map(|&r| game.sheet.written[team][r].map_or("null".into(), |v| v.to_string())).collect())
    };
    let schedule = match game.schedule {
        Some(s) if !choosing => {
            let tricks = game.round.as_ref().and_then(|r| r.schedule).unwrap_or(s.tricks());
            let at = if game.round.is_some() { played - usize::from(awaiting) } else { 0 };
            format!(
                "{{\"name\":\"{}\",\"tricks\":{},\"misere\":{},\"at\":{at}}}",
                s.name(),
                list(tricks.iter().map(|&c| slot(c)).collect()),
                s.misere()
            )
        }
        _ => "null".into(),
    };
    let legal = if choosing && game.to_act() == Some(seat) {
        let (choices, can_shove) = game.legal_choices();
        let mut names: Vec<String> = choices.iter().map(|c| quoted(&c.name())).collect();
        if can_shove {
            names.push(quoted("SHOVE"));
        }
        names
    } else {
        Vec::new()
    };
    let blocks = if game.to_act() == Some(seat) {
        game.legal_blocks().into_iter().map(|c| quoted(contract_name(c))).collect()
    } else {
        Vec::new()
    };
    format!(
        "{{\"rows\":{},\"multipliers\":{},\"sheet\":[{},{}],\"row\":{},\"schedule\":{schedule},\
         \"legal\":{},\"shoves\":{},\"blocks\":{},\"tens\":{},\"strokes\":[{},{}],\"stroke\":{}}}",
        list(rows.iter().map(|&r| quoted(ROW_NAMES[r])).collect()),
        list(rows.iter().map(|&r| game.row_multipliers[r].to_string()).collect()),
        column(0),
        column(1),
        match game.row {
            Some(r) if !choosing => quoted(ROW_NAMES[r]),
            _ => "null".into(),
        },
        list(legal),
        if choosing { game.shoves } else { 0 },
        list(blocks),
        game.rules.coiffeur_tens,
        game.sheet.strokes[0],
        game.sheet.strokes[1],
        game.rules.coiffeur_match_stroke.map_or("null".into(), |v| v.to_string()),
    )
}

/// Kreuz, Ecken, Schaufel, Herz, left to right, so black and red alternate. Indexed by suit
/// (D H S C). Mirror of `HAND_SUIT_ORDER` in `web/app.py`.
const HAND_SUIT_ORDER: [u8; 4] = [1, 3, 2, 0];

fn sorted_hand(hand: u64) -> Vec<usize> {
    // Grouped by suit, ascending in rank left to right — the internal index runs ace-first,
    // which is right for the engine and backwards for a player looking at their cards.
    let mut cards = card_list(hand);
    cards.sort_by_key(|&c| (HAND_SUIT_ORDER[card_suit(c)], std::cmp::Reverse(c % 9)));
    cards
}

fn weis_json(game: &Game, awaiting: bool, played: usize) -> String {
    // The engine publishes for the whole round; the client decides how long to *show* it.
    // It used to close the moment the first trick was tapped away, so the winning Weis was
    // only ever on screen during the pause nobody waits through — which read as it never
    // appearing at all.
    let in_window = true;
    let _ = awaiting;
    if !in_window || game.round.is_none() {
        return "[]".into();
    }
    let round = game.round.as_ref().unwrap();
    let entries: Vec<String> = game
        .weis_summary
        .iter()
        .filter(|e| {
            if played > 0 {
                return true; // all calls are in
            }
            // Mid-first-trick: only the seats that have already played have spoken.
            (0..round.trick.len()).any(|i| (round.leader + i) % NUM_SEATS == e.seat)
        })
        .map(|e| {
            let cards = match (&e.cards, played > 0) {
                (Some(c), true) => cards_json(c), // shown only once the calls are in
                _ => "null".into(),
            };
            format!(
                "{{\"seat\":{},\"points\":{},\"cards\":{cards},\"winner\":{},\"best\":{}}}",
                e.seat, e.points, e.winner, e.best
            )
        })
        .collect();
    format!("[{}]", entries.join(","))
}

fn stoeck_json(game: &Game, awaiting: bool, played: usize) -> String {
    let current = if awaiting { played.saturating_sub(1) } else { played };
    let entries: Vec<String> = game
        .stoeck_announced
        .iter()
        .filter(|(_, _, trick)| *trick == current)
        .map(|(seat, points, _)| format!("{{\"seat\":{seat},\"points\":{points}}}"))
        .collect();
    format!("[{}]", entries.join(","))
}

/// Deterministic per-decision seed for a bot, derived from the game seed. Keeps replay
/// meaningful without the page having to know the seed.
#[no_mangle]
pub extern "C" fn decision_seed(handle: u32, seat: u32, trick: u32) -> u32 {
    GAMES.with(|g| {
        let games = g.borrow();
        let Some(game) = games.get(&handle) else { return 1 };
        let mut rng = Rng::split(game.seed, ((seat as u64) << 32) | trick as u64);
        (rng.next_u64() & 0xFFFF_FFFF) as u32
    })
}

/// Card point values for the current contract, so the page can show running totals without
/// duplicating the value tables.
#[no_mangle]
pub extern "C" fn card_value(handle: u32, card: u32) -> i32 {
    GAMES.with(|g| {
        let games = g.borrow();
        games
            .get(&handle)
            .and_then(|game| game.contract)
            .map(|c| CARD_VALUES[c][card as usize])
            .unwrap_or(0)
    })
}
