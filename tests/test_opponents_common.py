"""Our side of the opponent harness (`arena/opponents/common.py`). No opponent code runs here."""

from arena.arena import deal_spec, double_round
from arena.opponents.common import (
    challenge_history, ch_card, ch_game_type, double_round_logged, our_card_ch, our_contract_ch,
    trumpf_history,
)
from krass_jass.agent import GreedyAgent, RandomAgent
from krass_jass.cards import card_list
from krass_jass.rules import EVAL, SHOVE, Contract


def test_card_and_contract_round_trip():
    assert all(our_card_ch(ch_card(c)) == c for c in range(36))
    assert all(our_contract_ch(ch_game_type(Contract(k))) == Contract(k) for k in range(6))
    assert our_contract_ch({"mode": "SCHIEBE"}) == SHOVE
    assert ch_card(0)["number"] == 14 and ch_card(8)["number"] == 6  # Ace high, six low


class Recorder(RandomAgent):
    def decide(self, obs):
        h = challenge_history(obs, "us", "them")
        dealt = h[0]["data"]
        assert h[0]["type"] == "DEAL_CARDS" and len(dealt) == 9
        held = {our_card_ch(c) for c in dealt}
        assert set(card_list(obs.hand)) <= held
        assert h[-1] == {"type": "REQUEST_CARD", "data": [ch_card(c) for c in obs.trick]}
        stiche = [m for m in h if m["type"] == "BROADCAST_STICH"]
        assert len(stiche) == len(obs.tricks_played)
        played = [m for m in h if m["type"] == "PLAYED_CARDS"]
        assert len(played) == 4 * len(obs.tricks_played) + len(obs.trick)
        return super().decide(obs)


def test_logged_double_round_matches_the_arena_and_histories_are_whole():
    for i in range(5):
        hands, _, leader, seed = deal_spec(7, i, None)
        a, b = GreedyAgent(), Recorder()
        rec = double_round_logged(hands, leader, a, b, EVAL, seed)
        ref, _ = double_round(hands, None, leader, a, b, EVAL, seed)
        assert rec["share"] == ref
        for half in rec["halves"]:
            assert half["ours"] + half["theirs"] == sum(half["points"])


def test_trumpf_history_marks_a_shove():
    assert [m["type"] for m in trumpf_history(0x1FF, True)] == ["DEAL_CARDS", "REQUEST_TRUMPF"]
    msgs = trumpf_history(0x1FF, False)
    assert msgs[1] == {"type": "BROADCAST_TRUMPF", "data": {"mode": "SCHIEBE"}}
    assert msgs[-1] == {"type": "REQUEST_TRUMPF", "data": True}


def test_pyschieber_vocabulary_round_trips():
    from arena.opponents.pyschieber import our_card_ps, our_trumpf_ps, ps_card, ps_trumpf

    assert all(our_card_ps(ps_card(c)) == c for c in range(36))
    assert all(our_trumpf_ps(ps_trumpf(Contract(k))) == Contract(k) for k in range(6))
    assert our_trumpf_ps("SCHIEBEN") == SHOVE
    assert ps_card(0) == "<ROSE:Ass>" and ps_card(3) == "<ROSE:Under>" and ps_card(8) == "<ROSE:6>"
