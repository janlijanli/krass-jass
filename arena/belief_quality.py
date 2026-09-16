"""How much better are the beliefs, before anyone plays a match?

`docs/measurements.md` §5k replaced a fraction `p` of the imagined worlds with the true deal
and measured what that is worth: +1.34 of a round's share at p=0.1, +2.52 at p=0.2. That
intervention has an exact offline counterpart. Score a belief by the expected fraction of the
unseen cards it places in the right hand; mixing a fraction `p` of true worlds into a sampler
with accuracy `u` gives exactly `u + p(1 - u)`. So a weighted sampler with accuracy `a` is
worth an **oracle-equivalent p of `(a - u) / (1 - u)`** — on the same axis as §5k's curve.

It is a proxy, not a result: the search uses the worlds, not the accuracy, and a belief can be
sharper in a way that does not change a decision. What it is good for is choosing weights and
temperatures in seconds instead of in hour-long matches, and for saying early whether a match
is worth running at all.

Three sources of weight on the same pool of consistent worlds, combinable:

- α — the other seats' plays, under the play model (`rust/src/belief.rs`);
- β — the bid, under a softmax over the rule selector's scores;
- γ — the belief network (`rust/src/beliefnet.rs`, `--belief-net`): Σ log q(card at its seat).

The plays being read are our own bots', which is also who both models were fitted to. Pass
`--players random` for a table the models know nothing about.

Usage::

    python -m arena.belief_quality --rounds 300
    python -m arena.belief_quality --rounds 300 --belief-net krass_jass/data/belief_net.json
"""

from __future__ import annotations

import argparse
import os
import pickle
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

import krass_jass_core as core  # noqa: E402
from arena.arena import choose_contract, deal_spec, resolve_weis  # noqa: E402
from arena.belief_data import public_inputs  # noqa: E402
from krass_jass.agent import DmctsAgent, RandomAgent  # noqa: E402
from krass_jass.observation import build_observation, derive_decision_seed  # noqa: E402
from krass_jass.rules import EVAL, HOUSE  # noqa: E402
from krass_jass.state import RoundState  # noqa: E402

#: Decisions sampled per round, by number of cards already played. Early decisions have
#: little evidence to read; the interesting ones are mid-round.
PROBE_AT = (6, 13, 17, 22, 26)
KEYS = ("seat", "hand", "history", "contract", "declarer", "forehand", "forbidden", "known",
        "weis_called")
CARDS = np.arange(36, dtype=np.uint64)


@lru_cache(maxsize=2)
def _net_text(path: str) -> str:
    return Path(path).read_text()


def _cfg(name: str):
    return HOUSE.variant(target_score=None) if name == "house" else EVAL


def _probe_round(args):
    seed, index, players, pool, temperature, cfg_name, iterations = args
    cfg = _cfg(cfg_name)
    hands, _, leader, game_seed = deal_spec(seed, index, None)
    if players == "random":
        agent = RandomAgent()
        # Random card play, but the rule selector bids, so the bid is still evidence to read.
        agent.trump_policy = "rules"
    else:
        agent = DmctsAgent(determinizations=40, iterations=max(1, iterations // 40), cfg=cfg)
    reader = DmctsAgent(cfg=cfg)
    seats = {s: agent for s in range(4)}
    contract, declarer = choose_contract(hands, leader, seats, cfg)
    _, _, shown, announced = resolve_weis(hands, contract, leader, cfg)
    st = RoundState(contract=contract, hands=list(hands), cfg=cfg, leader=leader)
    rng = random.Random(f"probe:{seed}:{index}")
    out = []
    played = 0
    while not st.done:
        seat = st.to_play
        obs = build_observation(
            st, seat, declarer_seat=declarer,
            decision_seed=derive_decision_seed(game_seed, "probe", seat, 0, len(st.tricks_played)),
            known_cards=tuple((s, c) for s, c in shown if st.hands[s] & (1 << c)),
            weis_announced=announced,
        )
        if played in PROBE_AT:
            x = public_inputs(obs, reader)
            called = x["weis_called"] if announced else None
            worlds, play_ll, bid_ll = core.rs_belief_pool(
                seat, obs.hand, obs.unseen, list(obs.trick), obs.trick_leader, int(obs.contract),
                x["forbidden"], declarer, x["history"], pool, rng.getrandbits(63), temperature, 3.0,
                called, list(obs.played_by) if called else None,
            )
            truth = list(st.hands)
            W = np.array(worlds, dtype=np.uint64)
            bits = ((W[:, :, None] >> CARDS) & np.uint64(1)).astype(bool)  # (P, 4, 36)
            n_unseen = bin(obs.unseen).count("1")
            correct = sum(
                (bits[:, s, :] & (((np.uint64(truth[s]) >> CARDS) & np.uint64(1)).astype(bool))).sum(axis=1)
                for s in range(4) if s != seat
            ) / n_unseen
            # Everything a network needs is kept, so any number of networks can be scored later
            # against the same decisions without replaying a card (`--save-probes`).
            out.append({"played": played, "pl": np.array(play_ll), "bl": np.array(bid_ll),
                        "correct": correct, "worlds": W, "x": x, "truth": truth,
                        "unseen": obs.unseen})
        st.play(agent.decide(obs))
        played += 1
    return out


def score_net(probes, net_path: str) -> None:
    """Attach the network's log-weight per world and its per-card accuracy to every probe."""
    text = _net_text(net_path)
    for pr in probes:
        x, W, truth, seat = pr["x"], pr["worlds"], pr["truth"], pr["x"]["seat"]
        bits = ((W[:, :, None] >> CARDS) & np.uint64(1)).astype(bool)
        lq = np.array(core.rs_belief_log_probs(*(x[k] for k in KEYS), text))
        lw = np.zeros(len(W))
        accs = []
        for r in (1, 2, 3):
            other = (seat + r) % 4
            lw += np.where(bits[:, other, :], lq[:, r - 1], 0.0).sum(axis=1)
            held = ((np.uint64(truth[other] & pr["unseen"]) >> CARDS) & np.uint64(1)).astype(bool)
            accs.extend(np.exp(lq[held, r - 1]))
        pr["nl"], pr["net_acc"] = lw, float(np.mean(accs)) if accs else np.nan


def _rescore(args):
    x, worlds, policy_t, bid_t, model_text = args
    pl, bl = core.rs_belief_loglik(worlds, x["seat"], x["forehand"], x["contract"], x["declarer"],
                                   x["history"], policy_t, bid_t, model_text)
    return np.array(pl), np.array(bl)


def rescore(probes, args) -> None:
    """Temperatures × α × β on saved worlds, under the shipped or a given play model."""
    model_text = Path(args.play_model).read_text() if args.play_model else None
    policy_ts = [float(v) for v in args.policy_temps.split(",")]
    bid_ts = [float(v) for v in args.bid_temps.split(",")]
    alphas, betas = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0), (0.5, 1.0, 2.0)
    print(f"re-scoring {len(probes)} saved decisions; play model: {args.play_model or 'shipped'}")
    print("ESS here is for the saved pool (2,048 worlds); the search draws 4,096, roughly doubling it.\n")
    print(f"  {'policy T':>8} {'bid T':>6} {'α':>5} {'β':>5}  {'oracle-equivalent p':>22}  {'median ESS':>10}")
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for pt in policy_ts:
            for bt in bid_ts:
                jobs = [(pr["x"], pr["worlds"].tolist(), pt, bt, model_text) for pr in probes]
                scored = list(ex.map(_rescore, jobs, chunksize=16))
                view = [dict(pr, pl=pl, bl=bl) for pr, (pl, bl) in zip(probes, scored)]
                for a in alphas:
                    for b in betas:
                        _, _, p, se, ess = summarise(view, a, b, 0.0)
                        rows.append((pt, bt, a, b, p, se, ess))
                        print(f"  {pt:8.2f} {bt:6.2f} {a:5.2f} {b:5.2f}  {p:14.4f} ± {se:.4f}  {ess:10.0f}", flush=True)
    ok = [r for r in rows if r[6] >= 150]
    print("\n  best with median ESS ≥ 150 here (≈ 300 in the search):")
    for r in sorted(ok, key=lambda r: -r[4])[:8]:
        print(f"    policy T {r[0]:.2f}  bid T {r[1]:.2f}  α {r[2]:.2f}  β {r[3]:.2f}  p = {r[4]:.4f} ± {r[5]:.4f}  ESS {r[6]:.0f}")


def summarise(probes, alpha, beta, gamma):
    acc_u, acc_w, ess = [], [], []
    for pr in probes:
        pl, bl, correct = pr["pl"], pr["bl"], pr["correct"]
        nl = pr.get("nl", 0.0)
        lw = alpha * pl + beta * bl + gamma * nl
        ok = np.isfinite(lw)
        # Nothing left to believe: every consistent world is the true one.
        if not ok.any() or correct[ok].min() >= 1.0:
            continue
        lw = lw[ok] - lw[ok].max()
        w = np.exp(lw)
        w /= w.sum()
        acc_u.append(correct[ok].mean())
        acc_w.append((w * correct[ok]).sum())
        ess.append(1.0 / (w * w).sum())
    u, a = np.array(acc_u), np.array(acc_w)
    per = (a - u) / (1 - u)
    return u.mean(), a.mean(), per.mean(), per.std(ddof=1) / np.sqrt(len(per)), np.median(ess)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=300)
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--pool", type=int, default=2048)
    ap.add_argument("--players", choices=["bots", "random"], default="bots")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--cfg", choices=["eval", "house"], default="house")
    ap.add_argument("--iterations", type=int, default=2400)
    ap.add_argument("--belief-net", type=str, default="")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--save-probes", type=Path, default=None,
                    help="keep the decisions, worlds and truth so networks can be scored later")
    ap.add_argument("--load-probes", type=Path, default=None,
                    help="score against saved decisions instead of replaying rounds")
    ap.add_argument("--rescore", action="store_true",
                    help="with --load-probes: sweep temperatures, α and β on the saved worlds")
    ap.add_argument("--policy-temps", default="1.0")
    ap.add_argument("--bid-temps", default="3.0")
    ap.add_argument("--play-model", default="", help="play model JSON to read the table through")
    args = ap.parse_args()

    if args.load_probes:
        with args.load_probes.open("rb") as fh:
            probes = pickle.load(fh)
    else:
        payload = [(args.seed, i, args.players, args.pool, args.temperature, args.cfg,
                    args.iterations) for i in range(args.rounds)]
        probes = []
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for part in ex.map(_probe_round, payload, chunksize=4):
                probes.extend(part)
        if args.save_probes:
            with args.save_probes.open("wb") as fh:
                pickle.dump(probes, fh)
    if args.rescore:
        rescore(probes, args)
        return
    if args.belief_net:
        score_net(probes, args.belief_net)
    print(f"{len(probes)} decisions from {args.rounds} rounds, {args.players} at the table, "
          f"{args.cfg.upper()}, pool {args.pool}, play-model temperature {args.temperature}\n")

    header = f"  {'plays α':>7} {'bid β':>6} {'net γ':>6}  {'uniform':>8} {'weighted':>8}  {'oracle-equivalent p':>22}  {'median ESS':>10}"
    if args.belief_net:
        rows = [(0, 0, 0), (1, 1, 0), (0, 0, 0.5), (0, 0, 1), (0, 1, 1), (1, 1, 0.5), (1, 1, 1)]
    else:
        rows = [(a, b, 0) for a in (0.0, 0.25, 0.5, 1.0, 2.0) for b in (0.0, 0.5, 1.0, 2.0)]
    print(header)
    for alpha, beta, gamma in rows:
        u, a, p, se, ess = summarise(probes, alpha, beta, gamma)
        print(f"  {alpha:7.2f} {beta:6.2f} {gamma:6.2f}  {u:8.4f} {a:8.4f}  {p:14.4f} ± {se:.4f}  {ess:10.0f}")

    if args.belief_net:
        marg = np.nanmean([pr["net_acc"] for pr in probes])
        print(f"\n  network per-card accuracy on its own (a marginal, not a world): {marg:.4f}")

    best = (1, 1, 1) if args.belief_net else (1, 1, 0)
    print(f"\n  by cards played, α={best[0]} β={best[1]} γ={best[2]}")
    for when in PROBE_AT:
        sub = [pr for pr in probes if pr["played"] == when]
        if sub:
            _, _, p, se, ess = summarise(sub, *best)
            print(f"    {when:2d} played  n={len(sub):<5} p = {p:.4f} ± {se:.4f}  ESS {ess:.0f}")


if __name__ == "__main__":
    main()
