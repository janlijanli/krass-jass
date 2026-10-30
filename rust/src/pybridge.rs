//! PyO3 exports for the ported rules, so each one can be checked against the Python it
//! replaces.
//!
//! This is the whole safety argument for the port, and it is the same one that made the
//! search port safe: `tests/reference.py` was written from the rules text and imports
//! neither implementation, so the Python side is itself independently checked. Agreement
//! across all three is what says the port is right.

use pyo3::prelude::*;

use crate::awareness::trick_taker;
use crate::bidding::infer_from_bid;
use crate::convention;
use crate::leafeval::{features, N_FEATURES};
use crate::policy::{card_features, N_POLICY_FEATURES};
use crate::rollout::{pick_random, Kernel};
use crate::round::Round;
use crate::determinize::determinize;
use crate::objective::{reward, Stakes};
use crate::reading::infer_affinity;
use crate::rng::Rng;
use crate::search::Candidate;
use crate::config::Rules;
use crate::scoring::{claim_sequence, score_round, RoundScore};
use crate::trump::{select_trump, SHOVE};
use crate::voids::infer_forbidden;
use crate::weis::{find_weis, score_stoeck, score_weis, WeisKind};

/// Build a Rules from the fields a test cares about. Anything omitted keeps its default,
/// which is the same default `krass_jass/rules.py` documents.
#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature = (
    multipliers=None, weis_enabled=true, weis_large=false, weis_four_nines=true,
    weis_four_beats_sequence=true, stoeck_enabled=true, last_trick_bonus=5, match_bonus=100,
    strict_undertrump=true, puur_exempt=true, claim_order=None
))]
fn rules_dict(
    multipliers: Option<Vec<i32>>,
    weis_enabled: bool,
    weis_large: bool,
    weis_four_nines: bool,
    weis_four_beats_sequence: bool,
    stoeck_enabled: bool,
    last_trick_bonus: i32,
    match_bonus: i32,
    strict_undertrump: bool,
    puur_exempt: bool,
    claim_order: Option<Vec<u8>>,
) -> Vec<i32> {
    // Returned only so Python can round-trip a config; the real object is built below.
    let r = build_rules(
        multipliers, weis_enabled, weis_large, weis_four_nines, weis_four_beats_sequence,
        stoeck_enabled, last_trick_bonus, match_bonus, strict_undertrump, puur_exempt, claim_order,
    );
    r.multipliers.to_vec()
}

#[allow(clippy::too_many_arguments)]
fn build_rules(
    multipliers: Option<Vec<i32>>,
    weis_enabled: bool,
    weis_large: bool,
    weis_four_nines: bool,
    weis_four_beats_sequence: bool,
    stoeck_enabled: bool,
    last_trick_bonus: i32,
    match_bonus: i32,
    strict_undertrump: bool,
    puur_exempt: bool,
    claim_order: Option<Vec<u8>>,
) -> Rules {
    let mut rules = Rules {
        weis_enabled,
        weis_large,
        weis_four_nines,
        weis_four_beats_sequence,
        stoeck_enabled,
        last_trick_bonus,
        match_bonus,
        strict_undertrump,
        puur_exempt,
        ..Rules::default()
    };
    if let Some(m) = multipliers {
        for (i, v) in m.iter().take(6).enumerate() {
            rules.multipliers[i] = *v;
        }
    }
    if let Some(order) = claim_order {
        for (i, v) in order.iter().take(3).enumerate() {
            rules.claim_order[i] = *v;
        }
    }
    rules
}

/// `(kind, points, cards_mask, length, top_rank, suit)` per meld.
#[pyfunction]
#[pyo3(signature = (hand, trump=-1, weis_large=false, weis_four_nines=true, weis_four_beats_sequence=true))]
fn rs_find_weis(
    hand: u64,
    trump: i32,
    weis_large: bool,
    weis_four_nines: bool,
    weis_four_beats_sequence: bool,
) -> Vec<(String, i32, u64, usize, usize, i64)> {
    let rules = Rules {
        weis_large,
        weis_four_nines,
        weis_four_beats_sequence,
        ..Rules::default()
    };
    find_weis(hand, &rules, trump)
        .into_iter()
        .map(|m| {
            (
                match m.kind {
                    WeisKind::Sequence => "sequence".to_string(),
                    WeisKind::Four => "four".to_string(),
                },
                m.points,
                m.cards,
                m.length,
                m.top_rank,
                if m.suit == usize::MAX { -1 } else { m.suit as i64 },
            )
        })
        .collect()
}

#[pyfunction]
#[pyo3(signature = (hands, trump, forehand=0, weis_large=false, weis_four_nines=true, weis_four_beats_sequence=true))]
fn rs_score_weis(
    hands: Vec<u64>,
    trump: i32,
    forehand: usize,
    weis_large: bool,
    weis_four_nines: bool,
    weis_four_beats_sequence: bool,
) -> ((i32, i32), i32) {
    let mut h = [0u64; 4];
    h.copy_from_slice(&hands);
    let rules = Rules { weis_large, weis_four_nines, weis_four_beats_sequence, ..Rules::default() };
    let (points, winner) = score_weis(&h, trump, &rules, forehand);
    ((points[0], points[1]), winner)
}

#[pyfunction]
#[pyo3(signature = (hands, trump, stoeck_enabled=true))]
fn rs_score_stoeck(hands: Vec<u64>, trump: i32, stoeck_enabled: bool) -> (i32, i32) {
    let mut h = [0u64; 4];
    h.copy_from_slice(&hands);
    let rules = Rules { stoeck_enabled, ..Rules::default() };
    let out = score_stoeck(&h, trump, &rules);
    (out[0], out[1])
}

#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature = (trick_points, tricks_won, last_trick_winner, contract, weis=(0,0), stoeck=(0,0), multipliers=None, last_trick_bonus=5, match_bonus=100, weis_enabled=true, stoeck_enabled=true))]
fn rs_score_round(
    trick_points: (i32, i32),
    tricks_won: (usize, usize),
    last_trick_winner: usize,
    contract: usize,
    weis: (i32, i32),
    stoeck: (i32, i32),
    multipliers: Option<Vec<i32>>,
    last_trick_bonus: i32,
    match_bonus: i32,
    weis_enabled: bool,
    stoeck_enabled: bool,
) -> ((i32, i32), (i32, i32), (i32, i32), (i32, i32), (i32, i32), i32, (i32, i32)) {
    let rules = build_rules(
        multipliers, weis_enabled, false, true, true, stoeck_enabled, last_trick_bonus,
        match_bonus, true, true, None,
    );
    let s: RoundScore = score_round(
        [trick_points.0, trick_points.1],
        [tricks_won.0, tricks_won.1],
        last_trick_winner,
        contract,
        &rules,
        [weis.0, weis.1],
        [stoeck.0, stoeck.1],
    );
    let total = s.total();
    (
        (s.trick_points[0], s.trick_points[1]),
        (s.last_trick[0], s.last_trick[1]),
        (s.match_bonus[0], s.match_bonus[1]),
        (s.weis[0], s.weis[1]),
        (s.stoeck[0], s.stoeck[1]),
        s.multiplier,
        (total[0], total[1]),
    )
}

#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature = (trick_points, tricks_won, last_trick_winner, contract, trick_results, weis=(0,0), stoeck=(0,0), multipliers=None, claim_order=None))]
fn rs_claim_sequence(
    trick_points: (i32, i32),
    tricks_won: (usize, usize),
    last_trick_winner: usize,
    contract: usize,
    trick_results: Vec<(usize, i32)>,
    weis: (i32, i32),
    stoeck: (i32, i32),
    multipliers: Option<Vec<i32>>,
    claim_order: Option<Vec<u8>>,
) -> Vec<(usize, i32)> {
    let rules = build_rules(
        multipliers, true, false, true, true, true, 5, 100, true, true, claim_order,
    );
    let score = score_round(
        [trick_points.0, trick_points.1],
        [tricks_won.0, tricks_won.1],
        last_trick_winner,
        contract,
        &rules,
        [weis.0, weis.1],
        [stoeck.0, stoeck.1],
    );
    claim_sequence(&score, &trick_results, &rules)
}

#[pyfunction]
#[pyo3(signature = (tricks, current_trick, current_leader, trump, puur_exempt=true))]
fn rs_infer_forbidden(
    tricks: Vec<(usize, Vec<usize>)>,
    current_trick: Vec<usize>,
    current_leader: usize,
    trump: i32,
    puur_exempt: bool,
) -> Vec<u64> {
    let rules = Rules { puur_exempt, ..Rules::default() };
    infer_forbidden(&tricks, &current_trick, current_leader, trump, &rules).to_vec()
}

/// The table read that feeds the display. Public information only — see awareness.rs.
#[pyfunction]
fn rs_trick_taker(cards: Vec<usize>, leader: usize, contract: usize) -> Option<usize> {
    trick_taker(&cards, leader, contract)
}

/// Leaf positions with the *mean* of many random playouts as the label.
///
/// The label is deliberately the playout's own expectation rather than the true value of the
/// position: fitting to it makes the evaluator a zero-variance version of the thing it
/// replaces, so a measured difference is variance and nothing else. See leafeval.rs.
///
/// Positions come from random play, one per ply — roughly the distribution the tree's leaves
/// are drawn from, since a leaf is a short tree descent followed by random continuation.
#[pyfunction]
#[pyo3(signature = (seed, rounds, playouts, contract=None))]
fn rs_leaf_samples(
    seed: u64,
    rounds: usize,
    playouts: usize,
    contract: Option<usize>,
) -> (Vec<Vec<f64>>, Vec<f64>) {
    let rules = Rules::default();
    let mut rng = Rng::new(seed | 1);
    let mut xs: Vec<Vec<f64>> = Vec::new();
    let mut ys: Vec<f64> = Vec::new();
    const ROOT: usize = 0;

    for r in 0..rounds {
        let c = contract.unwrap_or(rng.below(6) as usize);
        let k = Kernel::new(c, rules.strict_undertrump, rules.puur_exempt, 5, 0);
        let hands = crate::deal::deal(seed.wrapping_add(r as u64).wrapping_mul(0x9E37_79B9), 0);
        let mut round = Round::new(c, hands, rng.below(4) as usize, rules);

        while !round.done() {
            let mut feats = [0.0f64; N_FEATURES];
            features(
                &round.hands, &round.trick, round.leader, round.to_play(),
                &round.tricks_won, &k, ROOT, &mut feats,
            );

            // The label: many random completions of this exact position, averaged. The
            // baseline evaluator is one draw from this distribution; the fit is its mean.
            let banked = round.trick_points;
            let mut acc = 0.0f64;
            for _ in 0..playouts {
                let mut sim = round.clone();
                while !sim.done() {
                    let card = pick_random(sim.legal_moves(sim.to_play()), &mut rng);
                    let _ = sim.play(card);
                }
                let a = sim.trick_points[ROOT] - banked[ROOT] + k.last_trick_bonus
                    * if sim.last_trick_winner as usize & 1 == ROOT { 1 } else { 0 };
                let b = sim.trick_points[1 - ROOT] - banked[1 - ROOT] + k.last_trick_bonus
                    * if sim.last_trick_winner as usize & 1 == ROOT { 0 } else { 1 };
                acc += a as f64 / ((a + b).max(1)) as f64;
            }
            xs.push(feats.to_vec());
            ys.push(acc / playouts as f64);

            let card = pick_random(round.legal_moves(round.to_play()), &mut rng);
            if round.play(card).is_err() {
                break;
            }
        }
    }
    (xs, ys)
}

/// Features of one candidate card, for building a policy-training set in Python.
#[pyfunction]
#[pyo3(signature = (card, hand, live, trick, contract, trump, partner_winning, opponent_winning))]
#[allow(clippy::too_many_arguments)]
fn rs_card_features(
    card: usize,
    hand: u64,
    live: u64,
    trick: Vec<usize>,
    contract: usize,
    trump: i32,
    partner_winning: bool,
    opponent_winning: bool,
) -> Vec<f32> {
    let mut out = [0.0f32; N_POLICY_FEATURES];
    card_features(card, hand, live, &trick, contract, trump,
                  partner_winning, opponent_winning, &mut out);
    out.to_vec()
}

/// Features of every legal card at one decision, ascending by card — the training set for
/// `playmodel.rs` is built from these, so the model is fitted on exactly what it will see.
#[pyfunction]
#[pyo3(signature = (hand, live, trick, trick_leader, seat, contract, declarer, legal))]
#[allow(clippy::too_many_arguments)]
fn rs_play_features(
    hand: u64,
    live: u64,
    trick: Vec<usize>,
    trick_leader: usize,
    seat: usize,
    contract: usize,
    declarer: usize,
    legal: u64,
) -> Vec<Vec<f32>> {
    use crate::playmodel::{PlayCtx, N_PLAY_FEATURES};
    let ctx = PlayCtx::new(hand, live, &trick, trick_leader & 3, seat & 3, contract, declarer);
    let mut out = Vec::new();
    let mut f = [0.0f32; N_PLAY_FEATURES];
    for c in crate::cards::card_list(legal) {
        ctx.features(c, &mut f);
        out.push(f.to_vec());
    }
    out
}

/// log π(card) for every legal card, ascending by card. `model_json` of None uses the shipped
/// model; passing one lets Python check a freshly trained model against the Rust evaluation.
#[pyfunction]
#[pyo3(signature = (hand, live, trick, trick_leader, seat, contract, declarer, legal, temperature=1.0, model_json=None))]
#[allow(clippy::too_many_arguments)]
fn rs_play_log_probs(
    hand: u64,
    live: u64,
    trick: Vec<usize>,
    trick_leader: usize,
    seat: usize,
    contract: usize,
    declarer: usize,
    legal: u64,
    temperature: f32,
    model_json: Option<String>,
) -> Vec<(usize, f32)> {
    use crate::playmodel::{model, PlayCtx, PlayModel};
    let owned = model_json.map(|t| PlayModel::from_json(&t));
    let m = owned.as_ref().unwrap_or_else(|| model());
    let ctx = PlayCtx::new(hand, live, &trick, trick_leader & 3, seat & 3, contract, declarer);
    crate::cards::card_list(legal)
        .into_iter()
        .map(|c| (c, m.log_prob(&ctx, legal, c, temperature)))
        .collect()
}

/// Imagined worlds for one decision, with the evidence for each kept apart: the log-likelihood
/// of the other seats' plays and of the bid. Measurement only — `arena/belief_quality.py` sweeps
/// the weights on these offline, so tuning beliefs does not need a match per setting.
#[pyfunction]
#[pyo3(signature = (seat, hand, unseen, trick, trick_leader, contract, forbidden, declarer, history, pool, seed, policy_temperature=1.0, bid_temperature=3.0, weis_called=None, weis_played=None))]
#[allow(clippy::too_many_arguments)]
fn rs_belief_pool(
    seat: usize,
    hand: u64,
    unseen: u64,
    trick: Vec<usize>,
    trick_leader: usize,
    contract: usize,
    forbidden: Vec<u64>,
    declarer: usize,
    history: Vec<(usize, usize)>,
    pool: usize,
    seed: u64,
    policy_temperature: f32,
    bid_temperature: f32,
    weis_called: Option<Vec<i32>>,
    weis_played: Option<Vec<u64>>,
) -> (Vec<Vec<u64>>, Vec<f32>, Vec<f32>) {
    use crate::announce::{determinize_consistent, Announcements};
    use crate::belief::{bid_log_likelihood, play_log_likelihood, PlayInfo};
    let seat = seat & 3;
    let k = Kernel::new(contract, true, true, 5, 0);
    let base = hand.count_ones() as usize;
    let mut counts = [0usize; 4];
    for s in 0..4 {
        if s == seat {
            continue;
        }
        let played = (0..trick.len()).any(|i| (trick_leader + i) & 3 == s);
        counts[s] = if played { base - 1 } else { base };
    }
    let mut fb = [0u64; 4];
    fb.copy_from_slice(&forbidden[..4]);
    let mut info = PlayInfo::off();
    info.declarer = declarer;
    info.history = history;
    info.policy_temperature = policy_temperature;
    info.bid_temperature = bid_temperature;
    // The calls filter worlds exactly as the search does, so the pool is the search's own
    // baseline and not a looser one.
    let mut ann = Announcements::none();
    if let Some(called) = weis_called {
        ann.called.copy_from_slice(&called[..4]);
        ann.called[seat] = -1;
        ann.rules = Rules { weis_enabled: true, ..Rules::default() };
        ann.trump = if contract < 4 { contract as i32 } else { -1 };
        ann.draws = 16;
    }
    if let Some(played) = weis_played {
        ann.played.copy_from_slice(&played[..4]);
    }
    let mut rng = Rng::new(seed | 1);
    let (mut worlds, mut play, mut bid) = (Vec::new(), Vec::new(), Vec::new());
    for _ in 0..pool {
        let mut dealt = [0u64; 4];
        if !determinize_consistent(unseen, &counts, &fb, &[[0i8; 4]; 4], &[0i8; 4], &ann, seat,
                                   hand, &mut dealt, &mut rng) {
            continue;
        }
        dealt[seat] = hand;
        worlds.push(dealt.to_vec());
        play.push(play_log_likelihood(&dealt, &info, seat, &k));
        bid.push(bid_log_likelihood(&dealt, &info, seat, trick_leader & 3, contract));
    }
    (worlds, play, bid)
}

/// P(each unseen card sits at each other seat), as the search believes it — `belief.rs`.
///
/// The pool the search plays from, summarised instead of sampled: same worlds, same weights from
/// the table's play, calls and bids. Nothing hidden is read, so this is safe to show a player who
/// wants to see what the bot is reasoning from (the app's test mode). Returns `(card, p_next,
/// p_partner, p_previous)` in play order from `seat`, and the pool's effective sample size.
#[pyfunction]
#[pyo3(signature = (seat, hand, unseen, trick, trick_leader, contract, forbidden, declarer, history,
    pool=4096, seed=1, belief_alpha=1.0, bid_alpha=1.0, policy_temperature=1.0, bid_temperature=3.0,
    weis_called=None, weis_played=None, sidi_auction=None, sidi_alpha=0.0, model_json=None))]
#[allow(clippy::too_many_arguments)]
fn rs_belief_marginals(
    py: Python<'_>,
    seat: usize,
    hand: u64,
    unseen: u64,
    trick: Vec<usize>,
    trick_leader: usize,
    contract: usize,
    forbidden: Vec<u64>,
    declarer: usize,
    history: Vec<(usize, usize)>,
    pool: usize,
    seed: u64,
    belief_alpha: f32,
    bid_alpha: f32,
    policy_temperature: f32,
    bid_temperature: f32,
    weis_called: Option<Vec<i32>>,
    weis_played: Option<Vec<u64>>,
    sidi_auction: Option<Vec<(usize, usize, i32)>>,
    sidi_alpha: f32,
    model_json: Option<String>,
) -> (Vec<(usize, f32, f32, f32)>, f64) {
    use crate::announce::Announcements;
    use crate::belief::{PlayInfo, Pool};
    use crate::objective::Stakes;
    let seat = seat & 3;
    let k = Kernel::new(contract, true, true, 5, 0);
    // How many cards each seat still holds, counted from the round's public history — the view
    // may be asked for at any moment, not only when `seat` is on turn.
    let mut counts = [crate::scoring::TRICKS_PER_ROUND; 4];
    for &(s, _) in &history {
        counts[s & 3] -= 1;
    }
    counts[seat] = 0;
    let mut fb = [0u64; 4];
    fb.copy_from_slice(&forbidden[..4]);
    let mut ann = Announcements::none();
    if let Some(called) = weis_called {
        ann.called.copy_from_slice(&called[..4]);
        ann.called[seat] = -1;
        ann.rules = Rules { weis_enabled: true, ..Rules::default() };
        ann.trump = if contract < 4 { contract as i32 } else { -1 };
        ann.draws = crate::announce::MAX_DRAWS;
    }
    if let Some(played) = weis_played {
        ann.played.copy_from_slice(&played[..4]);
    }
    let mut info = PlayInfo::off();
    info.declarer = declarer;
    info.history = history;
    info.belief_alpha = belief_alpha;
    info.bid_alpha = bid_alpha;
    info.belief_pool = pool;
    info.policy_temperature = policy_temperature;
    info.bid_temperature = bid_temperature;
    info.sidi_alpha = sidi_alpha;
    info.sidi_auction = sidi_auction
        .unwrap_or_default()
        .into_iter()
        .map(|(s, contract, value)| crate::sidi_read::Bid { seat: s & 3, contract, value })
        .collect();
    info.model = model_json.map(|t| std::sync::Arc::new(crate::playmodel::PlayModel::from_json(&t)));

    let position = crate::search::Position {
        seat,
        hand,
        unseen,
        trick,
        trick_leader: trick_leader & 3,
        forbidden: fb,
        affinity: [[0i8; 4]; 4],
        rank_bias: [0i8; 4],
        stakes: Stakes::default(),
        adversarial: true,
        leaf_weights: Vec::new(),
        announcements: ann,
        play: info,
    };
    py.allow_threads(|| {
        let mut rng = Rng::new(seed | 1);
        let Some(built) = Pool::build(&position, &k, &counts, &mut rng) else {
            return (Vec::new(), 0.0);
        };
        let m = built.marginals();
        let mut out = Vec::new();
        let mut rest = unseen;
        while rest != 0 {
            let card = rest.trailing_zeros() as usize;
            rest &= rest - 1;
            out.push((
                card,
                m[(seat + 1) & 3][card],
                m[(seat + 2) & 3][card],
                m[(seat + 3) & 3][card],
            ));
        }
        (out, built.ess)
    })
}

/// The play and bid log-likelihood of given worlds, under a chosen play model and temperatures.
/// Saved worlds can be re-scored this way without replaying the rounds they came from, which is
/// what makes a temperature sweep a matter of minutes (`arena/belief_quality.py --rescore`).
#[pyfunction]
#[pyo3(signature = (worlds, seat, trick_leader, contract, declarer, history, policy_temperature=1.0, bid_temperature=3.0, model_json=None))]
#[allow(clippy::too_many_arguments)]
fn rs_belief_loglik(
    py: Python<'_>,
    worlds: Vec<Vec<u64>>,
    seat: usize,
    trick_leader: usize,
    contract: usize,
    declarer: usize,
    history: Vec<(usize, usize)>,
    policy_temperature: f32,
    bid_temperature: f32,
    model_json: Option<String>,
) -> (Vec<f32>, Vec<f32>) {
    use crate::belief::{bid_log_likelihood, play_log_likelihood, PlayInfo};
    let k = Kernel::new(contract, true, true, 5, 0);
    let mut info = PlayInfo::off();
    info.declarer = declarer;
    info.history = history;
    info.policy_temperature = policy_temperature;
    info.bid_temperature = bid_temperature;
    info.model = model_json.map(|t| std::sync::Arc::new(crate::playmodel::PlayModel::from_json(&t)));
    py.allow_threads(|| {
        let mut play = Vec::with_capacity(worlds.len());
        let mut bid = Vec::with_capacity(worlds.len());
        for w in &worlds {
            let mut h = [0u64; 4];
            h.copy_from_slice(&w[..4]);
            play.push(play_log_likelihood(&h, &info, seat & 3, &k));
            bid.push(bid_log_likelihood(&h, &info, seat & 3, trick_leader & 3, contract));
        }
        (play, bid)
    })
}

fn four(hands: &[u64]) -> [u64; 4] {
    let mut h = [0u64; 4];
    h.copy_from_slice(&hands[..4]);
    h
}

/// The value network's inputs for a perfect-information position, as little-endian `f32` bytes.
#[pyfunction]
fn rs_value_features(hands: Vec<u64>, trick: Vec<usize>, trick_leader: usize, contract: usize)
    -> std::borrow::Cow<'static, [u8]> {
    use crate::valuenet::{features, N_VALUE_FEATURES};
    let mut x = [0.0f32; N_VALUE_FEATURES];
    features(&four(&hands), &trick, trick_leader & 3, contract, &mut x);
    std::borrow::Cow::Owned(x.iter().flat_map(|v| v.to_le_bytes()).collect())
}

/// The value network's estimate: the fraction of the remaining points the mover's team takes.
#[pyfunction]
#[pyo3(signature = (hands, trick, trick_leader, contract, model_json=None))]
fn rs_value_eval(hands: Vec<u64>, trick: Vec<usize>, trick_leader: usize, contract: usize,
                 model_json: Option<String>) -> f32 {
    use crate::valuenet::{features, net, ValueNet, N_VALUE_FEATURES};
    let owned = model_json.map(|t| ValueNet::from_json(&t));
    let n = owned.as_ref().unwrap_or_else(|| net());
    let mut x = [0.0f32; N_VALUE_FEATURES];
    features(&four(&hands), &trick, trick_leader & 3, contract, &mut x);
    n.eval(&x)
}

/// The same fraction, estimated as the mean of `k` random playouts — the baseline to beat.
#[pyfunction]
fn rs_playout_fraction(hands: Vec<u64>, trick: Vec<usize>, trick_leader: usize, contract: usize,
                       k: usize, seed: u64) -> f64 {
    use crate::valuenet::{random_remaining, remaining_points, to_move};
    let kern = Kernel::new(contract, true, true, 5, 0);
    let h = four(&hands);
    let total = remaining_points(&h, &trick, &kern) as f64;
    if total <= 0.0 {
        return 0.5;
    }
    let team = to_move(&trick, trick_leader & 3) & 1;
    let mut rng = Rng::new(seed | 1);
    let mut acc = 0.0;
    for _ in 0..k.max(1) {
        let (a, b) = random_remaining(h, &trick, trick_leader & 3, &kern, &mut rng);
        acc += if team == 0 { a } else { b } as f64;
    }
    acc / (k.max(1) as f64 * total)
}

#[allow(clippy::too_many_arguments)]
fn belief_input<'a>(
    seat: usize,
    hand: u64,
    history: &'a [(usize, usize)],
    contract: usize,
    declarer: usize,
    forehand: usize,
    forbidden: &[u64],
    known: &[u64],
    weis_called: &[i32],
) -> crate::beliefnet::BeliefInput<'a> {
    let mut f = [0u64; 4];
    let mut k = [0u64; 4];
    let mut w = [-1i32; 4];
    f.copy_from_slice(&forbidden[..4]);
    k.copy_from_slice(&known[..4]);
    w.copy_from_slice(&weis_called[..4]);
    crate::beliefnet::BeliefInput {
        seat: seat & 3, hand, history, contract, declarer, forehand,
        forbidden: f, known: k, weis_called: w,
    }
}

/// Belief-network inputs for one decision, as little-endian `f32` bytes — `np.frombuffer`
/// reads them without building a Python list of 865 floats per decision.
#[pyfunction]
#[pyo3(signature = (seat, hand, history, contract, declarer, forehand, forbidden, known, weis_called))]
#[allow(clippy::too_many_arguments)]
fn rs_belief_features(
    seat: usize,
    hand: u64,
    history: Vec<(usize, usize)>,
    contract: usize,
    declarer: usize,
    forehand: usize,
    forbidden: Vec<u64>,
    known: Vec<u64>,
    weis_called: Vec<i32>,
) -> std::borrow::Cow<'static, [u8]> {
    use crate::beliefnet::N_BELIEF_FEATURES;
    let inp = belief_input(seat, hand, &history, contract, declarer, forehand, &forbidden, &known, &weis_called);
    let mut x = [0.0f32; N_BELIEF_FEATURES];
    inp.features(&mut x);
    std::borrow::Cow::Owned(x.iter().flat_map(|v| v.to_le_bytes()).collect())
}

/// `[card][r - 1]` log-probabilities from the belief network. `model_json` of None uses the
/// shipped network; passing one checks a freshly trained network against the Rust evaluation.
#[pyfunction]
#[pyo3(signature = (seat, hand, history, contract, declarer, forehand, forbidden, known, weis_called, model_json=None))]
#[allow(clippy::too_many_arguments)]
fn rs_belief_log_probs(
    seat: usize,
    hand: u64,
    history: Vec<(usize, usize)>,
    contract: usize,
    declarer: usize,
    forehand: usize,
    forbidden: Vec<u64>,
    known: Vec<u64>,
    weis_called: Vec<i32>,
    model_json: Option<String>,
) -> Vec<Vec<f32>> {
    use crate::beliefnet::{net, BeliefNet};
    let owned = model_json.map(|t| BeliefNet::from_json(&t));
    let n = owned.as_ref().unwrap_or_else(|| net());
    let inp = belief_input(seat, hand, &history, contract, declarer, forehand, &forbidden, &known, &weis_called);
    let mut out = [[0.0f32; 3]; 36];
    n.log_probs(&inp, &mut out);
    out.iter().map(|row| row.to_vec()).collect()
}

/// What the bidding says, exposed so the Python mirror can be held to the same answer.
#[pyfunction]
fn rs_infer_from_bid(
    forehand: usize,
    declarer: usize,
    contract: usize,
    seat: usize,
) -> (Vec<Vec<i8>>, Vec<i8>) {
    let (suits, ranks) = infer_from_bid(forehand, declarer, contract, seat);
    (suits.iter().map(|r| r.to_vec()).collect(), ranks.to_vec())
}

/// The search's reward, exposed so the Python mirror can be held to the same numbers.
#[pyfunction]
#[pyo3(signature = (ours, theirs, team, scores, weis, target, multiplier, sidi_bid=0, sidi_declarers=0, sidi_doubled=false))]
#[allow(clippy::too_many_arguments)]
fn rs_reward(
    ours: i32,
    theirs: i32,
    team: usize,
    scores: (i32, i32),
    weis: (i32, i32),
    target: i32,
    multiplier: i32,
    sidi_bid: i32,
    sidi_declarers: usize,
    sidi_doubled: bool,
) -> f64 {
    reward(
        ours,
        theirs,
        team,
        &Stakes {
            scores: [scores.0, scores.1],
            bonus: [weis.0, weis.1],
            target,
            multiplier,
            risk_lambda: 0.0,
            sidi_bid,
            sidi_declarers,
            sidi_doubled,
        },
    )
}

/// Sidi: `(P(the declarers reach the bid), their expected points)` as seen from `seat` —
/// `sidi_estimate.rs`. What a bot doubles on.
#[pyfunction]
#[pyo3(signature = (seat, hand, history, leader, contract, declarer, bid, auction, samples=400, alpha=1.0, seed=0))]
#[allow(clippy::too_many_arguments)]
fn rs_sidi_make_probability(
    py: Python<'_>,
    seat: usize,
    hand: u64,
    history: Vec<(usize, usize)>,
    leader: usize,
    contract: usize,
    declarer: usize,
    bid: i32,
    auction: Vec<(usize, usize, i32)>,
    samples: usize,
    alpha: f32,
    seed: u64,
) -> (f64, f64) {
    let bids: Vec<crate::sidi_read::Bid> = auction
        .into_iter()
        .map(|(seat, contract, value)| crate::sidi_read::Bid { seat, contract, value })
        .collect();
    py.allow_threads(|| {
        let q = crate::sidi_estimate::Question {
            seat: seat & 3, hand, history: &history, leader: leader & 3, contract,
            declarer: declarer & 3, bid, auction: &bids, alpha,
        };
        crate::sidi_estimate::make_probability(&q, samples, seed)
    })
}

/// Sidi: the rule bidder's call — `sidi_bidding.rs`, held to `krass_jass/sidi_bidding.py`.
#[pyfunction]
#[pyo3(signature = (hand, auction, seat, double=None))]
fn rs_sidi_choose_call(hand: u64, auction: Vec<(usize, String)>, seat: usize, double: Option<bool>) -> PyResult<String> {
    let mut calls = Vec::with_capacity(auction.len());
    for (s, text) in &auction {
        let call = crate::auction::Call::parse(text)
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err(format!("unknown call {text:?}")))?;
        calls.push((*s, call));
    }
    Ok(crate::sidi_bidding::choose_call(hand, &calls, seat & 3, double).name())
}

/// log P(the auction | the dealt hands), for every seat but `root` — `sidi_read.rs`. Exposed so
/// the reading can be tested and inspected without running a search.
#[pyfunction]
fn rs_sidi_auction_loglik(dealt: Vec<u64>, auction: Vec<(usize, usize, i32)>, root: usize) -> f64 {
    let mut hands = [0u64; 4];
    hands.copy_from_slice(&dealt[..4]);
    let bids: Vec<crate::sidi_read::Bid> = auction
        .into_iter()
        .map(|(seat, contract, value)| crate::sidi_read::Bid { seat, contract, value })
        .collect();
    crate::sidi_read::auction_log_likelihood(&hands, &bids, root) as f64
}

/// What the discards suggest, per seat and suit. Mirror of `krass_jass/reading.py`.
#[pyfunction]
fn rs_infer_affinity(
    tricks: Vec<(usize, Vec<usize>)>,
    current_trick: Vec<usize>,
    current_leader: usize,
    trump: i32,
) -> Vec<Vec<i8>> {
    infer_affinity(&tricks, &current_trick, current_leader, trump)
        .iter()
        .map(|row| row.to_vec())
        .collect()
}

/// Draw `samples` determinizations. Exposed for tests: the two properties worth pinning —
/// that the prior tilts the sampling and that it never removes a world — are statements about
/// a *distribution*, so they need many draws rather than one search.
#[pyfunction]
#[pyo3(signature = (unseen, counts, forbidden, affinity, seed, samples, rank_bias=None))]
fn rs_determinize(
    unseen: u64,
    counts: Vec<usize>,
    forbidden: Vec<u64>,
    affinity: Vec<Vec<i8>>,
    seed: u64,
    samples: usize,
    rank_bias: Option<Vec<i8>>,
) -> Vec<Vec<u64>> {
    let mut c = [0usize; 4];
    c.copy_from_slice(&counts[..4]);
    let mut f = [0u64; 4];
    f.copy_from_slice(&forbidden[..4]);
    let mut a = [[0i8; 4]; 4];
    for (seat, row) in affinity.iter().enumerate().take(4) {
        for (suit, &n) in row.iter().enumerate().take(4) {
            a[seat][suit] = n;
        }
    }
    let mut rb = [0i8; 4];
    if let Some(rows) = rank_bias {
        for (i, &v) in rows.iter().enumerate().take(4) {
            rb[i] = v;
        }
    }
    let mut rng = Rng::new(seed | 1);
    let mut out = Vec::with_capacity(samples);
    for _ in 0..samples {
        let mut dealt = [0u64; 4];
        if determinize(unseen, &c, &f, &a, &rb, &mut dealt, &mut rng) {
            out.push(dealt.to_vec());
        }
    }
    out
}

/// The convention tie-break, on a candidate list the caller already has.
///
/// Exposed so `tests/test_convention.py` can hold both implementations to the same answer:
/// both sides read the *same* search output, so any difference is the convention itself.
#[pyfunction]
#[pyo3(signature = (candidates, hand, unseen, seen, trick, seat, trump, contract, forbidden, declaring=false, vote_slack=0.05, score_slack=0.01, discarded=0))]
#[allow(clippy::too_many_arguments)]
fn rs_convention_choose(
    candidates: Vec<(usize, u64, f64, u32)>,
    hand: u64,
    unseen: u64,
    seen: u64,
    trick: Vec<usize>,
    seat: usize,
    trump: i32,
    contract: usize,
    forbidden: Vec<u64>,
    declaring: bool,
    vote_slack: f64,
    score_slack: f64,
    discarded: u8,
) -> Option<usize> {
    let cands: Vec<Candidate> = candidates
        .into_iter()
        .map(|(card, visits, mean_score, determinizations_selecting)| Candidate {
            card,
            visits,
            mean_score,
            determinizations_selecting,
        })
        .collect();
    let mut forb = [0u64; 4];
    for (i, v) in forbidden.into_iter().take(4).enumerate() {
        forb[i] = v;
    }
    convention::choose(
        &cands, hand, unseen, seen, &trick, seat, trump, contract, &forb, declaring,
        (vote_slack, score_slack), discarded,
    )
}

/// Returns the contract index, or -1 for a shove.
#[pyfunction]
#[pyo3(signature = (hand, is_forehand, multipliers=None))]
fn rs_select_trump(hand: u64, is_forehand: bool, multipliers: Option<Vec<i32>>) -> i64 {
    let rules = build_rules(multipliers, true, false, true, true, true, 5, 100, true, true, None);
    let action = select_trump(hand, is_forehand, &rules);
    if action == SHOVE {
        -1
    } else {
        action as i64
    }
}

#[pyfunction]
#[pyo3(signature = (hand, multipliers=None))]
fn rs_trump_scores(hand: u64, multipliers: Option<Vec<i32>>) -> Vec<f64> {
    let rules = build_rules(multipliers, true, false, true, true, true, 5, 100, true, true, None);
    crate::trump::score_all(hand, &rules).to_vec()
}

/// Replay a whole round through the Rust round state, returning everything the Python
/// `RoundState` exposes, so the two can be compared ply by ply.
#[pyfunction]
#[pyo3(signature = (contract, hands, leader, cards))]
fn rs_replay_round(
    contract: usize,
    hands: Vec<u64>,
    leader: usize,
    cards: Vec<usize>,
) -> PyResult<(Vec<u64>, (i32, i32), (usize, usize), i32, Vec<(usize, i32)>, Vec<u64>)> {
    use crate::round::Round;
    use pyo3::exceptions::PyValueError;

    let mut h = [0u64; 4];
    h.copy_from_slice(&hands);
    let mut round = Round::new(contract, h, leader, Rules::default());

    // Record the legal set at every ply — comparing only the final state would miss a
    // divergence that happened to end up in the same place.
    let mut legal_per_ply = Vec::with_capacity(cards.len());
    for &card in &cards {
        legal_per_ply.push(round.legal_moves(round.to_play()));
        round
            .play(card)
            .map_err(|e| PyValueError::new_err(format!("{e:?}")))?;
    }
    Ok((
        round.hands.to_vec(),
        (round.trick_points[0], round.trick_points[1]),
        (round.tricks_won[0], round.tricks_won[1]),
        round.last_trick_winner,
        round.trick_results.clone(),
        legal_per_ply,
    ))
}

#[pyfunction]
fn rs_deal(seed: u64, round: u32) -> Vec<u64> {
    crate::deal::deal(seed, round).to_vec()
}

/// A Rust `Game`, driven from Python so the two phase machines can be run through the same
/// decisions and their event streams compared.
#[pyclass(name = "RsGame")]
pub struct PyGame {
    inner: crate::game::Game,
}

#[pymethods]
impl PyGame {
    #[new]
    #[pyo3(signature = (seed, target_score=1000, weis_enabled=true, weis_manual=false, stoeck_enabled=true, multipliers=None, sidi=false))]
    fn new(
        seed: u64,
        target_score: i32,
        weis_enabled: bool,
        weis_manual: bool,
        stoeck_enabled: bool,
        multipliers: Option<Vec<i32>>,
        sidi: bool,
    ) -> Self {
        let base = if sidi { Rules::sidi() } else { Rules::default() };
        let mut rules = Rules {
            target_score,
            weis_enabled: weis_enabled && !sidi,
            weis_manual,
            stoeck_enabled: stoeck_enabled && !sidi,
            ..base
        };
        if let Some(m) = multipliers {
            for (i, v) in m.iter().take(6).enumerate() {
                rules.multipliers[i] = *v;
            }
        }
        PyGame { inner: crate::game::Game::new(rules, seed) }
    }

    #[getter]
    fn phase(&self) -> String {
        self.inner.phase.as_str().to_string()
    }
    #[getter]
    fn to_act(&self) -> Option<usize> {
        self.inner.to_act()
    }
    #[getter]
    fn scores(&self) -> (i32, i32) {
        (self.inner.scores[0], self.inner.scores[1])
    }
    #[getter]
    fn forehand(&self) -> usize {
        self.inner.forehand
    }
    #[getter]
    fn round_index(&self) -> u32 {
        self.inner.round_index
    }
    #[getter]
    fn weis_offers(&self) -> Vec<i32> {
        self.inner.weis_offers.to_vec()
    }

    fn hand_of(&self, seat: usize) -> u64 {
        self.inner.hand_of(seat)
    }

    fn legal_moves(&self, seat: usize) -> u64 {
        self.inner.round.as_ref().map_or(0, |r| r.legal_moves(seat))
    }

    /// `action` is a contract index, or -1 to shove.
    fn bid(&mut self, seat: usize, action: i64) -> PyResult<()> {
        use pyo3::exceptions::PyValueError;
        let a = if action < 0 { crate::trump::SHOVE } else { action as usize };
        self.inner.bid(seat, a).map_err(|e| PyValueError::new_err(format!("{e:?}")))
    }

    /// Sidi: one call in the auction, in its wire form (`PASS`, `DOUBLE`, `HEARTS 100`).
    fn call(&mut self, seat: usize, call: &str) -> PyResult<()> {
        use pyo3::exceptions::PyValueError;
        let parsed = crate::auction::Call::parse(call)
            .ok_or_else(|| PyValueError::new_err(format!("unknown call {call:?}")))?;
        self.inner.call(seat, parsed).map_err(|e| PyValueError::new_err(format!("{e:?}")))
    }

    /// Sidi: the calls the seat may make now, in their wire form.
    fn legal_calls(&self, seat: usize) -> Vec<String> {
        self.inner.auction.as_ref().map_or(Vec::new(), |a| {
            a.legal_calls(seat).iter().map(|c| c.name()).collect()
        })
    }

    /// Sidi: an opponent's answer after the lead.
    fn double(&mut self, seat: usize, double: bool) -> PyResult<()> {
        use pyo3::exceptions::PyValueError;
        self.inner.double(seat, double).map_err(|e| PyValueError::new_err(format!("{e:?}")))
    }

    #[getter]
    fn declarer(&self) -> usize {
        self.inner.declarer
    }
    #[getter]
    fn dealer(&self) -> usize {
        self.inner.dealer
    }
    #[getter]
    fn bid_value(&self) -> i32 {
        self.inner.bid_value
    }
    #[getter]
    fn doubled(&self) -> bool {
        self.inner.doubled
    }

    fn choose_weis(&mut self, seat: usize, announce: bool) -> PyResult<()> {
        use pyo3::exceptions::PyValueError;
        self.inner
            .choose_weis(seat, announce)
            .map_err(|e| PyValueError::new_err(format!("{e:?}")))
    }

    fn play(&mut self, seat: usize, card: usize) -> PyResult<()> {
        use pyo3::exceptions::PyValueError;
        self.inner.play(seat, card).map_err(|e| PyValueError::new_err(format!("{e:?}")))
    }

    fn next_round(&mut self) -> PyResult<()> {
        use pyo3::exceptions::PyValueError;
        self.inner.next_round().map_err(|e| PyValueError::new_err(format!("{e:?}")))
    }

    /// Every event as JSON, in order.
    fn events(&self) -> Vec<String> {
        self.inner.log.all().iter().map(|e| e.to_json()).collect()
    }

    /// Events this seat may see, from `after` exclusive.
    fn events_for(&self, seat: usize, after: usize) -> Vec<String> {
        self.inner.log.for_seat(seat, after).into_iter().map(|e| e.to_json()).collect()
    }

    fn weis_summary(&self) -> Vec<(usize, i32, Option<Vec<usize>>, bool, bool)> {
        self.inner
            .weis_summary
            .iter()
            .map(|e| (e.seat, e.points, e.cards.clone(), e.winner, e.best))
            .collect()
    }

    fn stoeck_announced(&self) -> Vec<(usize, i32, usize)> {
        self.inner.stoeck_announced.clone()
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyGame>()?;
    m.add_function(wrap_pyfunction!(rs_deal, m)?)?;
    m.add_function(wrap_pyfunction!(rs_replay_round, m)?)?;
    m.add_function(wrap_pyfunction!(rules_dict, m)?)?;
    m.add_function(wrap_pyfunction!(rs_find_weis, m)?)?;
    m.add_function(wrap_pyfunction!(rs_score_weis, m)?)?;
    m.add_function(wrap_pyfunction!(rs_score_stoeck, m)?)?;
    m.add_function(wrap_pyfunction!(rs_score_round, m)?)?;
    m.add_function(wrap_pyfunction!(rs_claim_sequence, m)?)?;
    m.add_function(wrap_pyfunction!(rs_infer_forbidden, m)?)?;
    m.add_function(wrap_pyfunction!(rs_trick_taker, m)?)?;
    m.add_function(wrap_pyfunction!(rs_convention_choose, m)?)?;
    m.add_function(wrap_pyfunction!(rs_infer_affinity, m)?)?;
    m.add_function(wrap_pyfunction!(rs_reward, m)?)?;
    m.add_function(wrap_pyfunction!(rs_sidi_auction_loglik, m)?)?;
    m.add_function(wrap_pyfunction!(rs_sidi_make_probability, m)?)?;
    m.add_function(wrap_pyfunction!(rs_sidi_choose_call, m)?)?;
    m.add_function(wrap_pyfunction!(rs_infer_from_bid, m)?)?;
    m.add_function(wrap_pyfunction!(rs_leaf_samples, m)?)?;
    m.add_function(wrap_pyfunction!(rs_card_features, m)?)?;
    m.add_function(wrap_pyfunction!(rs_determinize, m)?)?;
    m.add_function(wrap_pyfunction!(rs_select_trump, m)?)?;
    m.add_function(wrap_pyfunction!(rs_trump_scores, m)?)?;
    m.add_function(wrap_pyfunction!(rs_play_features, m)?)?;
    m.add_function(wrap_pyfunction!(rs_play_log_probs, m)?)?;
    m.add_function(wrap_pyfunction!(rs_belief_pool, m)?)?;
    m.add_function(wrap_pyfunction!(rs_belief_loglik, m)?)?;
    m.add_function(wrap_pyfunction!(rs_belief_marginals, m)?)?;
    m.add_function(wrap_pyfunction!(rs_value_features, m)?)?;
    m.add_function(wrap_pyfunction!(rs_value_eval, m)?)?;
    m.add_function(wrap_pyfunction!(rs_playout_fraction, m)?)?;
    m.add_function(wrap_pyfunction!(rs_belief_features, m)?)?;
    m.add_function(wrap_pyfunction!(rs_belief_log_probs, m)?)?;
    Ok(())
}
