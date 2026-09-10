"""The event log is what the browser sees, so it is the second place hidden state can leak.

`build_observation` guards what a *bot* sees; this guards what a *client* sees. Both need
their own test, because they are different code paths carrying different payloads.
"""

import random

import pytest

from krass_jass.agent import GreedyAgent
from krass_jass.cards import parse_card
from krass_jass.events import EventType
from krass_jass.game import Game, Phase
from krass_jass.rules import HOUSE
from krass_jass.state import IllegalMove

CARD_BEARING = {"cards", "card"}


def cards_in(event) -> set[int]:
    found = set()
    for key in CARD_BEARING:
        value = event.payload.get(key)
        if isinstance(value, str):
            found.add(parse_card(value))
        elif isinstance(value, list):
            found.update(parse_card(c) for c in value)
    return found


def play_out(game: Game, agent=None, max_steps: int = 20000) -> None:
    agent = agent or GreedyAgent()
    for _ in range(max_steps):
        if game.phase is Phase.GAME_OVER:
            return
        if game.phase is Phase.ROUND_OVER:
            game.next_round()
            continue
        seat = game.to_act
        if game.phase is Phase.BIDDING:
            game.bid(seat, agent.select_trump(game.hand_of(seat), seat == game.forehand))
        else:
            game.play(seat, agent.decide(game.observation(seat)))
    raise AssertionError("game did not finish")


def test_a_seat_never_sees_a_card_it_should_not():
    """The core invariant, at the transport layer. Walk everything each seat receives and
    check every card against what that seat legitimately knows."""
    for seed in range(6):
        game = Game(cfg=HOUSE.variant(target_score=1000), seed=seed)
        dealt_per_round = []

        # capture each round's deal as it happens, since hands empty as they are played
        original = game.start_round

        play_out(game)

        for seat in range(4):
            known: set[int] = set()
            for event in game.log.for_seat(seat):
                if event.type is EventType.HAND_DEALT:
                    assert event.private_to == seat
                    known |= cards_in(event)
                    continue
                if event.type in (EventType.CARD_PLAYED, EventType.TRICK_WON,
                                  EventType.WEIS_DECLARED):
                    # public by the rules: played cards and announced Weis
                    known |= cards_in(event)
                    continue
                assert not cards_in(event), (
                    f"event {event.type} carries card identifiers but is not a "
                    f"recognised card-bearing public event"
                )


def test_only_hand_dealt_is_private():
    game = Game(cfg=HOUSE.variant(target_score=1000), seed=3)
    play_out(game)
    for event in game.log.all():
        if event.private_to is not None:
            assert event.type is EventType.HAND_DEALT


def test_a_seat_receives_only_its_own_deal():
    game = Game(seed=11)
    for seat in range(4):
        deals = [e for e in game.log.for_seat(seat) if e.type is EventType.HAND_DEALT]
        assert len(deals) == 1
        assert deals[0].payload["seat"] == seat


def test_replay_from_a_sequence_number():
    """Reconnection is just this: send the last seq you saw, get what you missed."""
    game = Game(cfg=HOUSE.variant(target_score=1000), seed=5)
    play_out(game)
    full = game.log.for_seat(0)
    midpoint = full[len(full) // 2].seq
    resumed = game.log.for_seat(0, after=midpoint)
    assert [e.seq for e in resumed] == [e.seq for e in full if e.seq > midpoint]


def test_games_replay_bit_for_bit():
    a = Game(cfg=HOUSE.variant(target_score=1000), seed=99)
    b = Game(cfg=HOUSE.variant(target_score=1000), seed=99)
    play_out(a)
    play_out(b)
    assert [e.as_dict() for e in a.log.all()] == [e.as_dict() for e in b.log.all()]
    assert a.scores == b.scores


def test_out_of_turn_and_illegal_actions_are_refused():
    game = Game(seed=1)
    off_turn = (game.to_act + 1) % 4
    with pytest.raises(IllegalMove):
        game.bid(off_turn, "HEARTS")
    game.bid(game.to_act, "HEARTS")

    seat = game.to_act
    with pytest.raises(IllegalMove):
        game.play((seat + 1) % 4, 0)
    illegal = game.round.hands[seat] ^ game.round.legal_moves(seat)
    if illegal:
        from krass_jass.cards import card_list

        with pytest.raises(IllegalMove):
            game.play(seat, card_list(illegal)[0])


def test_scores_accumulate_and_the_game_ends_at_the_target():
    game = Game(cfg=HOUSE.variant(target_score=1000), seed=21)
    play_out(game)
    assert game.phase is Phase.GAME_OVER
    assert max(game.scores) >= 1000
    over = [e for e in game.log.all() if e.type is EventType.GAME_OVER]
    assert len(over) == 1
    assert over[0].payload["scores"] == game.scores


@pytest.mark.parametrize("action", ["HEARTS", "hearts", " Hearts "])
def test_bids_accept_contract_names_from_the_wire(action):
    """Clients send names, and Contract is an IntEnum, so Contract("HEARTS") raises.
    Parsing belongs in the engine, not scattered through the transport layer."""
    from krass_jass.rules import Contract

    game = Game(seed=1)
    game.bid(game.to_act, action)
    assert game.contract is Contract.HEARTS


def test_nonsense_bids_are_rejected():
    game = Game(seed=1)
    for bad in ("TRUMP", "", "HEART", "42"):
        with pytest.raises(IllegalMove):
            game.bid(game.to_act, bad)


def test_diamonds_is_not_treated_as_no_trump():
    """Regression. Contract.DIAMONDS == 0, so `if contract:` is falsy — which silently made
    every diamonds round behave as a no-trump one: no Stöck, wrong Weis tie-break."""
    from krass_jass.cards import parse_hand as H
    from krass_jass.rules import Contract, HOUSE
    from krass_jass.weis import STOECK_POINTS

    game = Game(cfg=HOUSE, seed=2)
    # force a known deal where seat 0 holds the diamond King and Queen
    game._dealt = [
        H("DK DQ DA D9 D8 S6 S7 H6 H7"),
        H("SA SK SQ SJ ST S9 S8 H8 H9"),
        H("CA CK CQ CJ CT C9 C8 C7 C6"),
        H("DJ DT D7 D6 HA HK HQ HJ HT"),
    ]
    game.forehand = 0
    game.declarer = 0
    game.bid(0, "DIAMONDS")

    assert game.contract is Contract.DIAMONDS
    assert game._stoeck[0] == STOECK_POINTS, "K+Q of trumps must score Stöck in diamonds"


def test_every_contract_reports_itself_in_the_view():
    """The same falsy-enum trap, at the transport layer."""
    from web.app import Table, view
    from krass_jass.rules import Contract, HOUSE

    for contract in Contract:
        game = Game(cfg=HOUSE, seed=4)
        game.bid(game.to_act, contract.name)
        table = Table(game=game, human_seat=0, bots={})
        assert view(table, 0)["contract"] == contract.name


def test_a_losing_teams_weis_cards_are_never_revealed():
    """Real Schieber announces in two stages: everyone calls a value, only the winning team
    shows cards. That staging is what keeps three hands secret at the top of every round,
    so it is an information-boundary rule, not a presentational one."""
    from krass_jass.cards import parse_card, parse_hand as H
    from krass_jass.events import EventType
    from krass_jass.rules import HOUSE
    from krass_jass.scoring import team_of

    game = Game(cfg=HOUSE, seed=2)
    game._dealt = [
        H("DK DQ DA D9 D8 S6 S7 H6 H7"),
        H("SA SK SQ SJ ST S9 S8 H8 H9"),   # a 7-run: announces, but loses
        H("CA CK CQ CJ CT C9 C8 C7 C6"),   # a 9-run: wins
        H("DJ DT D7 D6 HA HK HQ HJ HT"),
    ]
    game.forehand = 0
    game.declarer = 0
    game.bid(0, "DIAMONDS")

    resolved = [e for e in game.log.all() if e.type is EventType.WEIS_RESOLVED]
    assert len(resolved) == 1
    winning_team = resolved[0].payload["team"]

    announced = [e for e in game.log.all() if e.type is EventType.WEIS_ANNOUNCED]
    assert len(announced) == 4, "every seat holding a Weis calls its value"
    assert all("cards" not in e.payload for e in announced), "a call carries no cards"

    for event in game.log.all():
        if event.type is EventType.WEIS_DECLARED:
            assert team_of(event.payload["seat"]) == winning_team, (
                "a losing team's Weis cards were revealed"
            )

    for entry in game.weis_summary:
        if team_of(entry["seat"]) != winning_team:
            assert entry["cards"] is None


def test_stoeck_is_announced_when_the_second_honour_is_played():
    """Not at the top of the round. The timing is information — holding both trump honours
    is worth knowing, and a real player chooses when to reveal it."""
    from krass_jass.cards import card_list, parse_card, parse_hand as H
    from krass_jass.events import EventType
    from krass_jass.rules import HOUSE

    game = Game(cfg=HOUSE, seed=2)
    game._dealt = [
        H("DK DQ DA D9 D8 S6 S7 H6 H7"),   # holds the diamond King and Queen
        H("SA SK SQ SJ ST S9 S8 H8 H9"),
        H("CA CK CQ CJ CT C9 C8 C7 C6"),
        H("DJ DT D7 D6 HA HK HQ HJ HT"),
    ]
    game.forehand = 0
    game.declarer = 0
    game.bid(0, "DIAMONDS")

    def stoeck_events():
        return [e for e in game.log.all() if e.type is EventType.STOECK]

    assert stoeck_events() == [], "nothing is announced before a card is played"

    dk, dq = parse_card("DK"), parse_card("DQ")
    seen_first = False
    while game.phase is Phase.PLAYING:
        seat = game.round.to_play
        card = card_list(game.round.legal_moves(seat))[0]
        was_honour = seat == 0 and card in (dk, dq)
        held_before = game.round.hands[0]
        game.play(seat, card)

        if was_honour:
            from krass_jass.tables import STOECK_MASK

            remaining = held_before & ~(1 << card) & STOECK_MASK[0]
            if remaining:
                assert stoeck_events() == [], "the first honour announces nothing"
                seen_first = True
            else:
                assert len(stoeck_events()) == 1, "the second honour announces"
                break

    assert seen_first, "the test never saw the first honour played"
    assert len(stoeck_events()) == 1
    assert stoeck_events()[0].payload["seat"] == 0
    assert stoeck_events()[0].payload["points"] == 20


def test_stoeck_still_scores_wherever_it_is_announced():
    from krass_jass.agent import GreedyAgent
    from krass_jass.cards import parse_hand as H
    from krass_jass.rules import HOUSE

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
    agent = GreedyAgent()
    while game.phase is Phase.PLAYING:
        seat = game.round.to_play
        game.play(seat, agent.decide(game.observation(seat)))
    assert game.last_score["stoeck"] == [20, 0]


def test_no_stoeck_event_in_a_no_trump_contract():
    game = Game(seed=2)
    game.bid(game.to_act, "OBENABE")
    from krass_jass.events import EventType

    assert not [e for e in game.log.all() if e.type is EventType.STOECK]


def test_manual_weis_lets_a_holder_decline():
    """Announcing tells the table what you hold, so declining is a real choice. A declined
    Weis is not merely hidden — it leaves the contest, so it cannot win for its team."""
    from krass_jass.cards import parse_hand as H
    from krass_jass.rules import HOUSE

    cfg = HOUSE.variant(weis_manual=True)
    game = Game(cfg=cfg, seed=2)
    game._dealt = [
        H("DK DQ DA D9 D8 S6 S7 H6 H7"),   # 20
        H("SA SK SQ SJ ST S9 S8 H8 H9"),   # 100
        H("CA CK CQ CJ CT C9 C8 C7 C6"),   # 100, the best — and it will decline
        H("DJ DT D7 D6 HA HK HQ HJ HT"),   # 100
    ]
    game.forehand = 0
    game.declarer = 0
    game.bid(0, "DIAMONDS")

    assert game.phase is Phase.WEIS
    assert set(game.weis_offers) == {0, 1, 2, 3}

    game.choose_weis(0, True)
    game.choose_weis(1, True)
    game.choose_weis(2, False)
    game.choose_weis(3, True)

    assert game.phase is Phase.PLAYING
    # seat 2 declining hands the Weis to the other team entirely
    assert game._weis == (0, 200)
    assert 2 not in [entry["seat"] for entry in game.weis_summary]


def test_declining_is_not_announced_at_all():
    from krass_jass.cards import parse_hand as H
    from krass_jass.events import EventType
    from krass_jass.rules import HOUSE

    cfg = HOUSE.variant(weis_manual=True)
    game = Game(cfg=cfg, seed=2)
    game._dealt = [
        H("DK DQ DA D9 D8 S6 S7 H6 H7"),
        H("SA SK SQ SJ ST S9 S8 H8 H9"),
        H("CA CK CQ CJ CT C9 C8 C7 C6"),
        H("DJ DT D7 D6 HA HK HQ HJ HT"),
    ]
    game.forehand = 0
    game.declarer = 0
    game.bid(0, "DIAMONDS")
    for seat in (0, 1, 3):
        game.choose_weis(seat, False)
    game.choose_weis(2, True)

    announced = [e.payload["seat"] for e in game.log.all() if e.type is EventType.WEIS_ANNOUNCED]
    assert announced == [2], "a declined Weis must not be announced"


def test_automatic_weis_still_skips_the_prompt():
    game = Game(seed=2)
    game.bid(game.to_act, "HEARTS")
    assert game.phase is Phase.PLAYING
