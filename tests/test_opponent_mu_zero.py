"""The jass-kit request bodies `arena/opponents/mu_zero.py` sends, checked against jass-kit's own
reading of them — written out here from its documented semantics (`next_player = [3, 0, 1, 2]`,
forehand = next_player[dealer], the declarer from the `forehand` flag), importing nothing of theirs.

A stub server in a thread stands in for the opponent, so the HTTP plumbing and the illegal-card
fallback run end to end without TensorFlow.
"""

from __future__ import annotations

import json
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from arena.arena import deal_hands, play_round
from arena.opponents.mu_zero import MuZero, kit_card, kit_seat, observation_body, our_card
from krass_jass.agent import Agent, RandomAgent
from krass_jass.cards import card_list
from krass_jass.rules import EVAL, SHOVE, Contract

NEXT = [3, 0, 1, 2]


def _seat_after(seat: int, k: int) -> int:
    for _ in range(k):
        seat = NEXT[seat]
    return seat


class _Check(Agent):
    """Plays randomly, and checks every body it would have sent against what it knows."""

    def __init__(self, rng):
        self.rng, self.cfg, self.checked = rng, EVAL, 0

    def decide(self, obs) -> int:
        forehand = obs.tricks_played[0][0] if obs.tricks_played else obs.trick_leader
        flag = 1 if obs.declarer_seat == forehand else 0
        body = observation_body(obs.hand, obs.seat, forehand, flag, int(obs.contract),
                                obs.tricks_played, obs.trick, obs.trick_leader)
        dealer = body["dealer"]
        assert NEXT[dealer] == kit_seat(forehand)
        declared = NEXT[dealer] if body["forehand"] == 1 else (NEXT[dealer] + 2) % 4
        assert declared == kit_seat(obs.declarer_seat)
        tricks = body["tricks"]
        assert len(tricks) == len(obs.tricks_played) + 1
        for (lead, cards), t in zip(obs.tricks_played, tricks):
            assert [our_card(c) for c in t["cards"]] == list(cards)
            assert t["first"] == kit_seat(lead)
        nxt = obs.tricks_played[1:] + ((obs.trick_leader, obs.trick),)
        for t, (lead, _) in zip(tricks[:-1], nxt):
            assert t["win"] == kit_seat(lead)    # the winner leads the next trick
        cur = tricks[-1]
        assert _seat_after(cur["first"], len(cur.get("cards", []))) == body["currentPlayer"] == kit_seat(obs.seat)
        assert sum(t["points"] for t in tricks[:-1]) <= 157
        assert sorted(our_card(c) for c in body["player"][kit_seat(obs.seat)]["hand"]) == card_list(obs.hand)
        assert all(not p["hand"] for i, p in enumerate(body["player"]) if i != kit_seat(obs.seat))
        self.checked += 1
        return self.rng.choice(card_list(obs.legal_moves))

    def select_trump(self, hand, is_forehand):
        return SHOVE if is_forehand and self.rng.random() < 0.3 else Contract(self.rng.randrange(6))


def test_cards_round_trip():
    assert all(our_card(kit_card(c)) == c for c in range(36))
    assert kit_card(0) == "DA" and kit_card(4) == "D10" and kit_card(35) == "C6"


@pytest.mark.parametrize("seed", range(20))
def test_bodies_read_back_as_our_state(seed):
    rng = random.Random(seed)
    agent = _Check(rng)
    play_round(deal_hands(rng), None, rng.randrange(4), {s: agent for s in range(4)}, EVAL, seed)
    assert agent.checked == 36


class _Stub(BaseHTTPRequestHandler):
    """Answers a card from the hand it is sent (legal or not), or a random contract."""

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.endswith("action_trump"):
            out = {"trump": 10 if body["forehand"] == -1 else 3}
        else:
            hand = body["player"][body["playerView"]]["hand"]
            out = {"card": hand[0]}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_rounds_against_a_stub_server(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".runs").mkdir()
    srv = HTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        theirs = MuZero(urls=(f"http://127.0.0.1:{srv.server_port}",), error_log=str(tmp_path / "err.log"))
        rng = random.Random(7)
        for _ in range(2):
            hands = deal_hands(rng)
            pts = play_round(hands, None, 0, {0: theirs, 2: theirs, 1: RandomAgent(), 3: RandomAgent()},
                             EVAL, 1)
            assert sum(pts) % 157 == 0   # times the contract multiplier
        # The stub shoves and then names clubs, and plays its first card whether legal or not:
        # whatever it got wrong is logged and replaced, never played.
        log = (tmp_path / "err.log").read_text().splitlines() if (tmp_path / "err.log").exists() else []
        assert all(json.loads(line)["kind"] == "card-illegal" for line in log)
    finally:
        srv.shutdown()
