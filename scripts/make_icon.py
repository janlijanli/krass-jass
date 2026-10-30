"""The app icon: four cards fanned in the hand, one of each suit, on the felt.

Drawn from signed distance functions and written as PNG with the standard library, so the
build needs no image tooling and no binary sits in git. Antialiasing comes from the
distance itself: a pixel's coverage is how far inside the edge its centre lies.

The background is full-bleed and opaque. iOS rounds the corners itself and fills any
transparency with black; Android crops "maskable" icons to a circle, so everything that
matters stays within 0.4 of the centre.
"""

from __future__ import annotations

import math
import struct
import zlib

FELT = (0x1F, 0x5C, 0x49)
FELT_DARK = (0x0B, 0x28, 0x1F)
PAPER = (0xFD, 0xFB, 0xF6)
RED = (0xC0, 0x26, 0x2F)
BLACK = (0x1B, 0x1B, 0x1B)
EDGE = (0x9A, 0x96, 0x8C)

# The fan: each card turns about a point below the hand, like cards held in one hand.
# Red and black alternate, as in the app's own hand.
PIVOT = (0.5, 0.9)
FAN = [("C", -24.0), ("D", -8.0), ("S", 8.0), ("H", 24.0)]
CARD = dict(cx=0.5, cy=0.47, hw=0.14, hh=0.205, r=0.024)
# Each card shows its suit where a hand is read: the top-left corner, the one strip the next
# card leaves uncovered. The front card also carries a large pip in the middle.
CORNER = (CARD["cx"] - CARD["hw"] + 0.052, CARD["cy"] - CARD["hh"] + 0.068)
CORNER_SIZE = 0.042
PIP = (CARD["cx"] + 0.012, CARD["cy"] + 0.01)
PIP_SIZE = 0.08


def _box(px: float, py: float, hw: float, hh: float, r: float) -> float:
    """Distance to a rounded rectangle centred on the origin."""
    qx, qy = abs(px) - hw + r, abs(py) - hh + r
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r


def _convex(px: float, py: float, points: list[tuple[float, float]]) -> float:
    """Distance (exact enough to antialias) to a convex polygon, points clockwise on screen."""
    d = -math.inf
    for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
        nx, ny = by - ay, ax - bx
        length = math.hypot(nx, ny)
        d = max(d, ((px - ax) * nx + (py - ay) * ny) / length)
    return d


def _heart(px: float, py: float, a: float) -> float:
    """A square stood on its corner with a circle on each upper side, centred on the origin."""
    py += 0.073 * a
    k = a / (2 * math.sqrt(2))
    d = min(math.hypot(px + k, py + k), math.hypot(px - k, py + k)) - a / 2
    rx, ry = (px + py) / math.sqrt(2), (py - px) / math.sqrt(2)
    qx, qy = abs(rx) - a / 2, abs(ry) - a / 2
    return min(d, math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0))


def _pip(suit: str, px: float, py: float, s: float) -> float:
    """The four suits, in the same silhouettes as the app's cards (cards.js), size `s`."""
    if suit == "H":
        return _heart(px, py, 1.25 * s)
    if suit == "D":
        w, h = 0.74 * s, s
        return (abs(px) * h + abs(py) * w - w * h) / math.hypot(w, h)
    if suit == "S":
        blade = _heart(px, -(py + 0.28 * s), 0.98 * s)      # a heart turned over
        stem = _convex(px, py, [(0.0, 0.2 * s), (0.34 * s, s), (-0.34 * s, s)])
        return min(blade, stem)
    # C: three lobes that do not touch, and a stem that flares at its foot
    r = 0.36 * s
    lobes = min(
        math.hypot(px, py + 0.6 * s) - r,
        math.hypot(px + 0.58 * s, py - 0.12 * s) - r,
        math.hypot(px - 0.58 * s, py - 0.12 * s) - r,
    )
    stem = _convex(px, py, [(0.0, -0.25 * s), (0.32 * s, s), (-0.32 * s, s)])
    return min(lobes, stem)


def _over(base: tuple[float, ...], top: tuple[int, ...], alpha: float) -> tuple[float, ...]:
    return tuple(b + (t - b) * alpha for b, t in zip(base, top))


def _cover(distance: float, pixel: float) -> float:
    return min(max(0.5 - distance / pixel, 0.0), 1.0)


def render(size: int) -> bytes:
    """The icon at `size` x `size`, as PNG bytes."""
    pixel = 1.0 / size
    turns = [(suit, math.cos(math.radians(a)), math.sin(math.radians(a))) for suit, a in FAN]
    rows = bytearray()
    for j in range(size):
        rows.append(0)  # PNG filter type: none
        y = (j + 0.5) * pixel
        for i in range(size):
            x = (i + 0.5) * pixel
            t = min(math.hypot((x - 0.5) / 1.2, y / 0.9), 1.0)
            colour: tuple[float, ...] = _over(FELT, FELT_DARK, t)

            for suit, c, s in turns:
                # Into the card's own frame: turn the pixel back about the pivot.
                dx, dy = x - PIVOT[0], y - PIVOT[1]
                lx, ly = PIVOT[0] + c * dx + s * dy, PIVOT[1] - s * dx + c * dy
                d = _box(lx - CARD["cx"], ly - CARD["cy"], CARD["hw"], CARD["hh"], CARD["r"])
                if d > pixel:
                    continue
                colour = _over(colour, EDGE, _cover(d, pixel))
                colour = _over(colour, PAPER, _cover(d + 0.005, pixel))
                ink = RED if suit in "HD" else BLACK
                pip = _pip(suit, lx - CORNER[0], ly - CORNER[1], CORNER_SIZE)
                if suit == FAN[-1][0]:
                    pip = min(pip, _pip(suit, lx - PIP[0], ly - PIP[1], PIP_SIZE))
                colour = _over(colour, ink, _cover(pip, pixel))

            rows.extend(round(c) for c in colour)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(
            ">I", zlib.crc32(kind + data) & 0xFFFFFFFF
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )
