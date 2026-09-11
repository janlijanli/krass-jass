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
use crate::search::{dmcts, Position};
use crate::tables::{contract_name, CARD_VALUES};
use crate::trump::{select_trump, SHOVE};
use crate::voids::infer_forbidden;

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
) -> u32 {
    let rules = Rules {
        target_score,
        weis_enabled: weis_enabled != 0,
        weis_manual: weis_manual != 0,
        multipliers: [m0, m1, m2, m3, m4, m5],
        ..Rules::default()
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

/// A bot's bid. Returns the contract index, or -1 to shove.
#[no_mangle]
pub extern "C" fn bot_bid(handle: u32, seat: u32) -> i32 {
    GAMES.with(|g| {
        let games = g.borrow();
        let Some(game) = games.get(&handle) else { return 0 };
        let action = select_trump(
            game.hand_of(seat as usize),
            seat as usize == game.forehand,
            &game.rules,
        );
        if action == SHOVE { -1 } else { action as i32 }
    })
}

/// A bot's card, by DMCTS with void-consistent determinization. Returns a card index.
#[no_mangle]
pub extern "C" fn bot_play(handle: u32, seat: u32, determinizations: u32, iterations: u32, seed: u32) -> i32 {
    GAMES.with(|g| {
        let games = g.borrow();
        let Some(game) = games.get(&handle) else { return -1 };
        let Some(round) = game.round.as_ref() else { return -1 };
        let seat = seat as usize;

        let legal = round.legal_moves(seat);
        if legal == 0 {
            return -1;
        }
        if legal.count_ones() == 1 {
            return legal.trailing_zeros() as i32; // no decision to make
        }

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

        let forbidden = infer_forbidden(
            &round.tricks_played,
            &round.trick,
            round.leader,
            round.trump,
            &game.rules,
        );
        let kernel = Kernel::new(
            contract,
            game.rules.strict_undertrump,
            game.rules.puur_exempt,
            game.rules.last_trick_bonus,
            0,
        );
        // What the discards suggest, alongside what they prove. Off, and the constant is
        // here rather than the code being deleted because the decision is a measurement —
        // `docs/measurements.md` §5c — and the next person to try it should re-run the match
        // rather than rebuild the machinery. Flipping this alone changes how the browser bot
        // plays, so it stays in step with the Python default in `agent.py`.
        const READ_SIGNALS: bool = false;
        let read = if READ_SIGNALS {
            infer_affinity(&round.tricks_played, &round.trick, round.leader, round.trump)
        } else {
            [[0i8; 4]; NUM_SEATS]
        };
        let (bid_suits, bid_ranks) =
            infer_from_bid(game.forehand, game.declarer, contract, seat);
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
            stakes: Stakes {
                scores: [game.scores[0], game.scores[1]],
                bonus: [game.weis_points_public(0), game.weis_points_public(1)],
                target: game.rules.target_score,
                multiplier: game.rules.multiplier(contract),
                risk_lambda: 0.0,
            },
            adversarial: true,
            leaf_weights: Vec::new(),
        };
        let out = dmcts(
            &position,
            &kernel,
            determinizations as usize,
            iterations as usize,
            1.5,
            seed as u64 | 1,
            1,
            5,
        );
        // The search has spoken; this only orders the moves it rated the same. See
        // krass_jass/convention.py for why that restriction is the whole design.
        convention::choose(
            &out,
            round.hands[seat],
            unseen,
            seen | round.hands[seat],
            &round.trick,
            seat,
            round.trump,
            contract,
            &position.forbidden,
        )
        .map(|c| c as i32)
        .unwrap_or(-1)
    })
}

fn cards_json(cards: &[usize]) -> String {
    let parts: Vec<String> = cards.iter().map(|&c| format!("\"{}\"", format_card(c))).collect();
    format!("[{}]", parts.join(","))
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

        // Which way the cards on the table are going, and what the other three still hold in
        // trump. Public both ways — see krass_jass/awareness.py and its Rust mirror.
        let contract = game.contract.unwrap_or(0);
        match game.round.as_ref().and_then(|_| trick_taker(&shown, shown_leader, contract)) {
            Some(s) => out.push_str(&format!(",\"trick_taker\":{s}")),
            None => out.push_str(",\"trick_taker\":null"),
        }


        match game.contract {
            Some(c) => out.push_str(&format!(
                ",\"contract\":\"{}\",\"multiplier\":{}",
                contract_name(c),
                game.rules.multiplier(c)
            )),
            None => out.push_str(",\"contract\":null,\"multiplier\":null"),
        }
        out.push_str(&format!(",\"declarer\":{}", game.declarer));
        out.push_str(&format!(",\"scores\":[{},{}]", game.scores[0], game.scores[1]));
        out.push_str(&format!(
            ",\"can_shove\":{}",
            game.phase == Phase::Bidding && seat == game.forehand && !game.shoved
        ));
        let won = game.round.as_ref().map(|r| r.tricks_won).unwrap_or([0, 0]);
        out.push_str(&format!(",\"tricks_won\":[{},{}]", won[0], won[1]));

        // The trump Jack, so the page does not have to work out what trump means.
        match game.contract {
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

fn sorted_hand(hand: u64) -> Vec<usize> {
    // Grouped by suit, ascending in rank left to right — the internal index runs ace-first,
    // which is right for the engine and backwards for a player looking at their cards.
    let mut cards = card_list(hand);
    cards.sort_by_key(|&c| (card_suit(c), std::cmp::Reverse(c % 9)));
    cards
}

fn weis_json(game: &Game, awaiting: bool, played: usize) -> String {
    let in_window = played == 0 || (played == 1 && awaiting);
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
