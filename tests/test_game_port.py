"""The Rust phase machine and event log must match Python's, event for event.

Driving both through the *same* decisions and diffing the whole stream is a stronger check
than comparing final scores: it catches an event emitted in the wrong order, with the wrong
payload, or addressed to the wrong seat — none of which would change the score.
"""

import json
import random

import pytest

from krass_jass.agent import GreedyAgent
from krass_jass.cards import card_list
from krass_jass.deal import deal as py_deal
from krass_jass.game import Game, Phase
from krass_jass.rules import DEFAULT_MULTIPLIERS, HOUSE, SHOVE, Contract

core = pytest.importorskip("krass_jass_core", reason="Rust core not built")

MULTS = [DEFAULT_MULTIPLIERS[Contract(i)] for i in range(6)]

#: Python carries a game_id the Rust engine has no use for — it is transport identity, not
#: game state. Everything else must match exactly.
IGNORED_KEYS = {"game_id"}


def normalise(event: dict) -> dict:
    return {k: v for k, v in event.items() if k not in IGNORED_KEYS}


def py_events(game):
    return [normalise(e.as_dict()) for e in game.log.all()]


def rs_events(game):
    return [normalise(json.loads(e)) for e in game.events()]


# --- the shared deal --------------------------------------------------------


def test_the_deal_is_identical_in_both_implementations():
    """If this drifts, nothing below means anything — and replay stops being true across
    languages, which is the whole reason the algorithm is specified rather than borrowed."""
    for seed in range(300):
        for rnd in range(3):
            assert py_deal(seed, rnd) == core.rs_deal(seed, rnd)


def test_the_deal_is_a_real_deal():
    for seed in range(50):
        hands = py_deal(seed, 0)
        assert sum(bin(h).count("1") for h in hands) == 36
        combined = 0
        for h in hands:
            assert combined & h == 0, "a card was dealt twice"
            combined |= h
        assert combined == (1 << 36) - 1


# --- whole games ------------------------------------------------------------


def assert_table_read_matches(py):
    """The display's table read, both implementations, at every ply of every game.

    It is shown to a player, so a disagreement between the two builds is a disagreement
    about what the cards on the table mean — the sort of thing a player would notice and
    nothing else would catch.
    """
    from krass_jass.awareness import trick_taker

    state = py.round
    contract = int(py.contract)

    assert trick_taker(state.trick, state.leader, py.contract) == core.rs_trick_taker(
        state.trick, state.leader, contract
    ), "trick taker diverged"


def drive_both(seed, target=1000, weis_manual=False, decide=None):
    """Run both engines through the same decisions and return their event streams."""
    py = Game(cfg=HOUSE.variant(target_score=target, weis_manual=weis_manual), seed=seed)
    rs = core.RsGame(seed, target_score=target, weis_manual=weis_manual, multipliers=MULTS)
    agent = GreedyAgent()
    rng = random.Random(seed)

    for _ in range(20000):
        assert py.phase.value == rs.phase, f"phase diverged: {py.phase.value} vs {rs.phase}"
        if py.phase is Phase.GAME_OVER:
            break
        if py.phase is Phase.ROUND_OVER:
            py.next_round()
            rs.next_round()
            continue

        seat = py.to_act
        assert seat == rs.to_act, f"turn diverged at seat {seat} vs {rs.to_act}"
        assert py.hand_of(seat) == rs.hand_of(seat), "hands diverged"

        if py.phase is Phase.BIDDING:
            action = agent.select_trump(py.hand_of(seat), seat == py.forehand)
            py.bid(seat, action)
            rs.bid(seat, -1 if action == SHOVE else int(action))
        elif py.phase is Phase.WEIS:
            announce = rng.random() < 0.6
            py.choose_weis(seat, announce)
            rs.choose_weis(seat, announce)
        else:
            legal = py.round.legal_moves(seat)
            assert legal == rs.legal_moves(seat), "legal moves diverged"
            assert_table_read_matches(py)
            cards = card_list(legal)
            card = cards[rng.randrange(len(cards))]
            py.play(seat, card)
            rs.play(seat, card)
    else:
        raise AssertionError("game did not finish")

    return py, rs


@pytest.mark.parametrize("seed", [1, 7, 42, 1234, 99999])
def test_whole_games_produce_identical_event_streams(seed):
    py, rs = drive_both(seed)
    a, b = py_events(py), rs_events(rs)
    assert len(a) == len(b), f"{len(a)} python events vs {len(b)} rust"
    for i, (x, y) in enumerate(zip(a, b)):
        assert x == y, f"event {i} differs:\n  python {x}\n  rust   {y}"
    assert py.scores == list(rs.scores)


@pytest.mark.parametrize("seed", [3, 88, 4242])
def test_manual_weis_games_also_match(seed):
    """Manual mode adds a phase and can remove a Weis from the contest entirely, which is
    the path most likely to diverge."""
    py, rs = drive_both(seed, weis_manual=True)
    assert py_events(py) == rs_events(rs)
    assert py.scores == list(rs.scores)


def test_per_seat_filtering_matches():
    """The information boundary has to be the same on both sides, or a browser build would
    leak what the server build does not."""
    py, rs = drive_both(11)
    for seat in range(4):
        a = [normalise(e.as_dict()) for e in py.log.for_seat(seat)]
        b = [normalise(json.loads(e)) for e in rs.events_for(seat, 0)]
        assert a == b, f"seat {seat} sees different events"
        # and the only private events are its own deal
        for event in b:
            if event["type"] == "hand_dealt":
                assert event["seat"] == seat


def test_resuming_from_a_sequence_number_matches():
    py, rs = drive_both(5)
    full = py.log.for_seat(0)
    midpoint = full[len(full) // 2].seq
    a = [normalise(e.as_dict()) for e in py.log.for_seat(0, after=midpoint)]
    b = [normalise(json.loads(e)) for e in rs.events_for(0, midpoint)]
    assert a == b


def test_weis_summary_matches():
    py, rs = drive_both(4242, weis_manual=True)
    a = [
        (e["seat"], e["points"], e["cards"], e["winner"], e["best"]) for e in py.weis_summary
    ]
    b = [
        (seat, points, [__import__("krass_jass.cards", fromlist=["x"]).format_card(c) for c in cards]
         if cards is not None else None, winner, best)
        for seat, points, cards, winner, best in rs.weis_summary()
    ]
    assert a == b


def test_stoeck_announcements_match():
    """Timing as well as points: Stöck fires when the second honour is played, so a wrong
    trick index would be a real divergence."""
    for seed in (2, 19, 77, 512):
        py, rs = drive_both(seed)
        a = [(e["seat"], e["points"], e["trick"]) for e in py.stoeck_seats]
        b = [tuple(x) for x in rs.stoeck_announced()]
        assert a == b, f"seed {seed}: python {a}, rust {b}"


def test_the_rust_engine_refuses_out_of_turn_and_illegal_actions():
    rs = core.RsGame(1, target_score=1000)
    with pytest.raises(ValueError):
        rs.bid((rs.to_act + 1) % 4, 1)
    rs.bid(rs.to_act, 1)
    seat = rs.to_act
    with pytest.raises(ValueError):
        rs.play((seat + 1) % 4, card_list(rs.legal_moves(seat))[0])
    illegal = rs.hand_of(seat) ^ rs.legal_moves(seat)
    if illegal:
        with pytest.raises(ValueError):
            rs.play(seat, card_list(illegal)[0])


def test_the_first_round_is_opened_by_whoever_holds_ecken_ten():
    """Who starts a *game* is decided by the cards, not by the seat numbering.

    Seat 0 opening every first round is an artefact of `dealer` defaulting to 3. A table
    settles it with a card instead, and this one uses the Ecken 10. From the second round
    the deal just passes on, so only the first is special — and both engines have to agree,
    because the seat that opens changes who bids and therefore the whole round.
    """
    from krass_jass.cards import card_list
    from krass_jass.deal import deal as deal_hands
    from krass_jass.game import ECKEN_TEN, Game
    from krass_jass.rules import HOUSE

    for seed in range(40):
        hands = deal_hands(seed, 0)
        holder = next(s for s in range(4) if hands[s] & (1 << ECKEN_TEN))

        py = Game(cfg=HOUSE, seed=seed)
        py.start_round()
        assert py.forehand == holder, f"seed {seed}: forehand {py.forehand} != holder {holder}"
        assert ECKEN_TEN in card_list(py.hand_of(py.forehand))

        rs = core.RsGame(seed, target_score=1000, multipliers=MULTS)
        assert rs.forehand == holder, f"seed {seed}: rust disagrees ({rs.forehand})"


def test_only_the_first_round_is_decided_by_the_card():
    """After the first, the deal passes on as it always did — otherwise the same seat would
    open whenever the Ecken 10 happened to land there again."""
    from krass_jass.game import Game
    from krass_jass.rules import HOUSE

    game = Game(cfg=HOUSE, seed=7)
    game.start_round()
    first = game.forehand
    game.round_index = 1
    game.dealer = (game.dealer + 1) % 4
    game.start_round()
    assert game.forehand == (first + 1) % 4, "the rotation stopped rotating"


# --- Sidi Barrani -----------------------------------------------------------


def drive_both_sidi(seed, target=2000):
    """Both engines through the same Sidi game: random calls, doubles and cards."""
    from krass_jass.rules import SIDI

    py = Game(cfg=SIDI.variant(target_score=target), seed=seed)
    rs = core.RsGame(seed, target_score=target, sidi=True)
    rng = random.Random(seed)

    for _ in range(40000):
        assert py.phase.value == rs.phase, f"phase diverged: {py.phase.value} vs {rs.phase}"
        if py.phase is Phase.GAME_OVER:
            break
        if py.phase is Phase.ROUND_OVER:
            py.next_round()
            rs.next_round()
            continue
        seat = py.to_act
        assert seat == rs.to_act, f"turn diverged at seat {seat} vs {rs.to_act}"
        assert py.hand_of(seat) == rs.hand_of(seat), "hands diverged"
        if py.phase is Phase.BIDDING and py.auction.high and rng.random() < 0.08:
            # A knock out of turn, from whichever opponent of the bidder is not on turn.
            bidder = py.auction.high[0]
            knocker = next(s for s in ((bidder + 1) % 4, (bidder + 3) % 4) if s != seat)
            py.bid(knocker, "DOUBLE")
            rs.call(knocker, "DOUBLE")
            continue
        if py.phase is Phase.BIDDING:
            legal = [str(c) for c in py.auction.legal_calls(seat)]
            assert legal == rs.legal_calls(seat), "legal calls diverged"
            call = "PASS" if rng.random() < 0.6 else rng.choice(legal[:14])
            py.bid(seat, call)
            rs.call(seat, call)
        elif py.phase is Phase.DOUBLING:
            answer = rng.random() < 0.25
            py.double(seat, answer)
            rs.double(seat, answer)
        else:
            legal = py.round.legal_moves(seat)
            assert legal == rs.legal_moves(seat), "legal moves diverged"
            cards = card_list(legal)
            card = cards[rng.randrange(len(cards))]
            py.play(seat, card)
            rs.play(seat, card)
        assert (py.bid_value, py.doubled, py.dealer) == (rs.bid_value, rs.doubled, rs.dealer)
    else:
        raise AssertionError("game did not finish")
    return py, rs


@pytest.mark.parametrize("seed", [1, 7, 42, 1234, 99999])
def test_sidi_games_produce_identical_event_streams(seed):
    if not hasattr(core.RsGame, "call"):
        pytest.skip("Rust core predates Sidi")
    py, rs = drive_both_sidi(seed)
    a, b = py_events(py), rs_events(rs)
    assert len(a) == len(b), f"{len(a)} python events vs {len(b)} rust"
    for i, (x, y) in enumerate(zip(a, b)):
        assert x == y, f"event {i} differs:\n  python {x}\n  rust   {y}"
    assert py.scores == list(rs.scores)
    kinds = {e["type"] for e in a}
    assert {"thrown_in", "double_answered", "round_scored", "game_over"} <= kinds
