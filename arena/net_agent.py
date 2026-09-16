"""An agent that plays from the policy network alone — no search.

Candidate A of `docs/neural-plan.md` in playable form: one forward pass per decision, the legal
moves as a mask, the highest-scoring legal card. It exists to answer two questions the offline
numbers cannot — how much of the search's strength survives distillation, and what that costs per
move — so it lives in `arena/` with the other measurement-only agents until it earns a place in
`krass_jass/`.

Inference is numpy here deliberately. Porting it to Rust is a day's work and is worth doing *after*
the match says the network is worth serving; `CLAUDE.md`'s "no Python fallback for the search" is
about the search, which this replaces rather than backs up.

    python -m arena.ab --a ... is for DmctsAgent; use arena/ladder.py or a small script for this one.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

import krass_jass_core as core  # noqa: E402
from arena.belief_data import public_inputs  # noqa: E402
from krass_jass.agent import Agent, DmctsAgent  # noqa: E402
from krass_jass.cards import card_list  # noqa: E402
from krass_jass.observation import Observation  # noqa: E402

KEYS = ("seat", "hand", "history", "contract", "declarer", "forehand", "forbidden", "known",
        "weis_called")
CARDS = np.arange(36, dtype=np.uint64)


@lru_cache(maxsize=4)
def _weights(path: str) -> tuple:
    d = np.load(path)
    head = str(d["head"]) if "head" in d.files else "flat"
    names = ("W1", "b1", "W2", "b2", "W3", "b3") if head == "flat" else ("W1", "b1", "A", "B", "b2", "w")
    return head, tuple(d[n] for n in names)


@dataclass
class NetAgent(Agent):
    """Policy network, one forward pass, no search."""

    model: str = ""
    #: Reads the observation the way the recorder did — voids and the Weis the table showed.
    reader: DmctsAgent = field(default_factory=DmctsAgent)
    label: str | None = None

    @property
    def name(self) -> str:
        return self.label or "net"

    def decide(self, obs: Observation) -> int:
        legal = card_list(obs.legal_moves)
        if len(legal) == 1:
            return legal[0]
        x = public_inputs(obs, self.reader)
        feats = np.frombuffer(core.rs_belief_features(*(x[k] for k in KEYS)), dtype=np.float32)
        head, w = _weights(self.model)
        if head == "flat":
            W1, b1, W2, b2, W3, b3 = w
            a1 = np.maximum(feats @ W1.T + b1, 0.0)
            z = np.maximum(a1 @ W2.T + b2, 0.0) @ W3.T + b3
            mask = ((np.uint64(obs.legal_moves) >> CARDS) & np.uint64(1)).astype(bool)
            return int(np.argmax(np.where(mask, z, -np.inf)))
        # Conditioned head: the state once, then each legal card from that plus its own features.
        W1, b1, A, B, b2, v = w
        h = np.maximum(feats @ W1.T + b1, 0.0)
        card_feats = np.array(core.rs_play_features(
            obs.hand, obs.hand | obs.unseen, list(obs.trick), obs.trick_leader, obs.seat,
            int(obs.contract), obs.declarer_seat, obs.legal_moves), dtype=np.float32)
        g = np.maximum(h @ A.T + card_feats @ B.T + b2, 0.0)
        return legal[int(np.argmax(g @ v))]
