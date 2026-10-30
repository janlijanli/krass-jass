"""The app icon: two cards on the felt, the front one a heart.

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

FELT = (0x1D, 0x5B, 0x45)
FELT_DARK = (0x16, 0x44, 0x2F)
PAPER = (0xFB, 0xFA, 0xF7)
GOLD = (0xD8, 0xB4, 0x5A)
RED = (0xB6, 0x21, 0x2C)
EDGE = (0x9A, 0x96, 0x8C)


def _rounded_box(x: float, y: float, cx: float, cy: float, hw: float, hh: float,
                 r: float, angle: float) -> float:
    """Distance to a rounded rectangle rotated by `angle` radians about its centre."""
    c, s = math.cos(angle), math.sin(angle)
    px, py = x - cx, y - cy
    px, py = c * px + s * py, -s * px + c * py
    qx, qy = abs(px) - hw + r, abs(py) - hh + r
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    return outside + min(max(qx, qy), 0.0) - r


def _heart(x: float, y: float, cx: float, cy: float, a: float, angle: float) -> float:
    """Distance to a heart: a square stood on its corner, with a circle on each upper side."""
    c, s = math.cos(angle), math.sin(angle)
    px, py = x - cx, y - cy
    px, py = c * px + s * py, -s * px + c * py + 0.073 * a  # centre the shape's height
    k = a / (2 * math.sqrt(2))
    d = min(math.hypot(px + k, py + k), math.hypot(px - k, py + k)) - a / 2
    rx, ry = (px + py) / math.sqrt(2), (py - px) / math.sqrt(2)
    qx, qy = abs(rx) - a / 2, abs(ry) - a / 2
    square = math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0)
    return min(d, square)


def _over(base: tuple[float, ...], top: tuple[int, ...], alpha: float) -> tuple[float, ...]:
    return tuple(b + (t - b) * alpha for b, t in zip(base, top))


def _cover(distance: float, pixel: float) -> float:
    return min(max(0.5 - distance / pixel, 0.0), 1.0)


def render(size: int) -> bytes:
    """The icon at `size` x `size`, as PNG bytes."""
    pixel = 1.0 / size
    back = dict(cx=0.42, cy=0.53, hw=0.165, hh=0.235, r=0.03, angle=math.radians(-14))
    front = dict(cx=0.57, cy=0.49, hw=0.165, hh=0.235, r=0.03, angle=math.radians(9))
    rows = bytearray()
    for j in range(size):
        rows.append(0)  # PNG filter type: none
        y = (j + 0.5) * pixel
        for i in range(size):
            x = (i + 0.5) * pixel
            t = min(math.hypot((x - 0.5) / 1.2, y / 0.9), 1.0)
            colour: tuple[float, ...] = _over(FELT, FELT_DARK, t)

            d = _rounded_box(x, y, **back)
            colour = _over(colour, EDGE, _cover(d, pixel))
            colour = _over(colour, GOLD, _cover(d + 0.006, pixel))
            colour = _over(colour, PAPER, _cover(abs(d + 0.03) - 0.004, pixel))

            d = _rounded_box(x, y, **front)
            colour = _over(colour, EDGE, _cover(d, pixel))
            colour = _over(colour, PAPER, _cover(d + 0.006, pixel))
            colour = _over(colour, RED, _cover(_heart(x, y, 0.57, 0.49, 0.13, front["angle"]), pixel))

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
