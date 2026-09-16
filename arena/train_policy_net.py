"""Distil the search into a policy network — candidate A of `docs/neural-plan.md`.

The search picks a card after 153,600 iterations. This fits a network that picks one after a single
forward pass, trained on the search's **visit distribution** rather than only its final choice: the
visits say how close the alternatives were, and a distribution is a softer, better-conditioned target
than a one-hot.

Two heads on the same ~900-input encoder (`rs_belief_features`, the one the belief network uses, so
there is one encoder and its inputs come from an observation alone — pinned by a test):

- `--head flat`: 36 output logits. Each card's meaning has to be learned separately, and it shows —
  51% top-1 against the search on 312k decisions, worse than a 36-feature linear model (§5s).
- `--head conditioned` (default): the state is embedded once, then **each legal card is scored from
  that embedding plus its own features** (`rs_play_features`, the 36 features of a (state, card) pair
  the play model uses). "This is the highest card left" then means the same thing for every card,
  which is how the small model beat the big one.

**What this is for.** Not strength: the published Jass work puts a supervised network roughly level
with determinized search, and §5j measured a learned prior inside our search at nothing. It buys
*cost* — a bot that plays near the search's level at about a millisecond a move, which is difficulty
levels, a mobile-cheap opponent, and the student half of anything that comes later.

Gates before it is worth a match (`docs/neural-plan.md` §2A): top-1 agreement with the search ≥ 70%
on held-out rounds, and then, in play, within 1% of the search's points at ~1 ms a move.

Usage::

    python -m arena.train_policy_net decisions.npz --out policy_net.npz
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

import krass_jass_core as core  # noqa: E402

N_FEATURES = 865
N_CARD_FEATURES = 36
KEYS = ("seat", "hand", "history", "contract", "declarer", "forehand", "forbidden", "known",
        "weis_called")


def encoder_args(d: dict, i: int) -> tuple:
    """The encoder's inputs for decision `i`, exactly as the search would pass them."""
    history = [(int(s), int(c)) for s, c in d["history"][i] if s >= 0]
    return (
        int(d["seat"][i]), int(d["hand"][i]), history, int(d["contract"][i]), int(d["declarer"][i]),
        int(d["forehand"][i]), [int(v) for v in d["forbidden"][i]], [int(v) for v in d["known"][i]],
        [int(v) for v in d["weis_called"][i]],
    )


def featurise(d: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Inputs, per-card features, the legal mask, the visit distribution and the card played."""
    n = len(d["card"])
    X = np.zeros((n, N_FEATURES), dtype=np.float16)
    C = np.zeros((n, 36, N_CARD_FEATURES), dtype=np.float16)
    mask = np.zeros((n, 36), dtype=bool)
    target = np.zeros((n, 36), dtype=np.float32)
    cards = np.arange(36, dtype=np.uint64)
    for i in range(n):
        X[i] = np.frombuffer(core.rs_belief_features(*encoder_args(d, i)), dtype=np.float32)
        legal = int(d["legal"][i])
        mask[i] = ((np.uint64(legal) >> cards) & np.uint64(1)).astype(bool)
        trick = [int(c) for c in d["trick"][i] if c >= 0]
        feats = core.rs_play_features(int(d["hand"][i]), int(d["live"][i]), trick,
                                      int(d["trick_leader"][i]), int(d["seat"][i]),
                                      int(d["contract"][i]), int(d["declarer"][i]), legal)
        for f, c in zip(feats, [c for c in range(36) if legal >> c & 1]):
            C[i, c] = f
        v = d["visits"][i].astype(np.float32)
        total = v.sum()
        # A forced move has no visits; the mask alone carries it.
        target[i] = v / total if total > 0 else mask[i] / max(1, mask[i].sum())
    return X, C, mask, target, d["card"].astype(np.int64)


def forward(params, X, C=None):
    """`C` present: the conditioned head — one embedding of the state, then a score per card from
    that embedding and the card's own features."""
    if C is None:
        W1, b1, W2, b2, W3, b3 = params
        a1 = np.maximum(X @ W1.T + b1, 0.0)
        a2 = np.maximum(a1 @ W2.T + b2, 0.0)
        return (a1, a2), a2 @ W3.T + b3
    W1, b1, A, B, b2, w = params
    h = np.maximum(X @ W1.T + b1, 0.0)                      # (n, h1)
    g = np.maximum((h @ A.T)[:, None, :] + C @ B.T + b2, 0.0)  # (n, 36, h2)
    return (h, g), g @ w


def log_softmax_masked(z, mask):
    z = np.where(mask, z, -1e9)
    m = z.max(axis=1, keepdims=True)
    return z - (m + np.log(np.exp(z - m).sum(axis=1, keepdims=True)))


def loss_and_grads(params, X, C, mask, target, l2):
    n = len(X)
    acts, z = forward(params, X, C)
    lp = log_softmax_masked(z, mask)
    loss = float(-(target * lp).sum() / n)
    dz = (np.exp(lp) - target) * mask / n
    if C is None:
        W1, b1, W2, b2, W3, b3 = params
        a1, a2 = acts
        gW3 = dz.T @ a2 + l2 * W3
        gb3 = dz.sum(axis=0)
        d2 = (dz @ W3) * (a2 > 0)
        gW2 = d2.T @ a1 + l2 * W2
        gb2 = d2.sum(axis=0)
        d1 = (d2 @ W2) * (a1 > 0)
        gW1 = d1.T @ X + l2 * W1
        gb1 = d1.sum(axis=0)
        return loss, [gW1, gb1, gW2, gb2, gW3, gb3]
    W1, b1, A, B, b2, w = params
    h, g = acts
    gw = np.einsum("nk,nkh->h", dz, g) + l2 * w
    dg = dz[..., None] * w * (g > 0)                       # (n, 36, h2)
    gb2 = dg.sum(axis=(0, 1))
    gB = np.einsum("nkh,nkf->hf", dg, C) + l2 * B
    dh = dg.sum(axis=1) @ A * (h > 0)                      # A's input is shared across cards
    gA = np.einsum("nkh,nf->hf", dg, h) + l2 * A
    gW1 = dh.T @ X + l2 * W1
    gb1 = dh.sum(axis=0)
    return loss, [gW1, gb1, gA, gB, gb2, gw]


def evaluate(params, X, C, mask, target, played, batch=8192):
    loss, top1, uniform, n = 0.0, 0, 0.0, 0
    for s in range(0, len(X), batch):
        xb = X[s : s + batch].astype(np.float32)
        cb = None if C is None else C[s : s + batch].astype(np.float32)
        mb, tb, pb = mask[s : s + batch], target[s : s + batch], played[s : s + batch]
        lp = log_softmax_masked(forward(params, xb, cb)[1], mb)
        loss += float(-(tb * lp).sum())
        top1 += int((lp.argmax(axis=1) == pb).sum())
        uniform += float(np.log(mb.sum(axis=1)).sum())
        n += len(xb)
    return loss / n, top1 / n, uniform / n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data", type=Path, nargs="+")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hidden", type=int, nargs=2, default=(256, 64))
    ap.add_argument("--head", choices=["conditioned", "flat"], default="conditioned")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--l2", type=float, default=1e-6)
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    t0 = time.time()
    parts, feats = [], []
    for k, path in enumerate(args.data):
        raw = np.load(path)
        part = {key: raw[key] for key in raw.files}
        if "history" not in part:
            raise SystemExit(f"{path} predates the encoder's fields — re-record with policy_data.py")
        part["round_id"] = part["round_id"].astype(np.int64) + k * 10_000_000
        cache = path.with_suffix(".netfeatures.npz")
        if cache.exists() and "C" in np.load(cache).files:
            c = np.load(cache)
            f = (c["X"], c["C"], c["mask"], c["target"], c["played"])
        else:
            f = featurise(part)
            np.savez(cache, X=f[0], C=f[1], mask=f[2], target=f[3], played=f[4])
        parts.append(part)
        feats.append(f)
    d = {"round_id": np.concatenate([p["round_id"] for p in parts])}
    X, C, mask, target, played = (np.concatenate([f[i] for f in feats]) for i in range(5))
    if args.head == "flat":
        C = None
    print(f"{len(X)} decisions featurised in {time.time() - t0:.0f}s")

    held = (d["round_id"] % 10) == 0
    tr, va = np.where(~held)[0], np.where(held)[0]
    print(f"train {len(tr)}  validation {len(va)} (rounds ending in 0)")

    h1, h2 = args.hidden
    rng = np.random.default_rng(args.seed)
    if args.head == "flat":
        params = [
            (rng.standard_normal((h1, N_FEATURES)) * np.sqrt(2 / N_FEATURES)).astype(np.float32),
            np.zeros(h1, dtype=np.float32),
            (rng.standard_normal((h2, h1)) * np.sqrt(2 / h1)).astype(np.float32),
            np.zeros(h2, dtype=np.float32),
            (rng.standard_normal((36, h2)) * 0.01).astype(np.float32),
            np.zeros(36, dtype=np.float32),
        ]
    else:
        params = [
            (rng.standard_normal((h1, N_FEATURES)) * np.sqrt(2 / N_FEATURES)).astype(np.float32),
            np.zeros(h1, dtype=np.float32),
            (rng.standard_normal((h2, h1)) * np.sqrt(2 / h1)).astype(np.float32),
            (rng.standard_normal((h2, N_CARD_FEATURES)) * np.sqrt(2 / N_CARD_FEATURES)).astype(np.float32),
            np.zeros(h2, dtype=np.float32),
            (rng.standard_normal(h2) * 0.01).astype(np.float32),
        ]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    step, best = 0, None
    for epoch in range(args.epochs):
        order = rng.permutation(tr)
        total, seen = 0.0, 0
        rate = args.lr * 0.5 * (1 + np.cos(np.pi * epoch / args.epochs))
        for start in range(0, len(order), args.batch):
            idx = np.sort(order[start : start + args.batch])
            cb = None if C is None else C[idx].astype(np.float32)
            loss, grads = loss_and_grads(params, X[idx].astype(np.float32), cb, mask[idx],
                                         target[idx], args.l2)
            total += loss * len(idx)
            seen += len(idx)
            step += 1
            for i, g in enumerate(grads):
                m[i] = 0.9 * m[i] + 0.1 * g
                v[i] = 0.999 * v[i] + 0.001 * g * g
                params[i] = (params[i] - rate * (m[i] / (1 - 0.9**step)) /
                             (np.sqrt(v[i] / (1 - 0.999**step)) + 1e-8)).astype(np.float32)
        vloss, top1, uniform = evaluate(params, X[va], None if C is None else C[va], mask[va],
                                        target[va], played[va])
        print(f"  epoch {epoch:2d}  train {total / seen:.4f}  val {vloss:.4f}  "
              f"top-1 vs the search {top1:.3f}  (uniform {uniform:.4f})", flush=True)
        if best is None or vloss < best[0]:
            best = (vloss, top1, [p.copy() for p in params], epoch)

    vloss, top1, params, epoch = best
    names = ("W1", "b1", "W2", "b2", "W3", "b3") if args.head == "flat" else ("W1", "b1", "A", "B", "b2", "w")
    np.savez(args.out, **dict(zip(names, params)), head=args.head, decisions=len(X),
             val_loss=vloss, top1=top1, epoch=epoch)
    print(f"best epoch {epoch}: val {vloss:.4f}, top-1 {top1:.3f} — wrote {args.out}")
    print("gate for a match (neural-plan §2A): top-1 >= 0.70" + ("  PASSED" if top1 >= 0.70 else "  not reached"))


if __name__ == "__main__":
    main()
