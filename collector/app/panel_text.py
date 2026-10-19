"""Text for the desk panels: their bitmap fonts hold Latin-1 only
(panels/firmware/fonts). Dashes and curly quotes become plain ones; anything
else outside Latin-1 (an emoji in a calendar's name) is left out."""

from __future__ import annotations

PLAIN = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
                       "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u00a0": " "})


def latin1(text: str) -> str:
    kept = text.translate(PLAIN).encode("latin-1", "ignore").decode("latin-1")
    return " ".join(kept.split())
