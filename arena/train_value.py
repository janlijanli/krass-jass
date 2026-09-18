"""Train the value network in `rust/src/valuenet.rs`, and hold it to the offline gate.

`fraction = sigmoid(w3 · relu(W2 · relu(W1 x + b1) + b2) + b3)`: the share of the remaining points
the mover's team takes, from the 295 perfect-information inputs `rs_value_features` builds — the
Rust function the search calls, so there is one feature implementation.

**The offline gate** (`docs/neural-plan.md` §2B) is the comparison §5g got wrong. The target is the
*real* outcome of the position under our bot's play, and the network is scored against the
estimator it would replace: the average of k random playouts from the same position. Random
playouts are unbiased only for random play, so no number of them converges on the real outcome —
the table below shows where their error bottoms out, and whether the network beats that floor.

Split by round. Rust and numpy must agree on the trained network, or it is not written.

Usage::

    python -m arena.train_value values.npz --out krass_jass/data/value_net.json
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

N_FEATURES = 295


def _position(d: dict, i: int) -> tuple:
    trick = [int(c) for c in d["trick"][i] if c >= 0]
    return [int(h) for h in d["hands"][i]], trick, int(d["trick_leader"][i]), int(d["contract"][i])


def featurise(d: dict) -> np.ndarray:
    n = len(d["fraction"])
    X = np.zeros((n, N_FEATURES), dtype=np.float16)
    for i in range(n):
        X[i] = np.frombuffer(core.rs_value_features(*_position(d, i)), dtype=np.float32)
    return X


def forward(params, X):
    W1, b1, W2, b2, w3, b3 = params
    a1 = np.maximum(X @ W1.T + b1, 0.0)
    a2 = np.maximum(a1 @ W2.T + b2, 0.0)
    z = a2 @ w3 + b3[0]
    return a1, a2, 1.0 / (1.0 + np.exp(-z))


def loss_and_grads(params, X, y, l2):
    W1, b1, W2, b2, w3, b3 = params
    a1, a2, p = forward(params, X)
    n = len(X)
    eps = 1e-6
    loss = float(-(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)).mean())
    dz = ((p - y) / n).astype(np.float32)          # cross-entropy with a soft label
    gw3 = a2.T @ dz + l2 * w3
    gb3 = np.array([dz.sum()], dtype=np.float32)
    d2 = np.outer(dz, w3) * (a2 > 0)
    gW2 = d2.T @ a1 + l2 * W2
    gb2 = d2.sum(axis=0)
    d1 = (d2 @ W2) * (a1 > 0)
    gW1 = d1.T @ X + l2 * W1
    gb1 = d1.sum(axis=0)
    return loss, [gW1, gb1, gW2, gb2, gw3, gb3]


def predict(params, X, batch=16384):
    return np.concatenate([forward(params, X[s:s + batch].astype(np.float32))[2]
                           for s in range(0, len(X), batch)])


def to_json(params, meta: dict) -> str:
    W1, b1, W2, b2, w3, b3 = params
    fmt = lambda a: ", ".join(f"{float(x):.5g}" for x in np.ravel(a))  # noqa: E731
    comment = "Trained by arena/train_value.py; read by rust/src/valuenet.rs. " + "; ".join(
        f"{k} {v}" for k, v in meta.items())
    return (
        "{\n"
        f'  "_comment": {json.dumps(comment)},\n'
        f'  "n_features": {N_FEATURES},\n  "h1": {W1.shape[0]},\n  "h2": {W2.shape[0]},\n'
        f'  "w1": [{fmt(W1)}],\n  "b1": [{fmt(b1)}],\n  "w2": [{fmt(W2)}],\n  "b2": [{fmt(b2)}],\n'
        f'  "w3": [{fmt(w3)}],\n  "b3": [{fmt(b3)}]\n'
        "}\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hidden", type=int, nargs=2, default=(128, 64))
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--l2", type=float, default=1e-6)
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--gate-positions", type=int, default=4000)
    args = ap.parse_args()

    raw = np.load(args.data)
    d = {k: raw[k] for k in raw.files}
    cache = args.data.with_suffix(".features.npz")
    t0 = time.time()
    if cache.exists():
        X = np.load(cache)["X"]
    else:
        X = featurise(d)
        np.savez(cache, X=X)
    y = d["fraction"].astype(np.float32)
    print(f"{len(X)} positions featurised in {time.time() - t0:.0f}s; mean label {y.mean():.3f}")

    held = (d["round_id"] % 10) == 0
    tr, va = np.where(~held)[0], np.where(held)[0]
    print(f"train {len(tr)}  validation {len(va)} (rounds ending in 0)")

    h1, h2 = args.hidden
    rng = np.random.default_rng(args.seed)
    params = [
        (rng.standard_normal((h1, N_FEATURES)) * np.sqrt(2 / N_FEATURES)).astype(np.float32),
        np.zeros(h1, dtype=np.float32),
        (rng.standard_normal((h2, h1)) * np.sqrt(2 / h1)).astype(np.float32),
        np.zeros(h2, dtype=np.float32),
        (rng.standard_normal(h2) * 0.01).astype(np.float32),
        np.zeros(1, dtype=np.float32),
    ]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    step, best = 0, None
    for epoch in range(args.epochs):
        order = rng.permutation(tr)
        total, seen = 0.0, 0
        rate = args.lr * 0.5 * (1 + np.cos(np.pi * epoch / args.epochs))
        for s in range(0, len(order), args.batch):
            idx = np.sort(order[s:s + args.batch])
            loss, grads = loss_and_grads(params, X[idx].astype(np.float32), y[idx], args.l2)
            total += loss * len(idx)
            seen += len(idx)
            step += 1
            for i, g in enumerate(grads):
                m[i] = 0.9 * m[i] + 0.1 * g
                v[i] = 0.999 * v[i] + 0.001 * g * g
                params[i] = (params[i] - rate * (m[i] / (1 - 0.9**step)) /
                             (np.sqrt(v[i] / (1 - 0.999**step)) + 1e-8)).astype(np.float32)
        rmse = float(np.sqrt(((predict(params, X[va]) - y[va]) ** 2).mean()))
        print(f"  epoch {epoch:2d}  train loss {total / seen:.4f}  validation RMSE {rmse:.4f}", flush=True)
        if best is None or rmse < best[0]:
            best = (rmse, [p.copy() for p in params], epoch)

    rmse, params, epoch = best
    meta = {"positions": int(len(X)), "search iterations": int(d["iterations"]),
            "validation RMSE": round(rmse, 4), "epoch": epoch}
    text = to_json(params, meta)

    # The offline gate: against the estimator it would replace, on the real outcome.
    gate = rng.choice(va, size=min(args.gate_positions, len(va)), replace=False)
    truth = y[gate]
    net = predict(params, X[gate])
    print(f"\nthe offline gate — RMSE against the real outcome on {len(gate)} held-out positions")
    print(f"  {'estimator':<32} {'RMSE':>7}")
    print(f"  {'constant 0.5':<32} {np.sqrt(((0.5 - truth) ** 2).mean()):7.4f}")
    playout_rmse = {}
    for k in (1, 4, 16, 64, 256):
        est = np.array([core.rs_playout_fraction(*_position(d, int(i)), k, 1000 + int(i)) for i in gate])
        playout_rmse[k] = float(np.sqrt(((est - truth) ** 2).mean()))
        print(f"  {'mean of ' + str(k) + ' random playouts':<32} {playout_rmse[k]:7.4f}")
    net_rmse = float(np.sqrt(((net - truth) ** 2).mean()))
    print(f"  {'value network':<32} {net_rmse:7.4f}")
    beats = [k for k, r in playout_rmse.items() if net_rmse < r]
    print("  the network beats " + (f"k = {', '.join(map(str, beats))}" if beats else "no playout count"))

    worst = 0.0
    for i in gate[:300]:
        rs = core.rs_value_eval(*_position(d, int(i)), text)
        worst = max(worst, abs(rs - float(predict(params, X[[i]])[0])))
    print(f"rust vs numpy, largest difference over 300 positions: {worst:.2e}")
    if worst > 1e-3:
        raise SystemExit("rust and numpy disagree about the network")
    args.out.write_text(text)
    print(f"best epoch {epoch}: validation RMSE {rmse:.4f}; wrote {args.out}")


if __name__ == "__main__":
    main()
