"""Throughput ceiling probe for `docs/plan-review.md` §1.

Not the M1 benchmark harness — this is a one-off, deliberately optimistic pure-Python
bitboard Jass rollout, to get an order-of-magnitude
rounds/sec. Card index = suit*9 + rank (rank 0=A .. 8=6). Deliberately favourable:
precomputed suit masks, table-driven trump ordering, no undertrump rule, no Weis,
no object allocation in the hot loop."""
import random, time

SUIT_MASK = [((1 << 9) - 1) << (9 * s) for s in range(4)]
# trump strength: J(idx3) > 9(idx5) > A K Q 10 8 7 6
TRUMP_ORD = {3: 8, 5: 7, 0: 6, 1: 5, 2: 4, 4: 3, 6: 2, 7: 1, 8: 0}
PLAIN_ORD = {r: 8 - r for r in range(9)}
VAL_PLAIN = [11, 4, 3, 2, 10, 0, 0, 0, 0]
VAL_TRUMP = [11, 4, 3, 20, 10, 14, 0, 0, 0]

def rollout(rng, trump):
    deck = list(range(36)); rng.shuffle(deck)
    hands = [0, 0, 0, 0]
    for i, c in enumerate(deck):
        hands[i // 9] |= 1 << c
    lead = 0; pts = [0, 0]
    for _ in range(9):
        trick = []; led_suit = -1
        for k in range(4):
            seat = (lead + k) & 3
            h = hands[seat]
            if k == 0:
                legal = h
            else:
                follow = h & SUIT_MASK[led_suit]
                tr = h & SUIT_MASK[trump]
                legal = (follow | tr) if follow else h
            # pick a random set bit without materialising the list twice
            n = bin(legal).count("1")
            pick = rng.randrange(n)
            m = legal
            for _ in range(pick):
                m &= m - 1
            card = (m & -m).bit_length() - 1
            hands[seat] ^= 1 << card
            if k == 0:
                led_suit = card // 9
            trick.append((seat, card))
        best_seat = -1; best_key = (-1, -1)
        tp = 0
        for seat, card in trick:
            s, r = divmod(card, 9)
            if s == trump:
                tp += VAL_TRUMP[r]; key = (1, TRUMP_ORD[r])
            else:
                tp += VAL_PLAIN[r]
                key = (0, PLAIN_ORD[r]) if s == led_suit else (-1, 0)
            if key > best_key:
                best_key = key; best_seat = seat
        pts[best_seat & 1] += tp
        lead = best_seat
    pts[lead & 1] += 5
    return pts

rng = random.Random(1)
rollout(rng, 0)
N = 20000
t = time.perf_counter()
for _ in range(N):
    rollout(rng, 0)
d = time.perf_counter() - t
print(f"{N/d:,.0f} rounds/sec   ({N*36/d:,.0f} card-plays/sec)   [{d:.2f}s]")
