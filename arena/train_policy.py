"""Fit the play model in `rust/src/playmodel.rs` to recorded decisions.

A card-scoring network: `logit(card) = skip · x + w2 · relu(W1 x + b1)`, softmaxed over the
legal cards, where `x` is the feature vector `rs_play_features` computes — the same Rust
function the search calls, so there is no second implementation of the features to drift.

The target is the card actually played. For belief inference that is the right target: the
likelihood being asked for is "how probable was *the card this seat played*", not how the
search spread its visits.

Split by round, never by decision — plays from one round are correlated, and a split by
decision leaks the round's own context into the held-out set.

Usage::

    python -m arena.train_policy decisions.npz --out krass_jass/data/play_policy.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

import krass_jass_core as core  # noqa: E402

MAX_LEGAL = 9
N_FEATURES = 36


def featurise(d: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(d["card"])
    X = np.zeros((n, MAX_LEGAL, N_FEATURES), dtype=np.float32)
    mask = np.zeros((n, MAX_LEGAL), dtype=bool)
    y = np.zeros(n, dtype=np.int64)
    for i in range(n):
        legal = int(d["legal"][i])
        trick = [int(c) for c in d["trick"][i] if c >= 0]
        feats = core.rs_play_features(
            int(d["hand"][i]), int(d["live"][i]), trick, int(d["trick_leader"][i]),
            int(d["seat"][i]), int(d["contract"][i]), int(d["declarer"][i]), legal,
        )
        cards = [c for c in range(36) if legal >> c & 1]
        X[i, : len(feats)] = feats
        mask[i, : len(feats)] = True
        y[i] = cards.index(int(d["card"][i]))
    return X, mask, y


def forward(params, X, mask):
    W1, b1, w2, skip = params
    h = X @ W1.T + b1
    a = np.maximum(h, 0.0)
    z = X @ skip + a @ w2
    z = np.where(mask, z, -1e9)
    z = z - z.max(axis=1, keepdims=True)
    p = np.exp(z)
    p /= p.sum(axis=1, keepdims=True)
    return h, a, p


def loss_and_grads(params, X, mask, y, l2):
    W1, b1, w2, skip = params
    n = len(y)
    h, a, p = forward(params, X, mask)
    rows = np.arange(n)
    nll = -np.log(np.maximum(p[rows, y], 1e-12)).mean()
    dz = p.copy()
    dz[rows, y] -= 1.0
    dz = np.where(mask, dz, 0.0) / n
    g_skip = np.einsum("nk,nkf->f", dz, X) + l2 * skip
    g_w2 = np.einsum("nk,nkh->h", dz, a) + l2 * w2
    dh = dz[..., None] * w2 * (h > 0)
    g_W1 = np.einsum("nkh,nkf->hf", dh, X) + l2 * W1
    g_b1 = dh.sum(axis=(0, 1))
    return nll, [g_W1, g_b1, g_w2, g_skip]


def evaluate(params, X, mask, y):
    _, _, p = forward(params, X, mask)
    rows = np.arange(len(y))
    nll = float(-np.log(np.maximum(p[rows, y], 1e-12)).mean())
    top1 = float((p.argmax(axis=1) == y).mean())
    uniform = float(np.log(mask.sum(axis=1)).mean())
    return nll, top1, uniform


def train(X, mask, y, hidden, epochs, lr, l2, batch, seed):
    rng = np.random.default_rng(seed)
    params = [
        (rng.standard_normal((hidden, N_FEATURES)) * 0.3).astype(np.float32),
        np.zeros(hidden, dtype=np.float32),
        (rng.standard_normal(hidden) * 0.1).astype(np.float32),
        np.zeros(N_FEATURES, dtype=np.float32),
    ]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    step = 0
    n = len(y)
    for epoch in range(epochs):
        order = rng.permutation(n)
        total = 0.0
        for start in range(0, n, batch):
            idx = order[start : start + batch]
            nll, grads = loss_and_grads(params, X[idx], mask[idx], y[idx], l2)
            total += nll * len(idx)
            step += 1
            rate = lr * (0.5 * (1 + np.cos(np.pi * epoch / epochs)))
            for i, g in enumerate(grads):
                m[i] = 0.9 * m[i] + 0.1 * g
                v[i] = 0.999 * v[i] + 0.001 * g * g
                mh = m[i] / (1 - 0.9**step)
                vh = v[i] / (1 - 0.999**step)
                params[i] = (params[i] - rate * mh / (np.sqrt(vh) + 1e-8)).astype(np.float32)
        yield epoch, total / n, params


def to_json(params, meta: dict) -> str:
    W1, b1, w2, skip = params

    def fmt(a):
        return ", ".join(f"{float(x):.6g}" for x in np.ravel(a))

    comment = (
        "Trained by arena/train_policy.py; read by rust/src/playmodel.rs. "
        + "; ".join(f"{k} {v}" for k, v in meta.items())
    )
    return (
        "{\n"
        f'  "_comment": {json.dumps(comment)},\n'
        f'  "n_features": {N_FEATURES},\n'
        f'  "n_hidden": {W1.shape[0]},\n'
        f'  "w1": [{fmt(W1)}],\n'
        f'  "b1": [{fmt(b1)}],\n'
        f'  "w2": [{fmt(w2)}],\n'
        f'  "skip": [{fmt(skip)}]\n'
        "}\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hidden", type=int, default=32)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--l2", type=float, default=1e-5)
    ap.add_argument("--batch", type=int, default=2048)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    raw = np.load(args.data)
    d = {k: raw[k] for k in raw.files}
    cache = args.data.with_suffix(".features.npz")
    t = time.time()
    if cache.exists():
        c = np.load(cache)
        X, mask, y = c["X"], c["mask"], c["y"]
    else:
        X, mask, y = featurise(d)
        np.savez(cache, X=X, mask=mask, y=y)
    print(f"{len(y)} decisions featurised in {time.time() - t:.0f}s")

    rounds = d["round_id"]
    held_out = (rounds % 10) == 0
    tr, va = ~held_out, held_out
    print(f"train {tr.sum()}  validation {va.sum()} (rounds ending in 0)")

    best = None
    for epoch, train_nll, params in train(
        X[tr], mask[tr], y[tr], args.hidden, args.epochs, args.lr, args.l2, args.batch, args.seed
    ):
        nll, top1, uniform = evaluate(params, X[va], mask[va], y[va])
        print(f"  epoch {epoch:2d}  train {train_nll:.4f}  val {nll:.4f}  top-1 {top1:.3f}  "
              f"(uniform {uniform:.4f})", flush=True)
        if best is None or nll < best[0]:
            best = (nll, top1, uniform, [p.copy() for p in params], epoch)

    nll, top1, uniform, params, epoch = best
    meta = {
        "decisions": int(len(y)),
        "search iterations": int(d["iterations"]),
        "validation nll": round(nll, 4),
        "uniform nll": round(uniform, 4),
        "top-1": round(top1, 3),
        "epoch": epoch,
    }
    text = to_json(params, meta)
    args.out.write_text(text)
    print(f"best epoch {epoch}: val nll {nll:.4f} vs uniform {uniform:.4f}, top-1 {top1:.3f}")

    # The numpy forward pass and the Rust one must agree, or the model in play is not the
    # model that was validated.
    idx = np.where(va)[0][:300]
    _, _, p = forward(params, X[idx], mask[idx])
    worst = 0.0
    for j, i in enumerate(idx):
        trick = [int(c) for c in d["trick"][i] if c >= 0]
        rs = core.rs_play_log_probs(
            int(d["hand"][i]), int(d["live"][i]), trick, int(d["trick_leader"][i]),
            int(d["seat"][i]), int(d["contract"][i]), int(d["declarer"][i]), int(d["legal"][i]),
            1.0, text,
        )
        for k, (_, lp) in enumerate(rs):
            worst = max(worst, abs(np.exp(lp) - p[j, k]))
    print(f"rust vs numpy, largest probability difference over 300 decisions: {worst:.2e}")
    if worst > 1e-3:
        raise SystemExit("rust and numpy disagree about the model")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
