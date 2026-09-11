//! Benchmark surface for wasm32.
//!
//! Plain `extern "C"` exports rather than wasm-bindgen: the numbers going in and out are
//! integers, so no marshalling is needed and no JS glue has to be generated. That keeps the
//! measurement about the engine rather than about the binding layer.
//!
//! Deals are generated *inside* wasm from a seed, so the timing loop never crosses the
//! boundary — a per-call JS round trip would dominate a 2μs rollout and measure the wrong
//! thing entirely.

use crate::cards::NUM_SEATS;
use crate::rng::Rng;
use crate::rollout::{play_out, Kernel};
use crate::search::{dmcts, Position};

fn deal(rng: &mut Rng) -> [u64; NUM_SEATS] {
    let mut deck: [u8; 36] = core::array::from_fn(|i| i as u8);
    // Fisher-Yates
    for i in (1..36).rev() {
        let j = rng.below(i as u32 + 1) as usize;
        deck.swap(i, j);
    }
    let mut hands = [0u64; NUM_SEATS];
    for (i, &card) in deck.iter().enumerate() {
        hands[i / 9] |= 1u64 << card;
    }
    hands
}

/// `n` full random playouts. Returns an accumulator so nothing is optimised away.
#[no_mangle]
pub extern "C" fn bench_rollouts(n: u32, seed: u32) -> u32 {
    let kernel = Kernel::new(1, true, true, 5, 0);
    let mut rng = Rng::new(seed as u64 | 1);
    let mut acc: u32 = 0;
    for _ in 0..n {
        let mut hands = deal(&mut rng);
        let (a, _) = play_out(&mut hands, 0, &kernel, &mut rng);
        acc = acc.wrapping_add(a as u32);
    }
    acc
}

/// One DMCTS search at the given budget, from a fresh deal. Returns the winning card index.
#[no_mangle]
pub extern "C" fn bench_dmcts(determinizations: u32, iterations: u32, seed: u32) -> u32 {
    let kernel = Kernel::new(1, true, true, 5, 0);
    let mut rng = Rng::new(seed as u64 | 1);
    let hands = deal(&mut rng);

    let position = Position {
        seat: 0,
        hand: hands[0],
        unseen: hands[1] | hands[2] | hands[3],
        trick: Vec::new(),
        trick_leader: 0,
        forbidden: [0; NUM_SEATS],
            affinity: [[0i8; 4]; NUM_SEATS],
        rank_bias: [0i8; NUM_SEATS],
        stakes: Default::default(),
        adversarial: true,
    };
    let out = dmcts(
        &position,
        &kernel,
        determinizations as usize,
        iterations as usize,
        1.5,
        seed as u64 | 1,
        1,
        0, // endgame solver off, so this measures the search rather than alpha-beta
    );
    out.first().map(|c| c.card as u32).unwrap_or(u32::MAX)
}

/// Play a whole game through the phase machine. Exists so the linker keeps the engine, and
/// so the wasm bundle size reflects what a browser build would actually carry.
#[no_mangle]
pub extern "C" fn bench_game(seed: u32) -> u32 {
    use crate::config::Rules;
    use crate::game::{Game, Phase};
    use crate::trump::select_trump;

    let rules = Rules { target_score: 1000, ..Rules::default() };
    let mut game = Game::new(rules, seed as u64 | 1);
    let mut rng = Rng::new(seed as u64 | 1);

    for _ in 0..20000 {
        match game.phase {
            Phase::GameOver => break,
            Phase::RoundOver => {
                let _ = game.next_round();
            }
            Phase::Bidding => {
                let seat = game.to_act().unwrap();
                let action = select_trump(game.hand_of(seat), seat == game.forehand, &rules);
                let _ = game.bid(seat, action);
            }
            Phase::Weis => {
                let seat = game.to_act().unwrap();
                let _ = game.choose_weis(seat, true);
            }
            Phase::Playing => {
                let seat = game.to_act().unwrap();
                let legal = game.round.as_ref().unwrap().legal_moves(seat);
                let card = crate::rollout::pick_random(legal, &mut rng);
                let _ = game.play(seat, card);
            }
        }
    }
    (game.scores[0] + game.scores[1]) as u32
}

/// Exact endgame solve on a `cards_each`-card position. Returns nodes visited.
#[no_mangle]
pub extern "C" fn bench_endgame(cards_each: u32, seed: u32) -> u32 {
    use crate::endgame::solve_exact;

    let kernel = Kernel::new(1, true, true, 5, 0);
    let mut rng = Rng::new(seed as u64 | 1);
    let full = deal(&mut rng);
    let keep = cards_each.min(9) as usize;

    let mut hands = [0u64; NUM_SEATS];
    for seat in 0..NUM_SEATS {
        let mut m = full[seat];
        let mut kept = 0u64;
        for _ in 0..keep {
            if m == 0 {
                break;
            }
            let low = m & m.wrapping_neg();
            kept |= low;
            m ^= low;
        }
        hands[seat] = kept;
    }
    let (_, nodes) = solve_exact(&mut hands, &[], 0, &kernel);
    nodes as u32
}
