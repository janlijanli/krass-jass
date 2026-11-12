"""Our bot against JassFormer (github.com/jberclaz/jass, MIT), double rounds, paired test.

JassFormer is a 4.8M-parameter transformer (6 layers, d=256) that reads a 96-token view of the
game and outputs card logits (36) and trump logits (4 suits + pass). It was trained by imitating
a Monte Carlo player and then by two rounds of PPO self-play; `jassformer-v2` is the network their
client ships. It plays one forward pass per decision, no search.

How it is seated. Their client runs the network from Java (ONNX Runtime). We do not run any of
their code: the trained network is a published ONNX file (release `jassformer-v2`, sha256 below),
which is data, and this module rebuilds its input exactly as their `GameView` /
`ArtificialPlayer` do (the encoding, the belief table it keeps from failed follows, the
tie-breaking of the argmax) and runs the network with `onnxruntime`. Ported from their MIT code;
the attribution is in `docs/opponents/jassformer.md`. Nothing of theirs is imported or vendored,
and nothing under `krass_jass/` imports this module or onnxruntime.

    python -m arena.opponents.jassformer --deals 100 --cfg chibre        # their game: suits only, spades x2
    python -m arena.opponents.jassformer --deals 100 --cfg eval          # our EVAL table, Obenabe/Undenufe in
    python -m arena.opponents.jassformer --report .runs/jassformer-chibre-1-shipped.jsonl

Rules. Their game is the Romand Chibre: four suit contracts only (no Obenabe / Undenufe), spades
count double (tricks, last trick, match), forehand may pass to the partner, who must choose. Card
legality agrees with ours except one corner: with nothing but trumps in hand after a trick was
overtrumped, they forbid undertrumping while holding a higher trump; we allow any trump. The
network picks the argmax over *their* legal set; if that card is not legal in our engine it is
logged and the argmax over *our* legal set is played instead (our engine stays authoritative).

Two tables:
  * `chibre` — their game: `EVAL` with spades x2 and everything else x1, and our bot restricted
    to the four suits (`SuitsOnly`: when our selector names Obenabe/Undenufe it takes its best suit
    instead, shoving when that suit is under our shove threshold). Only our *bid* is wrapped; our
    card play is the shipped search unchanged.
  * `eval` — our `EVAL` as is. The network never calls a no-trump contract; when we do, it is out
    of its training distribution (trump token as their code would write it for `COLOR_NONE`).

Seats. Their positions are relative to the deciding seat: SELF=0, RIGHT=1 (next to play),
ACROSS=2, LEFT=3. Our play order is seat+1, so their position of seat s seen from seat me is
(s - me) mod 4. Cards: theirs are color*9 + rank, colors spade/heart/club/diamond, ranks 6..A
upwards; ours are suit*9 + rank, suits D/H/S/C, ranks A..6 downwards. `test_mapping` in
`main --check` replays their unit tests' token vectors.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from arena.ab import build  # noqa: E402
from arena.arena import choose_contract, deal_spec, paired_test, resolve_weis  # noqa: E402
from krass_jass.agent import Agent  # noqa: E402
from krass_jass.cards import RANK_CHARS, SUIT_CHARS, card_list, card_rank, card_suit  # noqa: E402
from krass_jass.observation import build_observation, derive_decision_seed  # noqa: E402
from krass_jass.rules import EVAL, SHOVE, Contract, RulesConfig  # noqa: E402
from krass_jass.state import RoundState  # noqa: E402
from krass_jass.tables import STRENGTH  # noqa: E402
from krass_jass.trick import trick_winner  # noqa: E402
from krass_jass.trump import load_weights, score_all  # noqa: E402

MODEL_URL = "https://github.com/jberclaz/jass/releases/download/jassformer-v2/jassformer.onnx"
MODEL_SHA256 = "032533d5296e4a607dc16522eea597bce10fa386343c5d63fa348729ad2e3de8"
DEFAULT_MODEL = "/home/user/ext/jass-model/jassformer.onnx"

CHIBRE = EVAL.variant(multipliers={
    Contract.DIAMONDS: 1, Contract.HEARTS: 1, Contract.SPADES: 2, Contract.CLUBS: 1,
    Contract.OBENABE: 1, Contract.UNDENUFE: 1,
})
CFGS = {"chibre": CHIBRE, "eval": EVAL}

# ---------------------------------------------------------------- cards and seats

#: their colour of our suit (ours D,H,S,C = 0..3; theirs spade 0, heart 1, club 2, diamond 3)
THEIR_COLOR = (3, 1, 0, 2)
OUR_SUIT = tuple(THEIR_COLOR.index(c) for c in range(4))
COLOR_NONE = 4
RANK_NELL, RANK_BOURG = 3, 5
VALUES = (0, 0, 0, 0, 10, 2, 3, 4, 11)
VALUES_ATOUT = (0, 0, 0, 14, 10, 20, 3, 4, 11)


def their_card(c: int) -> int:
    return THEIR_COLOR[card_suit(c)] * 9 + (8 - card_rank(c))


def our_card(n: int) -> int:
    return OUR_SUIT[n // 9] * 9 + (8 - n % 9)


def their_atout(contract: Contract) -> int:
    return THEIR_COLOR[int(contract)] if contract < 4 else COLOR_NONE


def rel(seat: int, me: int) -> int:
    """Their PlayerPosition code of `seat` seen from `me`."""
    return (seat - me) % 4


# ---------------------------------------------------------------- their tokens (Tokens.java)

PAD, CLS = 0, 1
SECTION_GLOBALS, SECTION_HAND, SECTION_TRICK, SECTION_HISTORY, SECTION_BELIEF = 3, 4, 5, 6, 7
TRUMP_FIRST_CHOICE, TRUMP_FORCED = 50, 51
WIN_OUR_TEAM, WIN_OPP_TEAM = 123, 124
CHOOSE_NEXT_CARD, CHOOSE_TRUMP_SUIT = 125, 126
_POS_TOKEN = {0: 52, 2: 53, 1: 55, 3: 54}  # SELF, PARTNER, OPP_R (next), OPP_L


def card_token(n: int) -> int:
    return 10 + n


def trump_token(atout: int) -> int:
    return 56 + atout


def score_token(score: int) -> int:
    return 60 + min(score // 10, 25)


def global_score_token(score: int) -> int:
    return 86 + min(score // 100, 25)


def confidence_token(p: float) -> int:
    return 112 + min(max(math.floor(p * 10 + 0.5), 0), 10)  # Java Math.round


# ---------------------------------------------------------------- their trick rules (Plie.java)

def _gt(a: int, b: int, atout: int) -> bool:
    """Card.compareTo(a, b) > 0 for two cards of one colour."""
    ra, rb = a % 9, b % 9
    if ra == rb:
        return False
    if a // 9 == atout:
        for top in (RANK_BOURG, RANK_NELL):
            if rb == top:
                return False
            if ra == top:
                return True
    return ra > rb


def their_legal(hand: list[int], trick: list[int], atout: int) -> list[int]:
    """`Plie.canPlay` over a hand, in their card numbers."""
    if not trick:
        return list(hand)
    led = trick[0] // 9
    cut = led != atout and any(c // 9 == atout for c in trick)
    highest = trick[0]
    for c in trick[1:]:
        if c // 9 == highest // 9 and _gt(c, highest, atout):
            highest = c
        elif c // 9 == atout and highest // 9 != atout:
            highest = c
    trumps = [c for c in hand if c // 9 == atout]
    bourg_sec = len(trumps) == 1 and trumps[0] % 9 == RANK_BOURG
    out = []
    for c in hand:
        color = c // 9
        if color == led:
            ok = True
        elif color == atout:
            if not cut or _gt(c, highest, atout):
                ok = True
            elif any(h // 9 != atout for h in hand):
                ok = False
            else:
                ok = not any(_gt(h, highest, atout) for h in hand)
        else:
            has_led = any(h // 9 == led for h in hand)
            ok = (led == atout and bourg_sec) if has_led else True
        if ok:
            out.append(c)
    return out


def trick_score(trick: list[int], atout: int) -> int:
    s = sum(VALUES_ATOUT[c % 9] if c // 9 == atout else VALUES[c % 9] for c in trick)
    return 2 * s if atout == 0 else s


# ---------------------------------------------------------------- their GameView

class View:
    """`GameView` as `ArtificialPlayer` feeds it, rebuilt from one observation."""

    def __init__(self, hand: list[int]):
        self.unknown: dict[int, list[float]] = {
            n: [1 / 3, 1 / 3, 1 / 3] for n in range(36) if n not in hand
        }
        self.known: list[list[int]] = [[], [], []]

    def has(self, idx: int, n: int) -> None:
        if n not in self.unknown:
            return
        del self.unknown[n]
        self.known[idx].append(n)

    def does_not_have(self, idx: int, n: int) -> None:
        if n in self.known[idx]:
            raise RuntimeError(f"contradictory view: {idx} is known to hold {n}")
        prob = self.unknown.get(n)
        if prob is None or prob[idx] <= 0:
            return
        prob[idx] = 0.0
        total = sum(prob)
        if total == 0:
            raise RuntimeError("probabilities sum to zero")
        unique = -1
        for p in range(3):
            if prob[p] == total:
                unique = p
                break
            prob[p] /= total
        if unique >= 0:
            self.has(unique, n)

    def played(self, idx: int, n: int) -> None:
        from_game = self.unknown.pop(n, None) is not None
        from_hand = n in self.known[idx]
        if from_hand:
            self.known[idx].remove(n)
        if from_game == from_hand:
            raise RuntimeError(f"card {n} played by {idx} not accounted for")

    def most_probable(self, idx: int, k: int, threshold: float = 0.34) -> list[tuple[int, float]]:
        # HashMap<Integer> iterates in key order at this size, and the sort is stable.
        rows = [(n, p[idx]) for n, p in sorted(self.unknown.items()) if p[idx] > threshold]
        rows.sort(key=lambda r: -r[1])
        return rows[:k]


def card_tokens(obs) -> list[int]:
    """`GameView.getTransformersTokensForCardChoice` for the seat to play."""
    me = obs.seat
    atout = their_atout(obs.contract)
    hand = sorted(their_card(c) for c in card_list(obs.hand))
    view = View([their_card(c) for c in card_list(obs.hand)]
                + [their_card(c) for c in _own_played(obs)])
    ours = theirs = 0
    history: list[tuple[list[int], bool]] = []
    tricks = [(lead, list(cards)) for lead, cards in obs.tricks_played]
    tricks.append((obs.trick_leader, list(obs.trick)))
    for lead, cards in tricks:
        played: list[int] = []
        for i, c in enumerate(cards):
            seat = (lead + i) % 4
            n = their_card(c)
            pos = rel(seat, me)
            if pos != 0:
                # ArtificialPlayer.setPlayedCard: a failed follow with a non-trump voids the led suit
                # (all of it but the trump Jack).
                if played and n // 9 != atout and n // 9 != played[0] // 9:
                    led = played[0] // 9
                    for r in range(9):
                        if not (led == atout and r == RANK_BOURG):
                            view.does_not_have(pos - 1, led * 9 + r)
                view.played(pos - 1, n)
            played.append(n)
        if len(cards) == 4:
            winner = trick_winner(cards, lead, STRENGTH[obs.contract][card_suit(cards[0])])
            we = rel(winner, me) % 2 == 0
            pts = trick_score(played, atout)
            if we:
                ours += pts
            else:
                theirs += pts
            history.append((played, we))

    forehand = obs.forehand
    first = obs.declarer_seat == forehand
    t = [CLS, SECTION_GLOBALS, CHOOSE_NEXT_CARD,
         TRUMP_FIRST_CHOICE if first else TRUMP_FORCED,
         _POS_TOKEN[rel(obs.declarer_seat, me)], trump_token(atout),
         score_token(ours), score_token(theirs), global_score_token(0), global_score_token(0),
         SECTION_HAND]
    t += [card_token(n) for n in hand] + [PAD] * (9 - len(hand))
    t.append(SECTION_TRICK)
    for i, c in enumerate(obs.trick):
        t += [_POS_TOKEN[rel((obs.trick_leader + i) % 4, me)], card_token(their_card(c))]
    t += [PAD] * (27 - len(t))
    t.append(SECTION_HISTORY)
    for played, we in history:
        t += [card_token(n) for n in played] + [WIN_OUR_TEAM if we else WIN_OPP_TEAM]
    t += [PAD] * (68 - len(t))
    t.append(SECTION_BELIEF)
    for pos in (1, 2, 3):
        t.append(_POS_TOKEN[pos])
        cards = [(n, 1.0) for n in view.known[pos - 1][:4]]
        cards += view.most_probable(pos - 1, 4 - len(cards))
        for n, p in cards:
            t += [card_token(n), confidence_token(p)]
        t += [PAD, PAD] * (4 - len(cards))
    assert len(t) == 96, len(t)
    return t


def _own_played(obs) -> list[int]:
    out = []
    for lead, cards in obs.tricks_played:
        out += [c for i, c in enumerate(cards) if (lead + i) % 4 == obs.seat]
    return out


def trump_tokens(hand: int, first: bool) -> list[int]:
    """`GameView.getTransformersTokensForTrumpChoice`, at the start of a hand from 0-0."""
    cards = sorted(their_card(c) for c in card_list(hand))
    t = [CLS, SECTION_GLOBALS, CHOOSE_TRUMP_SUIT, TRUMP_FIRST_CHOICE if first else TRUMP_FORCED,
         _POS_TOKEN[0], PAD, score_token(0), score_token(0), global_score_token(0),
         global_score_token(0), SECTION_HAND]
    t += [card_token(n) for n in cards] + [PAD] * (9 - len(cards))
    t.append(SECTION_TRICK)
    t += [PAD] * (27 - len(t))
    t.append(SECTION_HISTORY)
    t += [PAD] * (68 - len(t))
    t.append(SECTION_BELIEF)
    t += [PAD] * (96 - len(t))
    return t


# ---------------------------------------------------------------- the agent

_SESSIONS: dict[str, object] = {}


def _session(path: str):
    if path not in _SESSIONS:
        import onnxruntime as ort  # arena-only dependency, never imported by krass_jass

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        _SESSIONS[path] = ort.InferenceSession(path, opts, providers=["CPUExecutionProvider"])
    return _SESSIONS[path]


def run_model(path: str, tokens: list[int]):
    import numpy as np

    sess = _session(path)
    card, trump = sess.run(["card_logits", "trump_logits"],
                           {"tokens": np.asarray([tokens], dtype=np.int64)})
    return card[0], trump[0]


def _argmax(logits, options: list[int]) -> int:
    """`JassModelLoader.chooseBestCard`: first strictly greater, in the order given."""
    best, best_v = options[0], -math.inf
    for o in options:
        if logits[o] > best_v:
            best, best_v = o, logits[o]
    return best


@dataclass
class JassFormer(Agent):
    """JassFormer v2, one forward pass per decision. Picklable: only paths."""

    cfg: RulesConfig = EVAL
    model: str = DEFAULT_MODEL
    log: str = ".runs/jassformer-illegal.log"
    name: str = "JassFormer-v2"

    def _log(self, row: dict) -> None:
        Path(self.log).parent.mkdir(parents=True, exist_ok=True)
        with open(self.log, "a") as fh:
            fh.write(json.dumps(row) + "\n")

    def select_trump(self, hand: int, is_forehand: bool):
        try:
            _, logits = run_model(self.model, trump_tokens(hand, is_forehand))
        except Exception as e:  # noqa: BLE001 - a broken opponent must not stall a match
            self._log({"kind": "error", "where": "trump", "error": repr(e)})
            return Contract.DIAMONDS
        choice = _argmax(logits, list(range(5 if is_forehand else 4)))
        if choice == COLOR_NONE:
            return SHOVE
        return Contract(OUR_SUIT[choice])

    def decide(self, obs) -> int:
        legal = card_list(obs.legal_moves)
        if len(legal) == 1:
            return legal[0]
        try:
            logits, _ = run_model(self.model, card_tokens(obs))
        except Exception as e:  # noqa: BLE001
            self._log({"kind": "error", "where": "card", "error": repr(e)})
            return legal[-1]
        hand = sorted(their_card(c) for c in card_list(obs.hand))
        trick = [their_card(c) for c in obs.trick]
        theirs = their_legal(hand, trick, their_atout(obs.contract))
        ours = sorted(their_card(c) for c in legal)
        pick = _argmax(logits, theirs)
        if pick not in ours:
            # Our engine decides what is legal. Record it and play the network's best legal card.
            self._log({"kind": "illegal", "card": pick, "hand": hand, "trick": trick,
                       "contract": int(obs.contract)})
            pick = _argmax(logits, ours)
        return our_card(pick)


@dataclass
class SuitsOnly(Agent):
    """Our agent at a suits-only table: its card play untouched, its bid kept unless it names
    Obenabe/Undenufe, which become its best suit (or a shove from forehand when that suit is under
    the selector's shove threshold)."""

    inner: Agent = None
    cfg: RulesConfig = EVAL
    name: str = "ours"
    #: When set, this agent bids for ours (`--our-bid jassformer`): isolates our card play.
    bidder: Agent | None = None

    def decide(self, obs) -> int:
        return self.inner.decide(obs)

    def select_trump(self, hand: int, is_forehand: bool):
        if self.bidder is not None:
            return self.bidder.select_trump(hand, is_forehand)
        choice = self.inner.select_trump(hand, is_forehand)
        if choice == SHOVE or Contract(choice).is_trump:
            return choice
        w = load_weights(getattr(self.inner, "trump_weights", "") or None)
        scores = score_all(hand, self.inner.cfg, w)
        best = max((Contract(s) for s in range(4)), key=lambda c: (scores[c], -int(c)))
        if is_forehand and scores[best] < w["shove_threshold"]["value"]:
            return SHOVE
        return best


# ---------------------------------------------------------------- the match

def play_round(hands, leader, seats, cfg, game_seed, game_id="arena") -> dict:
    """`arena.arena.play_round`, but it also returns the bid and the cards for the diagnosis."""
    first = seats[leader].select_trump(hands[leader], is_forehand=True)
    contract, declarer = choose_contract(hands, leader, seats, cfg)
    weis, stoeck, shown, announced = resolve_weis(hands, contract, leader, cfg)
    state = RoundState(contract=contract, hands=list(hands), cfg=cfg, leader=leader)
    cards, trick_no = [], 0
    while not state.done:
        seat = state.to_play
        obs = build_observation(
            state, seat, declarer_seat=declarer,
            decision_seed=derive_decision_seed(game_seed, game_id, seat, 0, trick_no),
            known_cards=tuple((s, c) for s, c in shown if state.hands[s] & (1 << c)),
            weis_announced=announced,
        )
        card = seats[seat].decide(obs)
        state.play(card)
        cards.append(card)
        trick_no = len(state.tricks_played)
    total = state.score(weis=weis, stoeck=stoeck).total
    return {"contract": int(contract), "declarer": declarer, "shoved": first == SHOVE,
            "points": list(total), "cards": cards}


def double_round(hands, leader, ours, theirs, cfg, game_seed) -> dict:
    """Both halves on the same game seed. In half 0 we sit at seats 0/2, in half 1 at 1/3."""
    halves = []
    for h, seats in enumerate(({0: ours, 2: ours, 1: theirs, 3: theirs},
                               {1: ours, 3: ours, 0: theirs, 2: theirs})):
        r = play_round(hands, leader, seats, cfg, game_seed)
        r["our_team"] = h
        halves.append(r)
    a = halves[0]["points"][0] + halves[1]["points"][1]
    b = halves[0]["points"][1] + halves[1]["points"][0]
    return {"share": 0.5 if a + b == 0 else a / (a + b), "halves": halves, "leader": leader}


def _deal(args):
    ours, theirs, cfg, seed, index = args
    hands, _, leader, game_seed = deal_spec(seed, index, None)
    out = double_round(hands, leader, ours, theirs, cfg, game_seed)
    out["deal"] = index
    return out


def _load(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {r["deal"]: r for r in rows}


def report(path: Path, worst: int = 5) -> dict:
    rows = sorted(_load(path).values(), key=lambda r: r["deal"])
    shares = [r["share"] for r in rows]
    _, pv = paired_test([s - 0.5 for s in shares])
    mean, std = statistics.fmean(shares), statistics.stdev(shares)
    print(f"{path.name}: ours {mean:.2%} ± {std:.2%} (std)  se {std / len(shares) ** 0.5:.2%}  "
          f"n={len(shares)}  p={pv:.2e}")

    # Per half: who declared, which contract, and our share of that half's points.
    by: dict[tuple, list[float]] = {}
    shove = {"ours": [0, 0], "theirs": [0, 0]}
    for r in rows:
        for h in r["halves"]:
            us = h["our_team"]
            pts = h["points"]
            if sum(pts) == 0:
                continue
            side = "ours" if h["declarer"] % 2 == us else "theirs"
            fh_side = "ours" if r["leader"] % 2 == us else "theirs"
            shove[fh_side][0] += h["shoved"]
            shove[fh_side][1] += 1
            share = pts[us] / sum(pts)
            by.setdefault((side, Contract(h["contract"]).name), []).append(share)
            by.setdefault((side, "ALL"), []).append(share)
    print("  declarer  contract   halves  our share of the half")
    for key in sorted(by):
        v = by[key]
        print(f"  {key[0]:8}  {key[1]:9} {len(v):6}  {statistics.fmean(v):.2%}")
    for side, (s, n) in shove.items():
        print(f"  shove rate from forehand, {side}: {s}/{n} = {s / max(n, 1):.1%}")
    print(f"  worst {worst} deals for us:")
    for r in sorted(rows, key=lambda r: r["share"])[:worst]:
        desc = "; ".join(
            f"half {h['our_team']}: {'we' if h['declarer'] % 2 == h['our_team'] else 'they'} "
            f"{'(shoved) ' if h['shoved'] else ''}{Contract(h['contract']).name} "
            f"{h['points'][h['our_team']]}-{h['points'][1 - h['our_team']]}"
            for h in r["halves"])
        print(f"    deal {r['deal']:4}  {r['share']:.1%}  {desc}")
    return {"a_share": mean, "std": std, "p": pv, "deals": len(shares),
            "se": std / len(shares) ** 0.5}


def _name(c: int) -> str:
    return SUIT_CHARS[card_suit(c)] + RANK_CHARS[card_rank(c)]


def show(path: Path, deal: int, seed: int) -> None:
    """One deal, both halves, trick by trick, for annotating a loss."""
    r = _load(path)[deal]
    hands, _, leader, _ = deal_spec(seed, deal, None)
    print(f"deal {deal}: our share {r['share']:.1%}, forehand seat {leader}")
    for s in range(4):
        print(f"  seat {s}: {' '.join(_name(c) for c in card_list(hands[s]))}")
    for h in r["halves"]:
        us = h["our_team"]
        who = lambda s: "ours" if s % 2 == us else "JF"  # noqa: E731
        print(f"  half {us}: we are seats {us}/{us + 2}; {who(h['declarer'])} seat {h['declarer']} "
              f"{'(shoved) ' if h['shoved'] else ''}declares {Contract(h['contract']).name}; "
              f"points ours {h['points'][us]}, JF {h['points'][1 - us]}")
        lead, cards = leader, h["cards"]
        for t in range(9):
            trick = cards[4 * t:4 * t + 4]
            win = trick_winner(trick, lead, STRENGTH[Contract(h["contract"])][card_suit(trick[0])])
            seq = " ".join(f"{(lead + i) % 4}{'*' if (lead + i) % 2 == us else ' '}{_name(c)}"
                           for i, c in enumerate(trick))
            print(f"    {t + 1}: {seq}  -> seat {win} ({who(win)})")
            lead = win


def errors(log: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    if log.exists():
        for line in log.read_text().splitlines():
            if line.strip():
                k = json.loads(line)["kind"]
                out[k] = out.get(k, 0) + 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deals", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--cfg", choices=sorted(CFGS), default="chibre")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--ours", nargs="*", default=[], help="DmctsAgent field=value pairs, as arena.ab")
    ap.add_argument("--out", type=Path, help="per-deal results, one JSON line each; a rerun resumes")
    ap.add_argument("--our-bid", choices=["ours", "jassformer"], default="ours",
                    help="chibre only: who bids for our side (jassformer = our card play, their bid)")
    ap.add_argument("--report", type=Path, help="report an --out file and stop")
    ap.add_argument("--show", type=int, help="with --report: print this deal trick by trick")
    ap.add_argument("--no-record", action="store_true", help="do not append to results.jsonl")
    args = ap.parse_args()
    if args.report:
        if args.show is not None:
            show(args.report, args.show, args.seed)
        else:
            report(args.report)
        return

    cfg = CFGS[args.cfg]
    tag = "-".join(args.ours) or "shipped"
    if args.our_bid != "ours":
        tag += f"-bid_{args.our_bid}"
    Path(".runs").mkdir(exist_ok=True)
    inner = build(args.ours, 153_600, cfg)  # 40 x 3,840, as served, unless --ours says otherwise
    log = Path(f".runs/jassformer-{args.cfg}-{args.seed}-{tag}.log")
    theirs = JassFormer(cfg=cfg, model=args.model, log=str(log))
    bidder = theirs if args.our_bid == "jassformer" else None
    ours = SuitsOnly(inner=inner, cfg=cfg, bidder=bidder) if args.cfg == "chibre" else inner
    out = args.out or Path(f".runs/jassformer-{args.cfg}-{args.seed}-{tag}.jsonl")
    done = _load(out)
    todo = [i for i in range(args.deals) if i not in done]
    print(f"{out}: {len(done)} done, {len(todo)} to play", flush=True)
    t = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool, out.open("a") as fh:
        futures = [pool.submit(_deal, (ours, theirs, cfg, args.seed, i)) for i in todo]
        for n, f in enumerate(as_completed(futures), 1):
            fh.write(json.dumps(f.result()) + "\n")
            fh.flush()
            if n % 10 == 0:
                print(f"  {n}/{len(todo)} ({(time.time() - t) / 60:.0f} min)", flush=True)

    res = report(out)
    errs = errors(log)
    print(f"  opponent log: {errs or 'no illegal cards, no errors'}")
    if args.no_record:
        return
    record = {
        "a": (args.ours or ["shipped"]) + ([f"bid={args.our_bid}"] if args.our_bid != "ours" else []), "b": ["JassFormer-v2"], "cfg": args.cfg, "seed": args.seed,
        "iterations": inner.determinizations * inner.iterations, **res,
        "illegal": errs.get("illegal", 0), "errors": errs.get("error", 0),
        "minutes": round((time.time() - t) / 60, 1), "when": time.strftime("%Y-%m-%d %H:%M"),
    }
    with Path("arena/opponents/results.jsonl").open("a") as fh:
        fh.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
