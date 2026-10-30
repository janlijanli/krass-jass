"""Web layer. The game invariants are tested at the engine level (`test_events.py`); what
is left here is the session cookie, which is the only security-relevant code in `web/`."""

import pytest

from web import session as sessions


def test_round_trips_a_session():
    data = {"game_id": "abc123", "seat": 0}
    assert sessions.decode(sessions.encode(data)) == data


def test_rejects_a_tampered_payload():
    """The whole point of signing: a client must not be able to promote itself to another
    seat, or into someone else's game, by editing its own cookie."""
    cookie = sessions.encode({"game_id": "abc123", "seat": 0})
    payload, signature = cookie.rsplit(".", 1)

    from base64 import urlsafe_b64decode, urlsafe_b64encode
    import json

    forged = json.loads(urlsafe_b64decode(payload))
    forged["seat"] = 1
    forged_payload = urlsafe_b64encode(json.dumps(forged, separators=(",", ":")).encode()).decode()

    assert sessions.decode(f"{forged_payload}.{signature}") is None


@pytest.mark.parametrize(
    "cookie", [None, "", "garbage", "a.b", "....", "no-dot", "eyJ9.zzzz"]
)
def test_rejects_malformed_cookies_without_raising(cookie):
    """A malformed cookie is a normal event — a restart rotates the secret — so it must
    return None rather than throw and take the request down."""
    assert sessions.decode(cookie) is None


def test_secret_is_not_hardcoded():
    """A default secret in source is the kind of thing that ships."""
    import inspect

    source = inspect.getsource(sessions)
    assert "token_hex" in source, "the fallback secret must be generated, not literal"


def test_hand_is_sorted_ascending_left_to_right():
    """The engine's rank index runs ace-first, which is backwards for a player looking at
    their own cards. Suits run Kreuz, Ecken, Schaufel, Herz, so red and black alternate."""
    from krass_jass.cards import parse_hand
    from web.app import sorted_hand
    from krass_jass.cards import format_card

    hand = parse_hand("CK C8 SQ S6 HK DK C9 CJ")
    codes = [format_card(c) for c in sorted_hand(hand)]
    assert codes == ["C8", "C9", "CJ", "CK", "DK", "S6", "SQ", "HK"]


def test_a_completed_trick_is_held_until_acknowledged():
    """Four cards appearing and vanishing faster than they can be read is unplayable, and
    the bots must not race ahead while the player is still looking."""
    from krass_jass.cards import card_list
    from krass_jass.game import Game
    from krass_jass.rules import HOUSE
    from web.app import Table, view

    game = Game(cfg=HOUSE, seed=6)
    game.bid(game.to_act, "HEARTS")
    table = Table(game=game, human_seat=0, bots={})

    for _ in range(4):
        seat = game.round.to_play
        game.play(seat, card_list(game.round.legal_moves(seat))[0])

    frame = view(table, 0)
    assert table.awaiting_ack()
    assert frame["trick_complete"] is True
    assert len(frame["trick"]) == 4, "the finished trick must still be on the table"
    assert frame["trick_winner"] is not None
    assert frame["legal"] == [], "no play is offered while the trick is held"

    table.acked_tricks = table.completed_tricks()
    after = view(table, 0)
    assert after["trick_complete"] is False
    assert len(after["trick"]) < 4


def test_hidden_attribute_is_forced_in_css():
    """Regression. `[hidden] { display: none }` lives in the UA stylesheet at the same
    specificity as a class rule, so `.scorecard-backdrop { display: grid }` — written later —
    beat it, and the round scorecard sat over the table with `hidden` set. Any element whose
    class sets `display` needs this rule to make `hidden` mean anything."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "web/static/table.css").read_text()
    assert "[hidden] { display: none !important; }" in css


def test_scorecard_components_reconcile_with_the_round_total():
    """157 is the whole round: 152 in the cards plus 5 for the last trick. Weis, Stöck and
    the match bonus add on top, and the multiplier scales all of it."""
    from krass_jass.agent import GreedyAgent
    from krass_jass.game import Game, Phase
    from krass_jass.rules import HOUSE, Contract

    agent = GreedyAgent()
    for contract in Contract:
        game = Game(cfg=HOUSE, seed=17)
        game.bid(game.to_act, contract.name)
        while game.phase is Phase.PLAYING:
            seat = game.round.to_play
            game.play(seat, agent.decide(game.observation(seat)))

        card = game.last_score
        assert sum(card["trick_points"]) + sum(card["last_trick"]) == 157, contract.name

        raw = sum(
            sum(card[key])
            for key in ("trick_points", "last_trick", "weis", "stoeck", "match")
        )
        assert raw * card["multiplier"] == sum(card["round_total"]), contract.name


def test_the_view_keeps_no_running_point_count():
    """Counting the points taken is what a player is at the table to do. The engine scores
    the round at the end of it; nothing streams a running total to the screen."""
    from krass_jass.cards import card_list
    from krass_jass.game import Game
    from krass_jass.rules import HOUSE
    from web.app import Table, view

    game = Game(cfg=HOUSE, seed=8)
    game.bid(game.to_act, "SPADES")
    table = Table(game=game, human_seat=0, bots={})

    for _ in range(8):
        seat = game.round.to_play
        game.play(seat, card_list(game.round.legal_moves(seat))[0])
    table.acked_tricks = table.completed_tricks()

    frame = view(table, 0)
    for field in ("round_points", "points_in_play", "trick_points"):
        assert field not in frame, f"{field} is back in the view"


def _weis_table():
    from krass_jass.cards import parse_hand as H
    from krass_jass.game import Game
    from krass_jass.rules import HOUSE
    from web.app import Table

    game = Game(cfg=HOUSE, seed=2)
    game._dealt = [
        H("DK DQ DA D9 D8 S6 S7 H6 H7"),   # 20, partner of the winner
        H("SA SK SQ SJ ST S9 S8 H8 H9"),   # 100, beaten
        H("CA CK CQ CJ CT C9 C8 C7 C6"),   # 100 over nine cards — the best
        H("DJ DT D7 D6 HA HK HQ HJ HT"),   # 100, beaten
    ]
    game.forehand = 0
    game.declarer = 0
    game.bid(0, "DIAMONDS")
    return game, Table(game=game, human_seat=0, bots={})


def test_only_the_single_best_weis_is_ever_shown():
    """The winning team scores all of its Weis but only the best one is proved. A partner's
    holding stays private — showing it would give away a hand for no reason."""
    game, table = _weis_table()
    shown = [e for e in game.weis_summary if e["cards"]]
    assert [e["seat"] for e in shown] == [2]
    winners = [e["seat"] for e in game.weis_summary if e["winner"]]
    assert sorted(winners) == [0, 2], "the whole team still scores"


def test_weis_is_called_in_turn_order_through_the_first_trick():
    """Each seat calls its value when its turn comes round, not all at once when the
    contract settles — and a call is a number, never cards."""
    from krass_jass.cards import card_list
    from web.app import visible_weis

    game, table = _weis_table()
    assert visible_weis(table, 0) == [], "nothing is called before a card is played"

    seen = []
    for _ in range(4):
        seat = game.round.to_play
        game.play(seat, card_list(game.round.legal_moves(seat))[0])
        visible = visible_weis(table, 0)
        seen.append([e["seat"] for e in visible])
        if len(game.round.tricks_played) == 0:
            assert all(e["cards"] is None for e in visible), "a call carries no cards"

    # each seat appears only once it has played
    assert seen[0] == [0]
    assert seen[-1] and 2 in seen[-1]


def test_the_best_weis_reveals_its_cards_once_the_calls_are_in():
    from krass_jass.cards import card_list
    from web.app import visible_weis

    game, table = _weis_table()
    for _ in range(4):
        seat = game.round.to_play
        game.play(seat, card_list(game.round.legal_moves(seat))[0])

    assert table.awaiting_ack()
    visible = visible_weis(table, 0)
    with_cards = [e for e in visible if e["cards"]]
    assert [e["seat"] for e in with_cards] == [2]
    assert len(visible) == 4, "everyone's call stays on the table for the comparison"


def test_the_winning_weis_survives_the_first_trick_being_acknowledged():
    """It used to vanish the moment the finished trick was tapped away.

    That pause is one the player taps straight through, so in practice the winning Weis was
    never on screen at all. The engine now offers it for the rest of the round and the client
    decides how long to show it — `renderWeis` gives it the next two tricks.
    """
    from krass_jass.cards import card_list
    from web.app import visible_weis

    game, table = _weis_table()
    for _ in range(4):
        seat = game.round.to_play
        game.play(seat, card_list(game.round.legal_moves(seat))[0])
    table.acked_tricks = table.completed_tricks()

    visible = visible_weis(table, 0)
    assert visible, "the winning Weis has to outlive the tap that clears the trick"
    shown = [e for e in visible if e["cards"]]
    assert [e["seat"] for e in shown] == [2], "only the best Weis ever shows its cards"


def test_a_losing_hand_never_shows_its_cards():
    """The one property that must not move: a call that was beaten is a *value* the table
    heard, never a holding it saw. Checked for the whole round, not just the first trick."""
    from krass_jass.cards import card_list
    from web.app import visible_weis

    game, table = _weis_table()
    for trick in range(4):
        for _ in range(4):
            seat = game.round.to_play
            game.play(seat, card_list(game.round.legal_moves(seat))[0])
        table.acked_tricks = table.completed_tricks()
        for entry in visible_weis(table, 0):
            if not entry.get("best"):
                assert entry["cards"] is None, f"trick {trick}: exposed a hand nobody showed"


def test_stoeck_shows_only_for_the_trick_it_was_announced_in():
    """Weis lives in the first trick; Stöck can fire in any of them, so it gets its own
    display window rather than riding on the Weis one."""
    from krass_jass.agent import GreedyAgent
    from krass_jass.cards import parse_hand as H
    from krass_jass.game import Game, Phase
    from krass_jass.rules import HOUSE
    from web.app import Table, visible_stoeck

    game = Game(cfg=HOUSE, seed=2)
    game._dealt = [
        H("DK DQ DA D9 D8 S6 S7 H6 H7"),
        H("SA SK SQ SJ ST S9 S8 H8 H9"),
        H("CA CK CQ CJ CT C9 C8 C7 C6"),
        H("DJ DT D7 D6 HA HK HQ HJ HT"),
    ]
    game.forehand = 0
    game.declarer = 0
    game.bid(0, "DIAMONDS")
    table = Table(game=game, human_seat=0, bots={})

    agent = GreedyAgent()
    announced_at = None
    windows = []
    while game.phase is Phase.PLAYING:
        seat = game.round.to_play
        game.play(seat, agent.decide(game.observation(seat)))
        table.acked_tricks = table.completed_tricks()
        if game.stoeck_seats and announced_at is None:
            announced_at = game.stoeck_seats[0]["trick"]
        if announced_at is not None and game.round is not None:
            windows.append((len(game.round.tricks_played), len(visible_stoeck(table))))

    assert announced_at is not None, "Stöck was never announced"
    shown = {tricks for tricks, count in windows if count}
    assert shown == {announced_at}, f"shown during {shown}, announced in trick {announced_at}"


def test_settings_are_clamped_to_the_offered_choices():
    """These arrive from a form. A rules engine driven by unvalidated client input is a
    rules engine with no rules."""
    from krass_jass.rules import Contract
    from web.app import build_config

    S = {"mode": "schieber"}
    cfg = build_config({**S, "target": 2500, "weis": False, "mult_undenufe": 1})
    assert cfg.target_score == 2500
    assert cfg.weis_enabled is False
    assert cfg.multiplier(Contract.UNDENUFE) == 1

    # out of range, wrong type and missing all fall back to the documented defaults
    assert build_config({**S, "target": 7}).target_score == 1000
    assert build_config({**S, "target": "2500"}).target_score == 1000
    assert build_config({**S, "mult_hearts": 9}).multiplier(Contract.HEARTS) == 2
    assert build_config({**S, "mult_hearts": 0}).multiplier(Contract.HEARTS) == 2
    assert build_config(S).target_score == 1000


def test_sidi_barrani_to_2000_is_the_default_game():
    """Owner, 2026-09-19: the app opens on Sidi Barrani, played to 2000, and its own scoring
    ignores the Schieber's multipliers and Weis switch whatever the form sends."""
    from krass_jass.rules import Contract
    from web.app import build_config, new_table

    for cfg in (build_config(), build_config({}), new_table().game.cfg):
        assert cfg.sidi and cfg.target_score == 2000
    cfg = build_config({"mode": "sidi", "mult_hearts": 4, "weis": True, "target": 7})
    assert cfg.multiplier(Contract.HEARTS) == 1 and not cfg.weis_enabled
    assert cfg.target_score == 2000


def test_every_contract_multiplier_is_settable_one_to_four():
    from krass_jass.rules import Contract
    from web.app import MULTIPLIER_RANGE, build_config

    for contract in Contract:
        for value in MULTIPLIER_RANGE:
            cfg = build_config({"mode": "schieber", f"mult_{contract.name.lower()}": value})
            assert cfg.multiplier(contract) == value


def test_weis_off_means_no_weis_phase_and_no_weis_points():
    from krass_jass.agent import GreedyAgent
    from krass_jass.game import Game, Phase
    from web.app import build_config

    cfg = build_config({"mode": "schieber", "weis": False})
    agent = GreedyAgent()
    for seed in range(4):
        game = Game(cfg=cfg, seed=seed)
        # drive the bidding properly — forehand may shove, and a shove leaves the phase
        # unchanged rather than starting the round
        while game.phase is Phase.BIDDING:
            seat = game.to_act
            game.bid(seat, agent.select_trump(game.hand_of(seat), seat == game.forehand))
        assert game.phase is not Phase.WEIS, "no prompt when Weis is switched off"
        while game.phase is Phase.PLAYING:
            seat = game.round.to_play
            game.play(seat, agent.decide(game.observation(seat)))
        assert game.last_score["weis"] == [0, 0]


def test_stoeck_is_not_optional():
    """Weis is a choice because announcing reveals a holding. Stöck is announced when the
    second honour is played, which gives away nothing the card did not."""
    import inspect

    from krass_jass import game as game_module

    source = inspect.getsource(game_module.Game.choose_weis)
    assert "stoeck" not in source.lower(), "Stöck must not be routed through the Weis choice"


def test_the_player_is_asked_to_knock_the_moment_an_opponent_bids():
    """Owner, 2026-09-19: the player may double the bid of the seat on their right before their
    partner speaks. The bots wait while the question is open; it is asked once per bid."""
    from krass_jass.game import Game
    from krass_jass.rules import SIDI
    from web.app import Table, view

    for seed in range(40):
        game = Game(cfg=SIDI, seed=seed)
        if game.to_act == 1:
            break
    table = Table(game=game, human_seat=0, bots={})
    assert table.knock_offer() is None
    game.bid(1, "HEARTS 90")                 # Rechts bids; the partner (seat 2) is on turn
    offer = view(table, 0)["knock"]
    assert offer == {"seat": 1, "call": "HEARTS 90"}

    # Letting it pass asks no more for this bid ...
    table.knock_declined = (game.round_index, len(game.auction.calls))
    assert table.knock_offer() is None
    # ... and knocking is a double out of turn, which ends the auction.
    table.knock_declined = None
    game.bid(0, "DOUBLE")
    assert game.doubled and game.declarer == 1
