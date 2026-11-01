"""Coiffeur rules, written from `docs/rules-config.md` ("Coiffeur").

`tests/test_game_port.py` holds Python and Rust to the same event stream; this holds the
Python engine to the rule text.
"""

import random

import pytest

from krass_jass.cards import card_list
from krass_jass.coiffeur import ROW_NAMES, Choice, Choosing, Sheet, multipliers, row_value
from krass_jass.game import Game, Phase
from krass_jass.rules import COIFFEUR, SHOVE, Contract
from krass_jass.state import IllegalMove

FIXED = COIFFEUR.variant(coiffeur_random_multipliers=False)


def play_out(game, rng):
    """Random legal cards to the end of the round."""
    while game.phase in (Phase.PLAYING, Phase.BLOCK):
        seat = game.to_act
        if game.phase is Phase.BLOCK:
            game.choose_block(seat, rng.choice(game.legal_blocks()))
        else:
            game.play(seat, rng.choice(card_list(game.round.legal_moves(seat))))


def test_preset_has_no_weis_no_stoeck_no_target_and_unit_contract_multipliers():
    assert COIFFEUR.coiffeur and not COIFFEUR.sidi
    assert not COIFFEUR.weis_enabled and not COIFFEUR.stoeck_enabled
    assert COIFFEUR.target_score is None
    assert all(COIFFEUR.multiplier(c) == 1 for c in Contract)


def test_multipliers_are_random_by_default_and_fixed_on_request():
    assert COIFFEUR.coiffeur_random_multipliers
    assert multipliers(3, FIXED) == (4, 2, 3, 1, 5, 6, 7, 8, 9, 10, 11, 12)
    eight = FIXED.variant(coiffeur_extra_rows=())
    assert multipliers(3, eight) == (4, 2, 3, 1, 5, 6, 7, 8, 0, 0, 0, 0)
    assert sorted(m for m in multipliers(3, COIFFEUR) if m) == list(range(1, 13))
    # Same seed, same sheet — replay depends on it.
    assert multipliers(3, COIFFEUR) == multipliers(3, COIFFEUR)
    assert multipliers(3, COIFFEUR) != multipliers(4, COIFFEUR) or multipliers(5, COIFFEUR) != multipliers(4, COIFFEUR)


def test_choice_wire_form_round_trips():
    for choice in Sheet().choices(0):
        assert Choice.parse(str(choice)) == choice
    assert str(Choice(Contract.HEARTS, 1)) == "HEARTS"
    assert str(Choice(Contract.OBENABE, 7)) == "OBENABE/JOKER2"
    with pytest.raises(ValueError):
        Choice.parse("HEARTS/OBENABE")      # only a Joker takes a foreign contract


def test_a_fresh_sheet_offers_six_rows_and_two_jokers_of_six():
    assert len(Sheet().choices(0)) == 6 + 2 * 6
    # With the extra rows: two Slaloms, two Guschtis, six 3x3 openings, two Misères.
    assert len(Sheet.for_game(COIFFEUR).choices(0, COIFFEUR)) == 6 + 2 + 2 + 6 + 2 + 2 * 6
    g45 = COIFFEUR.variant(coiffeur_guschti_45=True)
    assert len(Sheet.for_game(g45).choices(0, g45)) == 6 + 2 + 4 + 6 + 2 + 2 * 6
    joker = COIFFEUR.variant(coiffeur_joker_takes_extra=True)
    assert len(Sheet.for_game(joker).choices(0, joker)) == 6 + 12 + 2 * (6 + 12)


def test_shoving_goes_round_the_table_and_forehand_ends_up_in_the_hole():
    choosing = Choosing(forehand=1, sheet=Sheet())
    seats = []
    for _ in range(4):
        seats.append(choosing.chooser)
        choosing.act(choosing.chooser, SHOVE)
    # To the next seat — an opponent, not the partner — and back to forehand.
    assert seats == [1, 2, 3, 0]
    assert choosing.chooser == 1
    assert SHOVE not in choosing.legal()
    with pytest.raises(ValueError):
        choosing.act(1, SHOVE)


def test_once_a_team_is_done_only_the_other_chooses_and_shoves_to_the_partner_and_back():
    sheet = Sheet()
    sheet.written[0] = [100] * 8
    choosing = Choosing(forehand=0, sheet=sheet)      # forehand's team is finished
    assert choosing.chooser == 1
    choosing.act(1, SHOVE)
    assert choosing.chooser == 3
    choosing.act(3, SHOVE)
    assert choosing.chooser == 1
    assert SHOVE not in choosing.legal()


def test_a_played_row_is_closed_but_its_contract_can_still_go_to_a_joker():
    sheet = Sheet()
    sheet.written[1][Contract.HEARTS] = 80
    choices = sheet.choices(1)
    assert Choice(Contract.HEARTS, 1) not in choices
    assert Choice(Contract.HEARTS, 6) in choices
    # The other team's column is its own.
    assert Choice(Contract.HEARTS, 1) in sheet.choices(0)


def test_the_chooser_leads_and_only_the_choosing_team_writes():
    game = Game(cfg=FIXED, seed=11)
    chooser = game.to_act
    game.bid(chooser, SHOVE)
    second = game.to_act
    assert second == (chooser + 1) % 4
    game.bid(second, "OBENABE")
    assert game.round.leader == second
    play_out(game, random.Random(0))

    team = second % 2
    points = game.last_score["round_total"]
    assert sum(points) in (157, 257)
    tens = (points[team] + 5) // 10
    assert game.last_score["written"][team] == tens * 5     # Obenabe is x5 in the table
    assert game.last_score["written"][1 - team] == 0
    assert game.scores[1 - team] == 0
    assert game.sheet.written[team][Contract.OBENABE] == tens


def test_points_are_written_in_tens_rounded_half_up_or_in_full_on_request():
    assert [row_value(p, COIFFEUR) for p in (0, 4, 5, 84, 85, 157, 257)] == [0, 0, 1, 8, 9, 16, 26]
    full = COIFFEUR.variant(coiffeur_tens=False)
    assert row_value(85, full) == 85


def test_score_opponents_credits_the_defenders_at_the_rows_multiplier():
    game = Game(cfg=FIXED.variant(coiffeur_score_opponents=True), seed=11)
    seat = game.to_act
    game.bid(seat, "CLUBS")                 # x1 in the table
    play_out(game, random.Random(1))
    points = game.last_score["round_total"]
    assert game.scores == [(p + 5) // 10 for p in points]
    # ...but only the choosing team's row is filled.
    assert game.sheet.written[1 - seat % 2] == [None] * 12


def test_illegal_choices_are_refused():
    game = Game(cfg=FIXED, seed=5)
    seat = game.to_act
    with pytest.raises(IllegalMove):
        game.bid((seat + 1) % 4, "HEARTS")          # not on turn
    with pytest.raises(IllegalMove):
        game.bid(seat, "HEARTS/UNDENUFE")


@pytest.mark.parametrize("extra,rounds", [((), 16), (("SLALOM", "GUSCHTI"), 20), (None, 24)])
def test_a_game_is_two_rounds_a_row_and_ends_with_the_sheet(extra, rounds):
    rng = random.Random(9)
    cfg = COIFFEUR if extra is None else COIFFEUR.variant(coiffeur_extra_rows=extra)
    game = Game(cfg=cfg, seed=9)
    played = 0
    while game.phase is not Phase.GAME_OVER:
        if game.phase is Phase.ROUND_OVER:
            game.next_round()
        while game.phase is Phase.BIDDING:
            game.bid(game.to_act, rng.choice(game.legal_choices()))
        play_out(game, rng)
        played += 1
    assert played == rounds
    assert game.sheet.complete
    total = [
        sum(p * m for p, m in zip(game.sheet.written[t], game.row_multipliers) if p is not None)
        for t in (0, 1)
    ]
    assert total == game.scores
    over = game.log.all()[-1]
    assert over.payload["decided_by"] == "sheet"
    assert over.payload["winner"] == (-1 if total[0] == total[1] else int(total[1] > total[0]))


def test_row_names_cover_the_sheet():
    assert ROW_NAMES[:6] == tuple(c.name for c in Contract)
    assert ROW_NAMES[8:] == ("SLALOM", "GUSCHTI", "TRIO", "MISERE")


# --- the extra rows: a card order per trick ---------------------------------

from krass_jass.cards import SUIT_MASK  # noqa: E402
from krass_jass.schedule import block_options, for_row, guschti, misere, parse, slalom, trio  # noqa: E402
from krass_jass.state import RoundState  # noqa: E402
from krass_jass.tables import CARD_VALUES  # noqa: E402
from krass_jass.voids import infer_forbidden  # noqa: E402

O, U = Contract.OBENABE, Contract.UNDENUFE


def test_schedules_are_what_their_names_say():
    assert slalom(U).tricks == (U, O, U, O, U, O, U, O, U)
    assert guschti(O).tricks == (O,) * 5 + (U,) * 4
    assert guschti(U, 4).tricks == (U,) * 4 + (O,) * 5
    assert trio(U).tricks == (U,) * 3 + (None,) * 6 and trio(U).is_open
    assert misere(O).tricks == (O,) * 9 and misere(O).misere
    for row in ("SLALOM", "GUSCHTI", "TRIO", "MISERE"):
        for schedule in for_row(row, COIFFEUR.variant(coiffeur_guschti_45=True)):
            assert parse(schedule.name) == schedule and schedule.row == row
    for bad in ("SLALOM_HEARTS", "GUSCHTI_CLUBS", "TRIO_HEARTS_TOU", "MISERE_SPADES", "TRIO"):
        with pytest.raises(ValueError):
            parse(bad)
    choice = Choice.parse("TRIO_SPADES")
    assert choice.row == ROW_NAMES.index("TRIO") and choice.contract is Contract.SPADES
    with pytest.raises(ValueError):
        Choice.parse("SLALOM_OBENABE/SLALOM")


def deal_round(schedule, seed=4):
    from krass_jass.deal import deal

    return RoundState(
        contract=schedule.count, hands=list(deal(seed, 0)), cfg=COIFFEUR, leader=0,
        schedule=schedule.tricks,
    )


def test_each_trick_is_played_in_its_own_order_and_counted_in_the_first():
    """A 3x3 opened Undenufe, then hearts trump, then Obenabe: the first three tricks go to the
    lowest card, the middle three are hearts trump (trumping allowed, the Puur on top), the last
    three go to the highest. All nine are counted as Undenufe."""
    rng = random.Random(2)
    plan = (U,) * 3 + (Contract.HEARTS,) * 3 + (O,) * 3
    for seed in range(40):
        st = deal_round(trio(U), seed)
        for t in range(9):
            if t in (3, 6):
                assert st.block_pending
                with pytest.raises(IllegalMove):
                    st.play(card_list(st.hands[st.to_play])[0])
                st.set_block(plan[t])
            assert st.trick_contract is plan[t]
            while len(st.tricks_played) == t:
                seat = st.to_play
                legal = st.legal_moves(seat)
                if st.trick and st.trick_contract.trump_suit < 0:
                    # No trump this trick: follow suit if you can, and nothing else.
                    follow = st.hands[seat] & SUIT_MASK[st.led_suit]
                    assert legal == (follow or st.hands[seat])
                st.play(rng.choice(card_list(legal)))
        values = CARD_VALUES[U]
        total = sum(values[c] for _, cards in st.tricks_played for c in cards)
        assert sum(st.trick_points) == total == 152


def test_the_three_blocks_hold_a_trump_suit_and_obenabe_or_undenufe():
    """Any contract for the second block; the third is forced when the first two left one out
    (owner, 2026-10-31). The suit may change from block to block."""
    six = list(Contract)
    suits = [c for c in Contract if c.is_trump]
    def blocks(a, b):
        return block_options((a,) * 3 + (b,) * 3 + (None,) * 3, 6)
    assert block_options((O,) * 3 + (None,) * 6, 3) == six
    assert blocks(O, U) == suits
    assert blocks(Contract.HEARTS, Contract.CLUBS) == [O, U]
    assert blocks(Contract.HEARTS, O) == six
    assert block_options((O,) * 9, 3) == []


def test_the_leaders_of_tricks_4_and_7_name_the_blocks_in_the_game():
    rng = random.Random(1)
    for seed in range(20):
        game = Game(cfg=COIFFEUR, seed=seed)
        game.bid(game.to_act, "TRIO_OBENABE")
        while game.phase is not Phase.ROUND_OVER and game.phase is not Phase.GAME_OVER:
            if game.phase is Phase.BLOCK:
                t = len(game.round.tricks_played)
                assert t in (3, 6) and game.to_act == game.round.leader
                with pytest.raises(IllegalMove):
                    game.choose_block((game.to_act + 1) % 4, "HEARTS")
                game.choose_block(game.to_act, rng.choice(game.legal_blocks()))
                event = game.log.all()[-1]
                assert event.type.value == "block_chosen" and event.payload["trick"] == t + 1
            else:
                seat = game.to_act
                game.play(seat, rng.choice(card_list(game.round.legal_moves(seat))))
        tricks = game.round.schedule
        assert any(c.is_trump for c in tricks) and any(not c.is_trump for c in tricks)
        assert all(tricks[b] == tricks[b + 1] == tricks[b + 2] for b in (0, 3, 6))


def test_a_misere_credits_each_team_with_what_the_other_took():
    game = Game(cfg=FIXED, seed=6)
    seat = game.to_act
    game.bid(seat, "MISERE_UNDENUFE")
    assert game.observation(game.to_act).misere
    play_out(game, random.Random(4))
    team = seat % 2
    taken = game.last_score["round_total"]
    assert game.sheet.written[team][ROW_NAMES.index("MISERE")] == (taken[1 - team] + 5) // 10
    assert game.last_score["written"][team] == (taken[1 - team] + 5) // 10 * 12


def test_a_slalom_trick_goes_to_the_highest_then_the_lowest():
    st = deal_round(slalom(O), seed=11)
    for t in range(2):
        leader = st.leader
        cards = []
        for _ in range(4):
            seat = st.to_play
            card = card_list(st.legal_moves(seat))[0]
            cards.append(card)
            st.play(card)
        led = cards[0] // 9
        followers = [(i, c) for i, c in enumerate(cards) if c // 9 == led]
        # Rank 0 is the ace: Obenabe takes the lowest index, Undenufe the highest.
        pick = min if t == 0 else max
        best = pick(followers, key=lambda ic: ic[1] % 9)[0]
        assert st.tricks_played[t] == (leader, tuple(cards))
        assert st.last_trick_winner == (leader + best) % 4


def test_void_inference_reads_each_trick_in_its_own_order():
    """A heart thrown on a spade lead proves a spade void in an Obenabe trick — and proves
    nothing in a hearts-trump trick, where trumping is always allowed."""
    spade, heart = 2 * 9 + 5, 1 * 9 + 5
    trick = ((0, (spade, heart, spade + 1, spade + 2)),)
    obenabe = infer_forbidden(list(trick), [], 0, Contract.HEARTS, COIFFEUR, (O,) + (Contract.HEARTS,) * 8)
    trumped = infer_forbidden(list(trick), [], 0, Contract.HEARTS, COIFFEUR, (Contract.HEARTS,) * 9)
    assert obenabe[1] & SUIT_MASK[2] == SUIT_MASK[2]
    assert trumped[1] == 0


def test_a_scheduled_round_runs_in_the_game_and_the_event_says_so():
    game = Game(cfg=FIXED, seed=8)
    seat = game.to_act
    game.bid(seat, "GUSCHTI_UNDENUFE")
    event = game.log.all()[-1]
    assert event.payload["schedule"] == "GUSCHTI_UNDENUFE"
    assert event.payload["tricks"] == ["UNDENUFE"] * 5 + ["OBENABE"] * 4
    assert event.payload["multiplier"] == 10 and event.payload["row"] == "GUSCHTI"
    assert game.contract is U and game.round.trick_contract is U
    obs = game.observation(game.to_act)
    assert obs.schedule == (int(U),) * 5 + (int(O),) * 4 and obs.trick_contract is U
    play_out(game, random.Random(0))
    assert game.sheet.written[seat % 2][ROW_NAMES.index("GUSCHTI")] is not None


# --- the rule-based choice --------------------------------------------------

from krass_jass.cards import parse_card  # noqa: E402
from krass_jass.coiffeur_select import choose, value_choices  # noqa: E402


def hand(*codes):
    out = 0
    for code in codes:
        out |= 1 << parse_card(code)
    return out


def test_the_selector_always_returns_something_legal():
    rng = random.Random(3)
    for seed in range(30):
        game = Game(cfg=COIFFEUR, seed=seed)
        while game.phase is not Phase.GAME_OVER:
            if game.phase is Phase.ROUND_OVER:
                game.next_round()
            while game.phase is Phase.BIDDING:
                legal = game.legal_choices()
                action = choose(game.hand_of(game.to_act), legal, game.row_multipliers, COIFFEUR)
                assert action in legal
                game.bid(game.to_act, action)
            play_out(game, rng)


def test_a_monster_trump_hand_goes_into_the_dearest_row_that_takes_it():
    monster = hand("HJ", "H9", "HA", "HK", "HQ", "HT", "H8", "S6", "D7")
    mults = (1, 3, 2, 4, 5, 6, 7, 8)        # hearts x3, the Jokers x7 and x8
    choice = choose(monster, Sheet().choices(0) + [SHOVE], mults, COIFFEUR)
    assert choice == Choice(Contract.HEARTS, 7)


def test_a_weak_hand_shoves_when_it_may_and_chooses_when_it_must():
    # Queens and tens: no Puur, no Nell, no aces, no sixes — nothing in any contract.
    weak = hand("DQ", "DT", "HQ", "HT", "SQ", "ST", "CQ", "CT", "DK")
    legal = Sheet().choices(0)
    assert choose(weak, legal + [SHOVE], COIFFEUR.coiffeur_multipliers, COIFFEUR) == SHOVE
    forced = choose(weak, legal, COIFFEUR.coiffeur_multipliers, COIFFEUR)
    assert forced in legal
    # Forced, it spends the cheapest row it can rather than a dear one.
    values = value_choices(weak, legal, COIFFEUR.coiffeur_multipliers, COIFFEUR)
    assert values[forced] == max(values.values())


def test_the_search_plays_every_extra_row_game_legally():
    """The search reads each trick's order (`rust/src/rollout.rs`, `Kernel::at`): it must never
    propose a card the engine refuses, through the order changes of all three extra rows."""
    from krass_jass.agent import DmctsAgent

    agent = DmctsAgent(determinizations=4, iterations=60, cfg=COIFFEUR, label="t")
    for seed, name in enumerate(("SLALOM_UNDENUFE", "GUSCHTI_OBENABE", "TRIO_HEARTS", "TRIO_OBENABE", "MISERE_OBENABE")):
        game = Game(cfg=COIFFEUR, seed=seed)
        game.bid(game.to_act, name)
        while game.phase in (Phase.PLAYING, Phase.BLOCK):
            seat = game.to_act
            if game.phase is Phase.BLOCK:
                game.choose_block(seat, agent.coiffeur_block(game.hand_of(seat), game.legal_blocks()))
                continue
            obs = game.observation(seat)
            card = agent.decide(obs)
            assert game.round.legal_moves(seat) & (1 << card)
            game.play(seat, card)
        assert game.last_score["row"] == Choice.parse(name).schedule.row


def test_void_inference_per_trick_agrees_with_rust():
    """Both implementations read each trick under its own trump, over random scheduled rounds."""
    core = pytest.importorskip("krass_jass_core")
    rng = random.Random(17)
    schedules = [s for row in ("SLALOM", "GUSCHTI", "TRIO", "MISERE") for s in for_row(row, COIFFEUR)]
    for seed in range(60):
        schedule = rng.choice(schedules)
        st = deal_round(schedule, seed)
        while not st.done:
            if st.block_pending:
                st.set_block(rng.choice(st.block_options()))
            st.play(rng.choice(card_list(st.legal_moves())))
            py = infer_forbidden(st.tricks_played, st.trick, st.leader, st.contract, COIFFEUR, st.schedule)
            rs = core.rs_infer_forbidden(
                [(l, list(c)) for l, c in st.tricks_played], list(st.trick), st.leader,
                st.contract.trump_suit, True, [c.trump_suit if c is not None else -1 for c in st.schedule],
            )
            assert py == list(rs)
