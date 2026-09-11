"""Access to the Rust search core, with an honest report when it is missing.

The Python package remains the engine of record — `RoundState`, `build_observation`,
scoring and Weis all stay here and run 36 times a game. This module is the boundary to the
hot path, which runs hundreds of thousands of times per move and lives in `rust/`.

There is deliberately **no Python fallback for the search**. A silent fallback would be a
20x slowdown disguised as a working system, and the whole point of `docs/plan-review.md` §1
is that the difference decides whether M5 is reachable. Callers get an explicit error.
"""

from __future__ import annotations

from .rules import Contract, RulesConfig

try:
    import krass_jass_core as _core

    AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the build
    _core = None
    AVAILABLE = False


BUILD_HINT = (
    "The Rust core is not built. From the repo root:\n"
    "    cd rust && maturin develop --release\n"
    "See rust/README.md."
)


def require() -> None:
    if not AVAILABLE:
        raise RuntimeError(BUILD_HINT)


def dmcts(
    *,
    seat: int,
    hand: int,
    unseen: int,
    trick: list[int],
    trick_leader: int,
    contract: Contract,
    cfg: RulesConfig,
    forbidden: list[int] | None = None,
    affinity: list[list[int]] | None = None,
    rank_bias: list[int] | None = None,
    determinizations: int = 1000,
    iterations: int = 800,
    exploration: float = 1.5,
    seed: int = 0,
    threads: int = 1,
    endgame_cards: int = 5,
    scores: tuple[int, int] = (0, 0),
    weis: tuple[int, int] = (0, 0),
    target: int = 0,
    multiplier: int = 1,
    adversarial: bool = True,
    risk_lambda: float = 0.0,
    leaf_weights: list[float] | None = None,
) -> list[tuple[int, int, float, int]]:
    """Determinized MCTS. Returns `(card, visits, mean_score, determinizations_selecting)`
    per legal move, best first.

    `forbidden` is what the play *proves* (`voids.py`); `affinity` what it *suggests*
    (`reading.py`). The first removes worlds, the second only makes some likelier.

    `scores`, `weis`, `target` and `multiplier` say what the round is *for* — see
    `objective.py`. A `target` of 0 means no game to project onto and the search falls back
    to maximising this round's share, which is what the round-level arena measures.

    `seed` must be the engine's derived per-decision seed, never the game seed — see
    `CLAUDE.md` on the information boundary. Results are independent of `threads`.
    """
    require()
    return _core.dmcts(
        seat=seat,
        hand=hand,
        unseen=unseen,
        trick=list(trick),
        trick_leader=trick_leader,
        contract=int(contract),
        forbidden=forbidden,
        affinity=affinity,
        rank_bias=rank_bias,
        determinizations=determinizations,
        iterations=iterations,
        exploration=exploration,
        seed=seed,
        threads=threads,
        endgame_cards=endgame_cards,
        strict_undertrump=cfg.strict_undertrump,
        puur_exempt=cfg.puur_exempt_trump_lead,
        scores=scores,
        weis=weis,
        target=target,
        multiplier=multiplier,
        adversarial=adversarial,
        risk_lambda=risk_lambda,
        leaf_weights=leaf_weights,
    )
