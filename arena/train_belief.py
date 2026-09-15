"""Train the belief network in `rust/src/beliefnet.rs` on self-play with the true deal.

`logits = W3 · relu(W2 · relu(W1 x + b1) + b2) + b3`, reshaped to 36 cards × 3 seats (left,
partner, right), softmaxed per card over the seats that card is still allowed at. The loss is
the log-probability of the seat that really held it, over every hidden card at every recorded
decision. Inputs come from `rs_belief_features` — the Rust function the search would call — so
there is one feature implementation, not two.

Split by round, never by decision. The headline number is **per-card accuracy** — the mean
probability put on the true seat — against uniform over the allowed seats. That is a marginal;
what the search gets from it is measured in worlds by `arena/belief_quality.py --belief-net`.

Usage::

    python -m arena.train_belief beliefs.npz --out krass_jass/data/belief_net.json
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

N_FEATURES = 865
FULL = (1 << 36) - 1


def _args(d: dict, i: int) -> tuple:
    hist = [(int(s), int(c)) for s, c in d["history"][i] if s >= 0]
    return (
        int(d["seat"][i]), int(d["hand"][i]), hist, int(d["contract"][i]), int(d["declarer"][i]),
        int(d["forehand"][i]), [int(v) for v in d["forbidden"][i]], [int(v) for v in d["known"][i]],
        [int(v) for v in d["weis_called"][i]],
    )


def featurise(d: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Inputs (float16), the allowed mask `(n, 36, 3)` and the true seat per card (-1 if not hidden)."""
    n = len(d["seat"])
    X = np.zeros((n, N_FEATURES), dtype=np.float16)
    allowed = np.zeros((n, 36, 3), dtype=bool)
    target = np.full((n, 36), -1, dtype=np.int8)
    cards = np.arange(36, dtype=np.uint64)
    for i in range(n):
        a = _args(d, i)
        X[i] = np.frombuffer(core.rs_belief_features(*a), dtype=np.float32)
        seat, hand = a[0], a[1]
        played = 0
        for _, c in a[2]:
            played |= 1 << c
        unseen = FULL & ~hand & ~played
        for r in range(1, 4):
            other = (seat + r) % 4
            ok = unseen & ~a[6][other]
            allowed[i, :, r - 1] = (np.uint64(ok) >> cards) & np.uint64(1)
            held = (np.uint64(int(d["truth"][i][other]) & unseen) >> cards) & np.uint64(1)
            target[i, held.astype(bool)] = r - 1
    return X, allowed, target


def forward(params, X):
    W1, b1, W2, b2, W3, b3 = params
    a1 = np.maximum(X @ W1.T + b1, 0.0)
    a2 = np.maximum(a1 @ W2.T + b2, 0.0)
    return a1, a2, (a2 @ W3.T + b3).reshape(len(X), 36, 3)


def log_softmax_masked(z, allowed):
    z = np.where(allowed, z, -1e9)
    m = z.max(axis=2, keepdims=True)
    return z - (m + np.log(np.exp(z - m).sum(axis=2, keepdims=True)))


def loss_and_grads(params, X, allowed, target, l2):
    W1, b1, W2, b2, W3, b3 = params
    a1, a2, z = forward(params, X)
    lp = log_softmax_masked(z, allowed)
    scored = target >= 0
    n_scored = max(1, int(scored.sum()))
    t = np.where(scored, target, 0).astype(np.int64)
    picked = np.take_along_axis(lp, t[..., None], axis=2)[..., 0]
    nll = float(-(picked * scored).sum() / n_scored)
    dz = np.exp(lp)
    np.put_along_axis(dz, t[..., None], np.take_along_axis(dz, t[..., None], axis=2) - 1.0, axis=2)
    dz = np.where(allowed & scored[..., None], dz, 0.0) / n_scored
    dz = dz.reshape(len(X), 108).astype(np.float32)
    gW3 = dz.T @ a2 + l2 * W3
    gb3 = dz.sum(axis=0)
    d2 = (dz @ W3) * (a2 > 0)
    gW2 = d2.T @ a1 + l2 * W2
    gb2 = d2.sum(axis=0)
    d1 = (d2 @ W2) * (a1 > 0)
    gW1 = d1.T @ X + l2 * W1
    gb1 = d1.sum(axis=0)
    return nll, [gW1, gb1, gW2, gb2, gW3, gb3]


def evaluate(params, X, allowed, target, batch=8192):
    acc, uni, nll, n = 0.0, 0.0, 0.0, 0
    for s in range(0, len(X), batch):
        xb = X[s : s + batch].astype(np.float32)
        _, _, z = forward(params, xb)
        lp = log_softmax_masked(z, allowed[s : s + batch])
        tb = target[s : s + batch]
        scored = tb >= 0
        t = np.where(scored, tb, 0).astype(np.int64)
        picked = np.take_along_axis(lp, t[..., None], axis=2)[..., 0]
        k = scored.sum(axis=1)
        keep = k > 0
        # Per decision, then averaged — the unit belief_quality.py and §5k use.
        acc += float((np.where(scored, np.exp(picked), 0).sum(axis=1)[keep] / k[keep]).sum())
        n_allowed = allowed[s : s + batch].sum(axis=2)
        uni += float((np.where(scored, 1.0 / np.maximum(n_allowed, 1), 0).sum(axis=1)[keep] / k[keep]).sum())
        nll += float(-(picked * scored).sum())
        n += int(keep.sum())
    return acc / n, uni / n, nll / max(1, int((target >= 0).sum()))


def to_json(params, meta: dict) -> str:
    W1, b1, W2, b2, W3, b3 = params
    fmt = lambda a: ", ".join(f"{float(x):.5g}" for x in np.ravel(a))  # noqa: E731
    comment = "Trained by arena/train_belief.py; read by rust/src/beliefnet.rs. " + "; ".join(
        f"{k} {v}" for k, v in meta.items())
    return (
        "{\n"
        f'  "_comment": {json.dumps(comment)},\n'
        f'  "n_features": {N_FEATURES},\n  "h1": {W1.shape[0]},\n  "h2": {W2.shape[0]},\n'
        f'  "w1": [{fmt(W1)}],\n  "b1": [{fmt(b1)}],\n  "w2": [{fmt(W2)}],\n  "b2": [{fmt(b2)}],\n'
        f'  "w3": [{fmt(W3)}],\n  "b3": [{fmt(b3)}]\n'
        "}\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data", type=Path, nargs="+")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--h1", type=int, default=128)
    ap.add_argument("--h2", type=int, default=64)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--l2", type=float, default=1e-6)
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    t0 = time.time()
    parts, feats = [], []
    for n, path in enumerate(args.data):
        raw = np.load(path)
        part = {k: raw[k] for k in raw.files}
        # Round ids restart in every file; keep them distinct so the split stays by round.
        part["round_id"] = part["round_id"].astype(np.int64) + n * 10_000_000
        cache = path.with_suffix(".features.npz")
        if cache.exists():
            c = np.load(cache)
            f = (c["X"], c["allowed"], c["target"])
        else:
            f = featurise(part)
            np.savez(cache, X=f[0], allowed=f[1], target=f[2])
        parts.append(part)
        feats.append(f)
    keys = [k for k in parts[0] if np.ndim(parts[0][k]) > 0]
    d = {k: np.concatenate([p[k] for p in parts]) for k in keys}
    d["iterations"] = parts[0]["iterations"]
    X = np.concatenate([f[0] for f in feats])
    allowed = np.concatenate([f[1] for f in feats])
    target = np.concatenate([f[2] for f in feats])
    print(f"{len(X)} decisions from {len(args.data)} file(s) featurised in {time.time() - t0:.0f}s")

    held = (d["round_id"] % 10) == 0
    tr, va = np.where(~held)[0], np.where(held)[0]
    print(f"train {len(tr)}  validation {len(va)} (rounds ending in 0)")

    rng = np.random.default_rng(args.seed)
    params = [
        (rng.standard_normal((args.h1, N_FEATURES)) * np.sqrt(2 / N_FEATURES)).astype(np.float32),
        np.zeros(args.h1, dtype=np.float32),
        (rng.standard_normal((args.h2, args.h1)) * np.sqrt(2 / args.h1)).astype(np.float32),
        np.zeros(args.h2, dtype=np.float32),
        (rng.standard_normal((108, args.h2)) * 0.01).astype(np.float32),
        np.zeros(108, dtype=np.float32),
    ]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    step, best = 0, None
    for epoch in range(args.epochs):
        order = rng.permutation(tr)
        total, seen = 0.0, 0
        rate = args.lr * 0.5 * (1 + np.cos(np.pi * epoch / args.epochs))
        for s in range(0, len(order), args.batch):
            idx = np.sort(order[s : s + args.batch])
            nll, grads = loss_and_grads(params, X[idx].astype(np.float32), allowed[idx], target[idx], args.l2)
            total += nll * len(idx)
            seen += len(idx)
            step += 1
            for i, g in enumerate(grads):
                m[i] = 0.9 * m[i] + 0.1 * g
                v[i] = 0.999 * v[i] + 0.001 * g * g
                params[i] = (params[i] - rate * (m[i] / (1 - 0.9**step)) /
                             (np.sqrt(v[i] / (1 - 0.999**step)) + 1e-8)).astype(np.float32)
        acc, uni, vnll = evaluate(params, X[va], allowed[va], target[va])
        print(f"  epoch {epoch:2d}  train nll {total / seen:.4f}  val nll {vnll:.4f}  "
              f"per-card accuracy {acc:.4f} (uniform over allowed {uni:.4f})", flush=True)
        if best is None or vnll < best[0]:
            best = (vnll, acc, uni, [p.copy() for p in params], epoch)

    vnll, acc, uni, params, epoch = best
    meta = {"decisions": int(len(X)), "search iterations": int(d["iterations"]),
            "validation nll": round(vnll, 4), "per-card accuracy": round(acc, 4),
            "uniform over allowed": round(uni, 4), "epoch": epoch}
    text = to_json(params, meta)

    # Rust and numpy must agree, or the network in play is not the one that was validated.
    worst = 0.0
    sample = va[:200]
    _, _, z = forward(params, X[sample].astype(np.float32))
    lp = log_softmax_masked(z, allowed[sample])
    for j, i in enumerate(sample):
        rs = np.array(core.rs_belief_log_probs(*_args(d, int(i)), text))
        ok = allowed[i]
        worst = max(worst, float(np.abs(np.exp(rs[ok]) - np.exp(lp[j][ok])).max()) if ok.any() else 0.0)
    print(f"rust vs numpy, largest probability difference over {len(sample)} decisions: {worst:.2e}")
    if worst > 1e-3:
        raise SystemExit("rust and numpy disagree about the network")
    args.out.write_text(text)
    print(f"best epoch {epoch}: per-card accuracy {acc:.4f} vs uniform {uni:.4f}; wrote {args.out}")


if __name__ == "__main__":
    main()
