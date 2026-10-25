"""Painting tools for the panels' backgrounds (plan.md M27), with Pillow alone.

Everything here is seeded, so the same inputs give the same picture: a background
is painted again only when what it shows changes, and must not jump in between.
Shapes are drawn at twice the size and scaled down, for soft edges.
"""

from __future__ import annotations

import io
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

SIZE = 720
SS = 2  # supersampling for shapes
Colour = tuple[int, int, int]


def hex_colour(value: str) -> Colour:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def mix(a: Colour, b: Colour, t: float) -> Colour:
    t = max(0.0, min(1.0, t))
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))  # type: ignore[return-value]


def vertical(height: int, stops: list[tuple[float, Colour]], width: int = SIZE) -> Image.Image:
    """A top-to-bottom gradient through `stops` (position 0 to 1, colour)."""
    column = Image.new("RGB", (1, height))
    pixels = column.load()
    for y in range(height):
        t = y / max(1, height - 1)
        for (p0, c0), (p1, c1) in zip(stops, stops[1:], strict=False):
            if p0 <= t <= p1:
                pixels[0, y] = mix(c0, c1, (t - p0) / max(1e-6, p1 - p0))
                break
        else:
            pixels[0, y] = stops[-1][1] if t > stops[-1][0] else stops[0][1]
    return column.resize((width, height), Image.Resampling.BILINEAR)


def noise(width: int, height: int, seed: int, scale: int, stretch: float = 1.0) -> Image.Image:
    """Smooth value noise ('L', 0 to 255): a small seeded grid scaled up. `scale` is the
    size of one blob in pixels; `stretch` makes blobs wider than tall."""
    rng = random.Random(seed)
    gw = max(2, math.ceil(width / (scale * stretch)) + 3)
    gh = max(2, math.ceil(height / scale) + 3)
    grid = Image.frombytes("L", (gw, gh), bytes(rng.randrange(256) for _ in range(gw * gh)))
    big = grid.resize((round(gw * scale * stretch), gh * scale), Image.Resampling.BICUBIC)
    return big.crop((0, 0, width, height))


def fbm(width: int, height: int, seed: int, scale: int, octaves: int = 4,
        stretch: float = 1.0) -> Image.Image:
    """Layered noise: each octave half the size and half the weight of the one before."""
    out = noise(width, height, seed, scale, stretch)
    weight = 1.0
    for o in range(1, octaves):
        weight /= 2
        layer = noise(width, height, seed + o * 7919, max(2, scale >> o), stretch)
        out = Image.blend(out, layer, weight / (1 + weight))
    return out


def levels(mask: Image.Image, low: int, high: int, gain: float = 1.0) -> Image.Image:
    """Stretches `low..high` to 0..255 (times `gain`), with a smooth step."""
    span = max(1, high - low)

    def curve(v: int) -> int:
        t = max(0.0, min(1.0, (v - low) / span))
        return round(255 * min(1.0, gain * t * t * (3 - 2 * t)))

    return mask.point(curve)


def radial(radius: int, inner: float = 0.0, power: float = 2.0) -> Image.Image:
    """An 'L' disc of `radius`: 255 in the middle (up to `inner` of the radius), fading to
    0 at the edge."""
    size = 2 * radius
    grad = Image.radial_gradient("L").resize((size, size), Image.Resampling.BILINEAR)

    def fall(v: int) -> int:  # radial_gradient: 0 in the middle, 181 halfway along an edge
        d = v / 181
        if d >= 1:
            return 0
        t = max(0.0, (d - inner) / max(1e-6, 1 - inner))
        return round(255 * (1 - t) ** power)

    return grad.point(fall)


def glow(base: Image.Image, x: float, y: float, radius: int, colour: Colour,
         strength: float, power: float = 2.0) -> None:
    """Light added around (x, y), fading out over `radius`."""
    mask = radial(radius, 0.0, power).point(lambda v: round(v * strength))
    light = Image.new("RGB", mask.size, colour)
    box = (round(x) - radius, round(y) - radius)
    region = base.crop((box[0], box[1], box[0] + mask.size[0], box[1] + mask.size[1]))
    lit = ImageChops.add(region, ImageChops.multiply(light, Image.merge("RGB", [mask] * 3)))
    base.paste(lit, box)


def shapes() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """A transparent layer at twice the size, for shapes with soft edges (see `lay`)."""
    layer = Image.new("RGBA", (SIZE * SS, SIZE * SS), (0, 0, 0, 0))
    return layer, ImageDraw.Draw(layer)


def disc(draw: ImageDraw.ImageDraw, x: float, y: float, r: float, fill: tuple[int, ...]) -> None:
    """A disc on a `shapes` layer, in the picture's own coordinates."""
    draw.ellipse(((x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS), fill=fill)


def lay(base: Image.Image, layer: Image.Image) -> Image.Image:
    """The `shapes` layer over `base` (which may be smaller than the panel: cropped)."""
    w, h = base.size
    small = layer.crop((0, 0, w * SS, h * SS)).resize(base.size, Image.Resampling.LANCZOS)
    return Image.alpha_composite(base.convert("RGBA"), small).convert("RGB")


def tint(base: Image.Image, mask: Image.Image, colour: Colour | Image.Image,
         opacity: float = 1.0) -> Image.Image:
    """`colour` (a colour or a picture) laid over `base` where `mask` is bright."""
    top = colour if isinstance(colour, Image.Image) else Image.new("RGB", base.size, colour)
    if opacity < 1:
        mask = mask.point(lambda v: round(v * opacity))
    return Image.composite(top, base, mask)


def grain(base: Image.Image, seed: int, amount: int = 4) -> Image.Image:
    """A fine seeded grain: it hides the steps in a smooth gradient on the panel."""
    rng = random.Random(seed)
    n = Image.frombytes("L", base.size, rng.randbytes(base.size[0] * base.size[1]))
    n = n.point(lambda v: 128 + round((v - 128) * amount / 128))
    return ImageChops.add(base, Image.merge("RGB", [n] * 3), 1, -128)


def soften(image: Image.Image, radius: float) -> Image.Image:
    return image.filter(ImageFilter.GaussianBlur(radius))


def jpeg(image: Image.Image, quality: int = 84) -> bytes:
    """Baseline with 4:2:0 subsampling: what the ESP32-P4's JPEG decoder takes."""
    out = io.BytesIO()
    image.convert("RGB").save(out, "JPEG", quality=quality, progressive=False, subsampling="4:2:0")
    return out.getvalue()
