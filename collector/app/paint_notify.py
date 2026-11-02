"""Pictures for notifications (plan.md M31 step 4): the banner's thumbnail on the phone,
big on a long press, and full width on the message's page.

1200 x 800, dark, lit in the message's colour. iOS crops the banner's thumbnail to the
middle square, so the one figure that matters sits there; the sides carry the rest.
Percentages only, never amounts: a lock screen is seen by anyone nearby. Everything is
drawn at twice the size and scaled down, for soft edges.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from . import paint
from .paint import Colour, hex_colour

W, H = 1200, 800
S = 2  # supersampling

FONT = Path(__file__).with_name("instrument-sans.ttf")
INK, MUTED, FAINT, LINE = (236, 237, 239), (154, 158, 167), (126, 130, 139), (44, 46, 54)
VIOLET, GREEN, AMBER, RED = (hex_colour(c) for c in ("#8f80ff", "#3fb97f", "#e0a23b", "#e5646a"))
CANVAS = (12, 12, 16)
TONE = {"error": RED, "warning": AMBER, "ok": GREEN, "info": VIOLET}
MAX_BYTES = 400 * 1024


def _font(size: float, weight: int = 400) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT), round(size * S))
    font.set_variation_by_axes([100, weight])
    return font


@dataclass
class Canvas:
    image: Image.Image
    draw: ImageDraw.ImageDraw

    def text(self, xy: tuple[float, float], text: str, size: float, colour: Colour = INK,
             weight: int = 400, anchor: str = "la", spacing: float = 0.0) -> float:
        """Text at `xy` (picture coordinates); returns its width."""
        font = _font(size, weight)
        x, y = xy
        if spacing:  # letter-spaced small caps: one character at a time
            width = sum(font.getlength(ch) + spacing * S for ch in text) - spacing * S
            if anchor[0] == "m":
                x -= width / S / 2
            for ch in text:
                self.draw.text((x * S, y * S), ch, font=font, fill=colour, anchor="l" + anchor[1])
                x += (font.getlength(ch) + spacing * S) / S
            return width / S
        self.draw.text((x * S, y * S), text, font=font, fill=colour, anchor=anchor)
        return font.getlength(text) / S

    def width(self, text: str, size: float, weight: int = 400) -> float:
        return _font(size, weight).getlength(text) / S

    def line(self, points: list[tuple[float, float]], colour: Colour, width: float) -> None:
        self.draw.line([(x * S, y * S) for x, y in points], fill=colour, width=round(width * S),
                       joint="curve")

    def rect(self, box: tuple[float, float, float, float], colour: tuple[int, ...],
             radius: float = 0) -> None:
        self.draw.rounded_rectangle([v * S for v in box], radius=radius * S, fill=colour)

    def disc(self, x: float, y: float, r: float, colour: tuple[int, ...]) -> None:
        self.draw.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=colour)


def _canvas(tone: Colour, glow_at: tuple[float, float] = (W * 0.5, H * 0.38),
            strength: float = 0.22) -> Canvas:
    base = Image.new("RGB", (W * S, H * S), CANVAS)
    paint.glow(base, glow_at[0] * S, glow_at[1] * S, round(560 * S), tone, strength, power=2.2)
    paint.glow(base, (W - 40) * S, -60 * S, round(420 * S), VIOLET, 0.12, power=2.4)
    return Canvas(base, ImageDraw.Draw(base, "RGBA"))


def _finish(c: Canvas, seed: int) -> Image.Image:
    small = c.image.resize((W, H), Image.Resampling.LANCZOS)
    return paint.grain(small, seed, 3)


def jpeg(image: Image.Image) -> bytes:
    """A JPEG iOS shows in a notification, at most `MAX_BYTES`."""
    quality = 88
    while True:
        out = io.BytesIO()
        image.convert("RGB").save(out, "JPEG", quality=quality, optimize=True,
                                  progressive=False, subsampling="4:2:0")
        if out.tell() <= MAX_BYTES or quality <= 60:
            return out.getvalue()
        quality -= 8


def _pct(value: float, signed: bool = False, decimals: int = 0) -> str:
    text = f"{abs(value):.{decimals}f}%".replace(".", ",") if decimals else f"{abs(value):.0f}%"
    if not signed:
        return text
    return ("+" if value > 0 else "−" if value < 0 else "±") + text


# --- figure alerts -------------------------------------------------------------------


def disk(pool: str, used_pct: float, free: str, limit_pct: float,
         history: list[float]) -> Image.Image:
    """A pool filling up: the % and space left in the middle, its last 30 days (daily %)
    as a line across the whole width, against the limit."""
    tone = RED if used_pct >= 95 else AMBER
    c = _canvas(tone)
    c.text((W / 2, 150), pool.upper(), 22, MUTED, 600, "ma", spacing=4)
    c.text((W / 2, 300), _pct(used_pct), 150, INK, 600, "ms")
    c.text((W / 2, 352), f"{free} left", 34, MUTED, 400, "ms")
    points = history[-30:] or [used_pct]
    top, bottom = 420, 740
    low = min(min(points), limit_pct) - 3
    high = max(max(points), limit_pct, 100 if max(points) > 97 else 0) + 1
    span = max(1.0, high - low)

    def y(v: float) -> float:
        return bottom - (v - low) / span * (bottom - top)

    ly = y(limit_pct)
    for x in range(40, W - 40, 22):
        c.line([(x, ly), (x + 10, ly)], (*RED, 150), 2)
    c.text((44, ly - 12), f"limit {_pct(limit_pct)}", 20, (*RED, 220), 500, "ls")
    step = (W - 80) / max(1, len(points) - 1)
    line = [(40 + i * step, y(v)) for i, v in enumerate(points)] if len(points) > 1 else [
        (40, y(points[0])), (W - 40, y(points[0]))]
    # The area under the line, fading out towards the bottom.
    area = Image.new("L", c.image.size, 0)
    ImageDraw.Draw(area).polygon([(x * S, yy * S) for x, yy in line]
                                 + [(line[-1][0] * S, bottom * S), (line[0][0] * S, bottom * S)],
                                 fill=255)
    fade = paint.vertical(H * S, [(0.0, (90, 90, 90)), (top / H, (90, 90, 90)), (1.0, (0, 0, 0))],
                          W * S).convert("L")
    c.image.paste(paint.tint(c.image, ImageChops.multiply(area, fade), tone))
    c.line(line, tone, 5)
    c.disc(*line[-1], 9, tone)
    c.text((40, 774), "30 days", 20, FAINT, 400, "ls")
    c.text((W - 40, 774), "today", 20, FAINT, 400, "rs")
    return _finish(c, 31)


def gauge(label: str, used_pct: float, free: str, total: str, limit_pct: float) -> Image.Image:
    """A space without history (the storage box): an arc round the %, the limit marked."""
    tone = RED if used_pct >= 95 else AMBER if used_pct >= limit_pct else GREEN
    c = _canvas(tone, (W / 2, H / 2), 0.24)
    cx, cy, r = W / 2, 430, 250
    start, sweep = 135, 270
    box = ((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S)
    c.draw.arc(box, start, start + sweep, fill=LINE, width=34 * S)
    c.draw.arc(box, start, start + sweep * min(1, used_pct / 100), fill=tone, width=34 * S)
    angle = math.radians(start + sweep * limit_pct / 100)
    c.line([(cx + (r - 17) * math.cos(angle), cy + (r - 17) * math.sin(angle)),
            (cx + (r + 17) * math.cos(angle), cy + (r + 17) * math.sin(angle))], CANVAS, 6)
    c.text((cx, 120), label.upper(), 22, MUTED, 600, "ma", spacing=4)
    c.text((cx, 470), _pct(used_pct), 140, INK, 600, "ms")
    c.text((cx, 530), f"{free} left of {total}", 30, MUTED, 400, "ms")
    c.text((cx, 760), f"limit {_pct(limit_pct)}", 22, FAINT, 400, "ms")
    return _finish(c, 37)


def _bars(c: Canvas, rows: list[tuple[str, float]], top: float, x0: float, x1: float,
          row_h: float, scale: float, size: float = 26) -> None:
    """Diverging bars round a middle line: the name left, the % right of its bar."""
    mid = (x0 + x1) / 2
    half = (x1 - x0) / 2 - 150
    for i, (name, pct) in enumerate(rows):
        yy = top + i * row_h
        length = max(4.0, abs(pct) / scale * half)
        colour = GREEN if pct >= 0 else RED
        left, right = (mid, mid + length) if pct >= 0 else (mid - length, mid)
        box = (left, yy - 12, right, yy + 12)
        c.rect(box, (*colour, 230), 6)
        c.text((x0, yy), name, size, INK, 600, "lm")
        c.text((x1, yy), _pct(pct, signed=True, decimals=1), size, colour, 600, "rm")
    c.line([(mid, top - row_h / 2), (mid, top + (len(rows) - 0.5) * row_h)], LINE, 2)


def move(total_pct: float, movers: list[tuple[str, float]], when: str) -> Image.Image:
    """The portfolio's move of the day, with the holdings that moved it most."""
    tone = GREEN if total_pct >= 0 else RED
    c = _canvas(tone, (W / 2, 220))
    c.text((W / 2, 110), f"PORTFOLIO · {when.upper()}", 22, MUTED, 600, "ma", spacing=4)
    c.text((W / 2, 290), _pct(total_pct, signed=True, decimals=1), 140, tone, 600, "ms")
    rows = sorted(movers, key=lambda m: -abs(m[1]))[:4]
    scale = max([abs(p) for _, p in rows] + [1.0])
    _bars(c, rows, 420, 220, W - 220, 92, scale, 30)
    return _finish(c, 41)


# --- reports ---------------------------------------------------------------------------


def report(title: str, when: str, total_pct: float, holdings: list[tuple[str, float]],
           indices: list[tuple[str, float]]) -> Image.Image:
    """The Portfolio report: the day in %, every holding as a bar, the indices below."""
    tone = GREEN if total_pct >= 0 else RED
    c = _canvas(tone, (W / 2, 160), 0.18)
    c.text((W / 2, 70), f"{title.upper()} · {when.upper()}", 20, MUTED, 600, "ma", spacing=4)
    c.text((W / 2, 200), _pct(total_pct, signed=True, decimals=2), 104, tone, 600, "ms")
    rows = sorted(holdings, key=lambda h: -h[1])[:8]
    scale = max([abs(p) for _, p in rows] + [1.0])
    row_h = min(56.0, 420 / max(1, len(rows)))
    _bars(c, rows, 280, 200, W - 200, row_h, scale, 24)
    if indices:
        line = "   ·   ".join(f"{name} {_pct(p, signed=True, decimals=1)}"
                               for name, p in indices[:4])
        c.text((W / 2, 768), line, 22, MUTED, 400, "ms")
    return _finish(c, 43)


@dataclass(frozen=True)
class Tile:
    label: str
    value: str
    tone: str | None = None  # "ok", "warning", "error" colours the value


def briefing(day: str, headline: str, detail: str, tiles: list[Tile],
             tone: str = "info") -> Image.Image:
    """The morning briefing as a card: the day, the one line that matters (the train),
    its detail, and up to three tiles (portfolio, the day, the house)."""
    colour = TONE.get(tone, VIOLET)
    c = _canvas(colour, (W * 0.3, 0), 0.26)
    c.text((W / 2, 130), day.upper(), 22, (*VIOLET, 255) if tone == "info" else colour, 600, "ma",
           spacing=4)
    size = 96 if c.width(headline, 96, 600) < W - 160 else 72
    c.text((W / 2, 290), headline, size, INK, 600, "ms")
    c.text((W / 2, 350), detail, 32, MUTED, 400, "ms")
    # The tiles fit the middle square that iOS keeps for the thumbnail.
    shown = tiles[:3]
    gap, tw = 20, 246
    total = len(shown) * tw + (len(shown) - 1) * gap
    x = (W - total) / 2
    for tile in shown:
        c.rect((x, 470, x + tw, 650), (27, 28, 33, 235), 22)
        c.text((x + 24, 528), tile.label, 24, MUTED, 400, "ls")
        value = 40 if c.width(tile.value, 40, 600) < tw - 44 else 32
        c.text((x + 24, 606), tile.value, value,
               TONE.get(tile.tone or "", INK) if tile.tone else INK, 600, "ls")
        x += tw + gap
    return _finish(c, 47)
