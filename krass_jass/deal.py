"""The shared deal. Mirror of `rust/src/deal.rs` — the two must agree exactly.

A game seed has to produce the same deal in every implementation, or "any game replays
bit-for-bit" is only true inside one language. Python's own `random` cannot be reproduced in
Rust, so the algorithm is specified rather than borrowed:

1. stream = SplitMix64(seed, round)
2. Fisher-Yates over 36 cards, descending, index by Lemire multiply-shift
3. cards 0..9 to seat 0, 9..18 to seat 1, and so on

`tests/test_game_port.py` asserts both produce identical hands. Change one, change both.
"""

from __future__ import annotations

MASK64 = (1 << 64) - 1
NUM_SEATS = 4


class Rng:
    """xorshift64, seeded through SplitMix64. Same constants as `rust/src/rng.rs`."""

    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        self.state = seed & MASK64 or 0x9E3779B97F4A7C15

    @classmethod
    def split(cls, seed: int, index: int) -> "Rng":
        z = (seed + index * 0x9E3779B97F4A7C15) & MASK64
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return cls(z ^ (z >> 31))

    def next_u64(self) -> int:
        x = self.state
        x = (x ^ (x << 13)) & MASK64
        x ^= x >> 7
        x = (x ^ (x << 17)) & MASK64
        self.state = x
        return x

    def below(self, n: int) -> int:
        """Uniform in [0, n). Lemire multiply-shift — no division."""
        return (self.next_u64() * n) >> 64


def deal(seed: int, round_index: int = 0) -> list[int]:
    rng = Rng.split(seed, round_index)
    deck = list(range(36))
    for i in range(35, 0, -1):
        j = rng.below(i + 1)
        deck[i], deck[j] = deck[j], deck[i]
    hands = [0] * NUM_SEATS
    for i, card in enumerate(deck):
        hands[i // 9] |= 1 << card
    return hands
