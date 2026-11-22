#!/usr/bin/env python3
"""The picture that tastes of one ingredient: a steaming bowl of ramen.

Pure Python 3.13 standard library only. No network, no randomness,
no external files. Renders a 1024x1024 PNG to /output/entry.png.

Approach: a small software rasterizer over a bytearray canvas.
Everything is drawn with filled ellipses, thick polylines and
sine-wave noodle strands, blended with per-pixel alpha.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024
OUT = "/output/entry.png"


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.pix = bytearray(w * h * 3)

    def blend(self, x, y, r, g, b, a=1.0):
        if a <= 0.0:
            return
        ix = int(x)
        iy = int(y)
        if ix < 0 or iy < 0 or ix >= self.w or iy >= self.h:
            return
        i = (iy * self.w + ix) * 3
        if a >= 1.0:
            self.pix[i] = r
            self.pix[i + 1] = g
            self.pix[i + 2] = b
            return
        self.pix[i] = int(self.pix[i] * (1.0 - a) + r * a)
        self.pix[i + 1] = int(self.pix[i + 1] * (1.0 - a) + g * a)
        self.pix[i + 2] = int(self.pix[i + 2] * (1.0 - a) + b * a)

    def disc(self, cx, cy, rad, col, a=1.0):
        r0 = int(cx - rad - 1)
        r1 = int(cx + rad + 1)
        c0 = int(cy - rad - 1)
        c1 = int(cy + rad + 1)
        for y in range(max(0, c0), min(self.h, c1 + 1)):
            for x in range(max(0, r0), min(self.w, r1 + 1)):
                dx = (x + 0.5 - cx) / rad
                dy = (y + 0.5 - cy) / rad
                if dx * dx + dy * dy <= 1.0:
                    self.blend(x, y, col[0], col[1], col[2], a)

    def ellipse(self, cx, cy, rx, ry, col, a=1.0):
        for y in range(max(0, int(cy - ry - 1)), min(self.h, int(cy + ry + 1) + 1)):
            for x in range(max(0, int(cx - rx - 1)), min(self.w, int(cx + rx + 1) + 1)):
                dx = (x + 0.5 - cx) / rx
                dy = (y + 0.5 - cy) / ry
                if dx * dx + dy * dy <= 1.0:
                    self.blend(x, y, col[0], col[1], col[2], a)

    def ring(self, cx, cy, rx, ry, thick, col, a=1.0):
        for y in range(max(0, int(cy - ry - 1)), min(self.h, int(cy + ry + 1) + 1)):
            for x in range(max(0, int(cx - rx - 1)), min(self.w, int(cx + rx + 1) + 1)):
                dx = (x + 0.5 - cx) / rx
                dy = (y + 0.5 - cy) / ry
                d = dx * dx + dy * dy
                if d <= 1.0 and d >= (1.0 - thick / rx) ** 2:
                    self.blend(x, y, col[0], col[1], col[2], a)

    def hline(self, x0, x1, y, col, a=1.0):
        for x in range(max(0, int(x0)), min(self.w, int(x1) + 1)):
            self.blend(x, y, col[0], col[1], col[2], a)

    def thick_line(self, x0, y0, x1, y1, width, col, a=1.0):
        dx = x1 - x0
        dy = y1 - y0
        dist = math.hypot(dx, dy)
        steps = max(1, int(dist * 1.5))
        for s in range(steps + 1):
            t = s / steps
            self.disc(x0 + dx * t, y0 + dy * t, width / 2.0, col, a)

    def wavy(self, x0, x1, ybase, amp, freq, phase, width, col, a=1.0,
              clip=None):
        steps = int(x1 - x0)
        for s in range(steps + 1):
            x = x0 + s
            y = ybase + amp * math.sin(freq * s + phase)
            if clip is not None:
                cx, cy, rx, ry = clip
                dx = (x - cx) / rx
                dy = (y - cy) / ry
                if dx * dx + dy * dy > 1.0:
                    continue
            self.disc(x, y, width / 2.0, col, a)

    def soft_disc(self, cx, cy, rad, col, a=0.35):
        """A disc whose alpha fades towards the edge (for steam/glow)."""
        for y in range(max(0, int(cy - rad)), min(self.h, int(cy + rad) + 1)):
            for x in range(max(0, int(cx - rad)), min(self.w, int(cx + rad) + 1)):
                dx = (x + 0.5 - cx) / rad
                dy = (y + 0.5 - cy) / rad
                d2 = dx * dx + dy * dy
                if d2 <= 1.0:
                    self.blend(x, y, col[0], col[1], col[2],
                               a * (1.0 - d2))


def lerp_col(c1, c2, t):
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


# ---------------------------------------------------------------- palette
BG_TOP = (74, 18, 12)
BG_MID = (146, 42, 18)
BG_LOW = (214, 96, 32)
TABLE = (96, 52, 26)
TABLE_DARK = (70, 36, 18)
BOWL_RED = (178, 32, 22)
BOWL_DARK = (122, 18, 14)
BOWL_RIM = (246, 226, 196)
BROTH = (224, 138, 38)
BROTH_DEEP = (188, 96, 22)
NOODLE = (250, 214, 130)
NOODLE_SHADE = (228, 176, 84)
EGG_WHITE = (250, 244, 226)
YOLK = (244, 158, 26)
YOLK_DEEP = (226, 116, 12)
CHASHU = (238, 178, 158)
CHASHU_EDGE = (196, 96, 72)
NARUTO = (252, 248, 240)
PINK = (238, 96, 128)
GREEN = (74, 160, 64)
GREEN_DARK = (38, 110, 44)
NORI = (32, 64, 40)
CHOP = (124, 72, 32)
CHOP_TIP = (84, 48, 20)
WHITE = (255, 255, 255)
CREAM = (255, 238, 210)


# ---------------------------------------------------------------- picture
def draw(cv):
    # Warm vertical background gradient.
    for y in range(H):
        t = y / (H - 1)
        if t < 0.55:
            col = lerp_col(BG_TOP, BG_MID, t / 0.55)
        else:
            col = lerp_col(BG_MID, BG_LOW, (t - 0.55) / 0.45)
        for x in range(W):
            i = (y * W + x) * 3
            cv.pix[i] = col[0]
            cv.pix[i + 1] = col[1]
            cv.pix[i + 2] = col[2]

    # Soft golden glow behind the bowl.
    cv.soft_disc(512, 620, 430, (255, 176, 84), 0.30)
    cv.soft_disc(512, 620, 300, (255, 205, 120), 0.22)

    # Wooden table band along the bottom.
    for y in range(828, H):
        t = (y - 828) / (H - 828)
        col = lerp_col(TABLE, TABLE_DARK, t)
        for x in range(W):
            i = (y * W + x) * 3
            cv.pix[i] = col[0]
            cv.pix[i + 1] = col[1]
            cv.pix[i + 2] = col[2]
    cv.hline(0, W, 828, (60, 30, 14), 0.8)
    cv.hline(0, W, 900, (60, 30, 14), 0.35)
    cv.hline(0, W, 962, (60, 30, 14), 0.35)

    # Bowl shadow on the table.
    cv.ellipse(512, 872, 330, 42, (40, 16, 8), 0.55)

    # Bowl body: deep red, darker toward the base, cream rim.
    cv.ellipse(512, 640, 372, 268, BOWL_RED)
    cv.ellipse(512, 700, 330, 200, BOWL_DARK, 0.45)
    cv.ring(512, 640, 372, 268, 26, BOWL_RIM, 1.0)
    cv.ring(512, 640, 346, 246, 10, (214, 84, 52), 0.9)
    # Foot of the bowl.
    cv.ellipse(512, 884, 150, 34, BOWL_DARK)
    cv.ellipse(512, 876, 150, 30, BOWL_RED)
    cv.ring(512, 876, 150, 30, 8, BOWL_RIM, 0.85)

    # Decorative gold dots on the bowl front.
    for k in range(9):
        ang = math.pi * (0.18 + 0.09 * k)
        x = 512 + 330 * math.cos(ang)
        y = 640 + 232 * math.sin(ang)
        cv.disc(x, y, 9, (255, 196, 110), 0.95)

    # Broth surface, glossy and golden.
    broth = (512, 610, 316, 196)
    cv.ellipse(512, 610, 316, 196, BROTH_DEEP)
    cv.ellipse(512, 602, 300, 182, BROTH)
    cv.ellipse(430, 556, 150, 62, (244, 172, 66), 0.8)
    cv.ellipse(620, 660, 120, 48, (206, 116, 30), 0.55)

    # Noodle strands: layered sine waves clipped to the broth.
    noodle_rows = [
        (470, 16, 0.055, 0.0, 15),
        (500, 13, 0.062, 1.1, 14),
        (530, 16, 0.050, 2.2, 15),
        (560, 13, 0.066, 3.0, 14),
        (590, 16, 0.054, 4.1, 15),
        (620, 13, 0.060, 5.0, 14),
        (650, 15, 0.052, 0.6, 15),
        (680, 13, 0.064, 1.8, 14),
        (700, 12, 0.058, 2.9, 13),
    ]
    for yb, amp, freq, ph, wd in noodle_rows:
        cv.wavy(230, 794, yb, amp, freq, ph, wd, NOODLE_SHADE, 1.0, clip=broth)
        cv.wavy(230, 794, yb - 4, amp, freq, ph, wd - 3, NOODLE, 1.0, clip=broth)

    # Lifted noodle swirl on the left, catching the light.
    for k in range(5):
        cv.wavy(300, 480, 520 + k * 16, 22 - k * 2, 0.045, k * 0.9,
                13, NOODLE, 1.0, clip=broth)

    # Chashu slices (pork): two overlapping pink rounds with a swirl.
    for cx, cy, r in [(640, 560, 74), (716, 640, 66)]:
        cv.disc(cx, cy, r, CHASHU_EDGE)
        cv.disc(cx, cy, r - 7, CHASHU)
        cv.disc(cx, cy, r - 30, (244, 200, 178))
        cv.disc(cx, cy, 12, (226, 150, 128))
        cv.ellipse(cx - 18, cy - 20, 26, 12, (255, 224, 200), 0.7)

    # Halved soft egg, yolk glossy and runny-looking.
    cv.ellipse(392, 660, 62, 78, EGG_WHITE)
    cv.ellipse(392, 660, 62, 78, (232, 220, 196), 0.35)
    cv.disc(392, 668, 38, YOLK_DEEP)
    cv.disc(392, 664, 32, YOLK)
    cv.ellipse(380, 650, 14, 9, (255, 214, 130), 0.95)
    cv.disc(392, 668, 20, (250, 176, 52), 0.6)

    # Narutomaki fish cake: white round, pink spiral centre.
    cv.disc(560, 700, 40, PINK)
    cv.disc(560, 700, 34, NARUTO)
    cv.disc(560, 700, 20, PINK)
    cv.disc(560, 700, 12, NARUTO)
    cv.disc(560, 700, 5, PINK)

    # Spring-onion rings scattered over the broth.
    onion_spots = [(300, 560), (350, 730), (470, 742), (540, 540),
                   (700, 730), (760, 580), (430, 560), (620, 740)]
    for ox, oy in onion_spots:
        cv.disc(ox, oy, 13, GREEN_DARK)
        cv.disc(ox, oy, 10, GREEN)
        cv.disc(ox, oy, 5, (146, 214, 110))

    # Nori sheet standing at the back of the bowl.
    cv.thick_line(300, 640, 268, 430, 74, NORI, 1.0)
    cv.thick_line(300, 640, 268, 430, 60, (44, 84, 52), 1.0)
    cv.thick_line(286, 560, 276, 470, 8, (74, 120, 76), 0.8)

    # Chopsticks resting across the rim, upper right.
    cv.thick_line(700, 330, 950, 560, 22, CHOP, 1.0)
    cv.thick_line(676, 366, 928, 596, 22, CHOP, 1.0)
    cv.thick_line(700, 330, 950, 560, 22, (150, 96, 44), 0.35)
    cv.thick_line(918, 528, 950, 560, 22, CHOP_TIP, 1.0)
    cv.thick_line(896, 564, 928, 596, 22, CHOP_TIP, 1.0)

    # Glossy highlights on rim and broth.
    cv.ellipse(330, 470, 110, 26, CREAM, 0.55)
    cv.ellipse(690, 452, 80, 20, CREAM, 0.4)
    cv.ellipse(250, 700, 26, 90, (255, 220, 180), 0.28)

    # Steam: three soft rising wisps above the bowl.
    steam_cols = [(420, 0.0), (512, 1.4), (604, 2.6)]
    for sx, ph in steam_cols:
        for step in range(26):
            y = 400 - step * 11
            x = sx + 26 * math.sin(step * 0.32 + ph)
            cv.soft_disc(x, y, 34 - step * 0.5, WHITE, 0.16)
        cv.soft_disc(sx, 150, 46, WHITE, 0.10)

    # Gentle vignette to pull the eye to the bowl.
    for y in range(H):
        for x in range(0, W, 4):
            dx = (x - 512) / 512.0
            dy = (y - 512) / 512.0
            d2 = dx * dx + dy * dy
            if d2 > 0.85:
                a = min(0.35, (d2 - 0.85) * 0.5)
                cv.blend(x, y, 30, 8, 6, a)
                cv.blend(x + 1, y, 30, 8, 6, a)
                cv.blend(x + 2, y, 30, 8, 6, a)
                cv.blend(x + 3, y, 30, 8, 6, a)


# ---------------------------------------------------------------- PNG out
def write_png(cv, path):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)  # filter: none
        raw.extend(cv.pix[y * stride:(y + 1) * stride])
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    cv = Canvas(W, H)
    draw(cv)
    size = write_png(cv, OUT)
    print(f"wrote {OUT} {W}x{H} {size} bytes")


if __name__ == "__main__":
    main()
