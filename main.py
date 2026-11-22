#!/usr/bin/env python3
"""The picture that tastes of one ingredient: a steaming bowl of ramen.

Pure Python 3.13 standard library only. No network, no randomness, no
external files. Renders a 1024x1024 PNG of one appetizing subject -- a
steaming bowl of ramen (rich broth, wavy noodles, soft egg, chashu,
green onions, nori, chopsticks, rising steam) -- and writes it to
/output/entry.png. Fully deterministic: running it twice produces
byte-identical output.

Drawing approach: a small scanline rasterizer over a bytearray frame
buffer (filled circles / ellipses with optional vertical gradients,
thick polylines stamped as circles, alpha-blended steam and gloss),
plus a hand-rolled PNG encoder (zlib + struct + CRC).
"""

import binascii
import hashlib
import math
import os
import struct
import zlib

W = 1024
H = 1024
OUT = "/output/entry.png"


# ---------------------------------------------------------------- colors
def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# Warm background: deep red-brown at the top, amber table at the bottom.
BG_TOP = (72, 20, 12)
BG_BOTTOM = (150, 76, 26)
GLOW = (222, 144, 58)          # warm glow behind the bowl
SHADOW = (48, 14, 8)
BOWL_TOP = (188, 46, 30)       # lacquered red bowl, lit from above
BOWL_BOTTOM = (116, 22, 16)
BOWL_SHADE = (96, 18, 12)
RIM = (206, 58, 38)
RIM_DARK = (88, 18, 12)
BROTH = (204, 108, 30)         # rich golden-orange broth
BROTH_LIGHT = (234, 152, 54)
CHILI = (172, 46, 22)
NOODLE_A = (246, 198, 92)
NOODLE_B = (231, 166, 58)
NOODLE_DARK = (198, 128, 38)
EGG_WHITE = (250, 244, 228)
YOLK = (240, 138, 28)
YOLK_LIGHT = (255, 188, 88)
CHASHU = (216, 132, 110)
CHASHU_EDGE = (168, 88, 72)
CHASHU_LIGHT = (238, 178, 152)
NORI = (24, 56, 36)
NORI_LINE = (16, 38, 24)
ONION = (44, 158, 78)
ONION_LIGHT = (126, 214, 134)
SESAME = (250, 238, 210)
WOOD = (200, 150, 94)
WOOD_DARK = (148, 102, 58)
WHITE = (255, 255, 255)


# ---------------------------------------------------------------- canvas
buf = bytearray(W * H * 3)


def _row_bytes(color):
    return bytes(color)


def fill_rect(x0, y0, x1, y1, color):
    """Fill an axis-aligned rectangle (clipped)."""
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(W - 1, x1)
    y1 = min(H - 1, y1)
    if x1 < x0 or y1 < y0:
        return
    row = _row_bytes(color) * (x1 - x0 + 1)
    for y in range(y0, y1 + 1):
        base = y * W * 3 + x0 * 3
        buf[base:base + len(row)] = row


def fill_circle(cx, cy, r, color):
    """Filled circle, scanline fill."""
    r = int(r)
    row_color = bytes(color)
    for dy in range(-r, r + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        dx = int(math.sqrt(r * r - dy * dy))
        x0 = max(0, cx - dx)
        x1 = min(W - 1, cx + dx)
        if x1 < x0:
            continue
        base = y * W * 3 + x0 * 3
        buf[base:base + (x1 - x0 + 1) * 3] = row_color * (x1 - x0 + 1)


def fill_circle_grad(cx, cy, r, top_color, bottom_color):
    """Filled circle shaded top -> bottom (vertical gradient)."""
    r = int(r)
    for dy in range(-r, r + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        t = (dy + r) / (2.0 * r)
        color = bytes(_lerp(top_color, bottom_color, t))
        dx = int(math.sqrt(r * r - dy * dy))
        x0 = max(0, cx - dx)
        x1 = min(W - 1, cx + dx)
        if x1 < x0:
            continue
        base = y * W * 3 + x0 * 3
        buf[base:base + (x1 - x0 + 1) * 3] = color * (x1 - x0 + 1)


def fill_ellipse(cx, cy, rx, ry, color):
    """Filled axis-aligned ellipse, scanline fill."""
    rx = int(rx)
    ry = int(ry)
    row_color = bytes(color)
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        f = 1.0 - (dy * dy) / float(ry * ry)
        if f < 0:
            continue
        dx = int(rx * math.sqrt(f))
        x0 = max(0, cx - dx)
        x1 = min(W - 1, cx + dx)
        if x1 < x0:
            continue
        base = y * W * 3 + x0 * 3
        buf[base:base + (x1 - x0 + 1) * 3] = row_color * (x1 - x0 + 1)


def fill_ellipse_grad(cx, cy, rx, ry, top_color, bottom_color):
    """Filled ellipse shaded top -> bottom."""
    rx = int(rx)
    ry = int(ry)
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        t = (dy + ry) / (2.0 * ry)
        color = bytes(_lerp(top_color, bottom_color, t))
        f = 1.0 - (dy * dy) / float(ry * ry)
        if f < 0:
            continue
        dx = int(rx * math.sqrt(f))
        x0 = max(0, cx - dx)
        x1 = min(W - 1, cx + dx)
        if x1 < x0:
            continue
        base = y * W * 3 + x0 * 3
        buf[base:base + (x1 - x0 + 1) * 3] = color * (x1 - x0 + 1)


def fill_circle_alpha(cx, cy, r, color, alpha):
    """Filled circle alpha-blended over what is already there."""
    r = int(r)
    ia = 255 - alpha
    for dy in range(-r, r + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        dx = int(math.sqrt(r * r - dy * dy))
        x0 = max(0, cx - dx)
        x1 = min(W - 1, cx + dx)
        for x in range(x0, x1 + 1):
            i = (y * W + x) * 3
            buf[i] = (color[0] * alpha + buf[i] * ia) // 255
            buf[i + 1] = (color[1] * alpha + buf[i + 1] * ia) // 255
            buf[i + 2] = (color[2] * alpha + buf[i + 2] * ia) // 255


def fill_ellipse_alpha(cx, cy, rx, ry, color, alpha):
    """Filled ellipse alpha-blended over what is already there."""
    rx = int(rx)
    ry = int(ry)
    ia = 255 - alpha
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        f = 1.0 - (dy * dy) / float(ry * ry)
        if f < 0:
            continue
        dx = int(rx * math.sqrt(f))
        x0 = max(0, cx - dx)
        x1 = min(W - 1, cx + dx)
        for x in range(x0, x1 + 1):
            i = (y * W + x) * 3
            buf[i] = (color[0] * alpha + buf[i] * ia) // 255
            buf[i + 1] = (color[1] * alpha + buf[i + 1] * ia) // 255
            buf[i + 2] = (color[2] * alpha + buf[i + 2] * ia) // 255


def fill_polygon(points, color):
    """Filled polygon (even-odd scanline fill)."""
    row_color = bytes(color)
    ys = [p[1] for p in points]
    y0 = max(0, int(min(ys)))
    y1 = min(H - 1, int(max(ys)))
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x1, y1p = points[i]
            x2, y2p = points[(i + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                t = (y - y1p) / float(y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(math.ceil(xs[k])))
            xb = min(W - 1, int(math.floor(xs[k + 1])))
            if xb < xa:
                continue
            base = y * W * 3 + xa * 3
            buf[base:base + (xb - xa + 1) * 3] = row_color * (xb - xa + 1)


def thick_line(x0, y0, x1, y1, width, color):
    """Thick line with round caps, stamped as circles."""
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy)
    steps = max(1, int(dist / 2.0))
    r = width / 2.0
    for s in range(steps + 1):
        t = s / float(steps)
        fill_circle(int(x0 + dx * t), int(y0 + dy * t), r, color)


def thick_line_alpha(x0, y0, x1, y1, width, color, alpha):
    """Alpha-blended thick line with round caps."""
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy)
    steps = max(1, int(dist / 2.0))
    r = width / 2.0
    for s in range(steps + 1):
        t = s / float(steps)
        fill_circle_alpha(int(x0 + dx * t), int(y0 + dy * t), r, color, alpha)


def arc_points(cx, cy, rx, ry, deg0, deg1, step=3.0):
    """Points along an ellipse arc, degrees measured clockwise from +x."""
    pts = []
    a = deg0
    while a <= deg1:
        rad = math.radians(a)
        pts.append((int(cx + rx * math.cos(rad)), int(cy + ry * math.sin(rad))))
        a += step
    return pts


def polyline(points, width, color):
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        thick_line(x0, y0, x1, y1, width, color)


def polyline_alpha(points, width, color, alpha):
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        thick_line_alpha(x0, y0, x1, y1, width, color, alpha)


# ---------------------------------------------------------------- helpers
def in_broth(x, y):
    """True when (x, y) lies inside the broth ellipse."""
    return ((x - 512) / 296.0) ** 2 + ((y - 505) / 132.0) ** 2 <= 0.96


def det01(i, salt):
    """Deterministic pseudo-random value in [0, 1) from an integer seed."""
    v = math.sin(i * 12.9898 + salt * 78.233) * 43758.5453
    return v - math.floor(v)


# ---------------------------------------------------------------- scene
def draw_background():
    # Vertical warm gradient, row by row.
    for y in range(H):
        t = y / float(H - 1)
        color = bytes(_lerp(BG_TOP, BG_BOTTOM, t))
        base = y * W * 3
        buf[base:base + W * 3] = color * W
    # Warm glow behind the bowl: nested solid ellipses, warm -> background.
    for k in range(40, 0, -1):
        t = k / 40.0
        rx = int(430 * t)
        ry = int(360 * t)
        color = _lerp(GLOW, _lerp(BG_TOP, BG_BOTTOM, 0.45), 1.0 - t * 0.85)
        fill_ellipse(512, 540, rx, ry, color)


def draw_bowl():
    # Soft shadow under the bowl.
    fill_ellipse_alpha(512, 968, 330, 42, SHADOW, 110)
    fill_ellipse_alpha(512, 962, 280, 32, SHADOW, 90)
    # Lacquered bowl body, lit from above.
    fill_circle_grad(512, 650, 345, BOWL_TOP, BOWL_BOTTOM)
    # Darker shading low on the bowl body, blended at its top edge.
    fill_ellipse_grad(512, 872, 258, 118, BOWL_BOTTOM, (70, 12, 8))
    # Re-draw the lower rim of the body so the shade stays inside it.
    fill_ellipse_grad(512, 650, 345, 150, BOWL_TOP, BOWL_BOTTOM)
    # Rim band and inner edge, then the broth.
    fill_ellipse(512, 500, 335, 168, RIM)
    fill_ellipse(512, 500, 308, 142, RIM_DARK)
    fill_ellipse_grad(512, 505, 296, 132, BROTH_LIGHT, BROTH)
    # Lighter swirl of broth near the top-left.
    fill_ellipse(462, 478, 168, 58, BROTH_LIGHT)
    fill_ellipse(560, 540, 130, 44, (222, 132, 44))
    # Chili-oil ribbons in the broth.
    polyline(arc_points(512, 505, 210, 88, 20, 110), 13, CHILI)
    polyline(arc_points(512, 505, 160, 62, 200, 285), 11, CHILI)


def draw_nori():
    # Dark green nori sheet sticking up at the back of the bowl.
    fill_polygon([(588, 332), (668, 344), (656, 486), (576, 474)], NORI)
    thick_line(606, 348, 598, 468, 5, NORI_LINE)
    thick_line(628, 350, 620, 470, 5, NORI_LINE)
    thick_line(650, 354, 642, 472, 5, NORI_LINE)


def draw_noodles():
    # Wavy noodle strands across the broth, clipped to the broth ellipse.
    for i in range(15):
        y0 = 448 + i * 8
        color = NOODLE_A if i % 2 == 0 else NOODLE_B
        prev = None
        x = 236
        while x <= 792:
            y = int(y0 + 9 * math.sin((x - 236) / 52.0 + i * 1.35)
                    + 4 * math.sin((x - 236) / 23.0 + i * 0.7))
            if in_broth(x, y):
                if prev is not None:
                    thick_line(prev[0], prev[1], x, y, 10, color)
                prev = (x, y)
            else:
                prev = None
            x += 4
    # A few darker noodle shadows for depth.
    for i in range(5):
        y0 = 470 + i * 18
        prev = None
        x = 250
        while x <= 780:
            y = int(y0 + 8 * math.sin((x - 250) / 47.0 + i * 2.0 + 0.5))
            if in_broth(x, y):
                if prev is not None:
                    thick_line(prev[0], prev[1], x, y, 5, NOODLE_DARK)
                prev = (x, y)
            else:
                prev = None
            x += 5


def draw_chashu(cx, cy, r):
    fill_circle(cx, cy, r, CHASHU_EDGE)
    fill_circle(cx, cy, r - 7, CHASHU)
    fill_circle(cx, cy, int(r * 0.55), CHASHU_LIGHT)
    fill_circle(cx, cy, int(r * 0.30), (226, 150, 128))
    # Glossy highlight on the pork.
    fill_circle_alpha(cx - int(r * 0.35), cy - int(r * 0.40), 10, WHITE, 70)


def draw_egg(cx, cy):
    # Halved soft egg: white with a glossy orange yolk.
    fill_ellipse(cx, cy, 80, 58, EGG_WHITE)
    fill_ellipse(cx, cy, 66, 46, (244, 236, 216))
    fill_circle(cx, cy, 35, YOLK)
    fill_circle(cx - 6, cy - 4, 26, (244, 152, 44))
    fill_circle_alpha(cx - 12, cy - 12, 10, YOLK_LIGHT, 150)
    fill_ellipse_alpha(cx - 30, cy - 34, 34, 12, WHITE, 60)


def draw_onions():
    # Green-onion rings scattered over the noodles.
    spots = [
        (300, 470), (340, 545), (430, 452), (470, 560), (520, 448),
        (560, 568), (600, 452), (700, 480), (760, 540), (330, 505),
        (470, 500), (680, 590), (590, 600), (410, 585), (750, 500),
        (540, 520),
    ]
    for (x, y) in spots:
        if not in_broth(x, y):
            continue
        fill_circle(x, y, 11, ONION)
        fill_circle(x, y, 6, ONION_LIGHT)
        fill_circle(x, y, 3, (60, 120, 60))
    # Toasted sesame seeds.
    for i in range(26):
        x = int(280 + det01(i, 1) * 470)
        y = int(450 + det01(i, 2) * 130)
        if in_broth(x, y):
            fill_circle(x, y, 3, SESAME)


def draw_chopsticks():
    # Wooden chopsticks resting across the upper-right rim.
    thick_line(648, 448, 936, 344, 17, WOOD)
    thick_line(668, 474, 950, 376, 17, WOOD)
    thick_line(880, 362, 936, 344, 17, WOOD_DARK)
    thick_line(894, 394, 950, 376, 17, WOOD_DARK)
    fill_circle_alpha(700, 428, 6, WHITE, 60)


def draw_gloss():
    # Gloss highlight along the upper-left rim.
    polyline_alpha(arc_points(512, 500, 322, 156, 150, 235), 12, WHITE, 70)
    # Glossy sheen on the broth surface.
    fill_ellipse_alpha(430, 452, 96, 24, WHITE, 46)
    # Faint specular sheen on the bowl body.
    fill_ellipse_alpha(330, 780, 40, 60, WHITE, 12)


def draw_steam():
    # Three rising steam curls above the bowl, soft white and translucent.
    for c in range(3):
        cx0 = 398 + c * 112
        phase = c * 2.1
        pts = []
        for s in range(41):
            t = s / 40.0
            y = int(368 - t * 268)
            x = int(cx0 + 30 * math.sin(t * 8.5 + phase)
                    + 12 * math.sin(t * 4.3 + phase * 1.7))
            pts.append((x, y))
        for s in range(len(pts) - 1):
            t = s / float(len(pts) - 1)
            width = 17 - 10 * t
            alpha = int(88 - 46 * t)
            thick_line_alpha(pts[s][0], pts[s][1], pts[s + 1][0],
                             pts[s + 1][1], width, WHITE, alpha)
        # Brighter thin core so the curl reads as steam, not smoke.
        core = [(x + 4, y) for (x, y) in pts]
        for s in range(len(core) - 1):
            t = s / float(len(core) - 1)
            thick_line_alpha(core[s][0], core[s][1], core[s + 1][0],
                             core[s + 1][1], 6 - 3 * t, WHITE,
                             int(70 - 40 * t))


# ---------------------------------------------------------------- png
def _chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    return out


def encode_png():
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += buf[y * W * 3:(y + 1) * W * 3]
    comp = zlib.compress(bytes(raw), 6)
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", comp)
    png += _chunk(b"IEND", b"")
    return png


def main():
    draw_background()
    draw_bowl()
    draw_nori()
    draw_noodles()
    draw_chashu(716, 556, 58)
    draw_chashu(640, 520, 66)
    draw_egg(392, 500)
    draw_onions()
    draw_chopsticks()
    draw_gloss()
    draw_steam()
    png = encode_png()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(png)
    print("wrote %s %d bytes sha256=%s" % (
        OUT, len(png), hashlib.sha256(png).hexdigest()))


if __name__ == "__main__":
    main()
