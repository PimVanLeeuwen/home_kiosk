"""Headlines: the newest story of each news group, with its picture.

The Now panel's Headlines screen and the top of the hub's News page. One story
per group, so it is always a mix; the lead is the newest that has a picture
big enough to stand behind its title.

A headline's picture comes from its feed (media:content, an enclosure, an
<img> in the body) or else from the article page's og:image, looked up once.
It is fetched through the reader's guarded client (public addresses only),
then stored small as WebP: a lead of about 900 px wide and a 240 px square.
The browser and the panels only ever get these stored copies.
"""

from __future__ import annotations

import asyncio
import html
import io
import logging
import re
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urljoin

import httpx
from PIL import Image, ImageOps
from pydantic import BaseModel

from ..models import Envelope
from ..store import Store
from . import reader, stories
from . import store as news

log = logging.getLogger(__name__)

CACHE_KEY = "headlines"
LEAD_MIN_WIDTH = 600  # narrower originals only make a thumbnail
LEAD_WIDTH = 900
THUMB_SIZE = 240
WEBP_QUALITY = 78
MAX_PAGE_BYTES = 1024 * 1024  # og:image sits in the <head>
# Pillow's own guard against decompression bombs is a warning at 89 MP; a news
# picture is far smaller, so anything this big is refused outright.
MAX_PIXELS = 40_000_000

_META = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_ATTR = re.compile(r"""([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
# Feeds that only carry a small square, and where the same picture is larger.
# NU.nl's pages sit behind DPG's consent wall, so og:image cannot help there.
_BIGGER = [(re.compile(r"(//images\.nu\.nl/m/[^/]+)_sqr\d+/"), r"\1_wd1280/")]
_PAGE_IMAGE = ("og:image:secure_url", "og:image", "twitter:image", "twitter:image:src")


class HeadlineSource(BaseModel):
    """Another feed's article on the same event (a grouped story)."""
    id: str
    source: str
    url: str


class Headline(BaseModel):
    id: str  # the article id, as in /api/news/articles
    group_id: str
    group: str
    title: str
    source: str
    url: str
    published: datetime
    summary: str | None = None
    # Which stored pictures exist: "lead" has both sizes, "thumb" only the square.
    image: Literal["lead", "thumb"] | None = None
    # A grouped story (M26): Claude's sentence, and the other feeds' articles.
    story: str | None = None
    sources: list[HeadlineSource] = []


class Headlines(Envelope):
    items: list[Headline]  # the lead first
    grouped: bool = False  # top stories by event, not the newest of each group


def page_image(page: str, base: str) -> str | None:
    """The og:image (or Twitter card image) of an HTML page, made absolute."""
    found: dict[str, str] = {}
    for tag in _META.findall(page):
        attrs = {k.lower(): (a or b) for k, a, b in _ATTR.findall(tag)}
        name = (attrs.get("property") or attrs.get("name") or "").lower()
        if name in _PAGE_IMAGE and attrs.get("content"):
            found.setdefault(name, html.unescape(attrs["content"]).strip())
    for name in _PAGE_IMAGE:
        if found.get(name):
            return urljoin(base, found[name])
    return None


def shrink(data: bytes) -> tuple[bytes | None, bytes]:
    """(lead or None, thumbnail) as WebP from an image's bytes; raises for
    anything Pillow cannot read or that is unreasonably large."""
    with Image.open(io.BytesIO(data)) as raw:
        if raw.width * raw.height > MAX_PIXELS:
            raise ValueError("image too large")
        picture = ImageOps.exif_transpose(raw).convert("RGB")
    lead = None
    if picture.width >= LEAD_MIN_WIDTH:
        height = round(picture.height * LEAD_WIDTH / picture.width)
        out = io.BytesIO()
        picture.resize((LEAD_WIDTH, height), Image.Resampling.LANCZOS).save(
            out, "WEBP", quality=WEBP_QUALITY)
        lead = out.getvalue()
    out = io.BytesIO()
    ImageOps.fit(picture, (THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS).save(
        out, "WEBP", quality=WEBP_QUALITY)
    return lead, out.getvalue()


async def _page_image(url: str, transport: httpx.AsyncBaseTransport | None) -> str | None:
    async with reader.client(transport) as http:
        async with http.stream("GET", url) as resp:
            resp.raise_for_status()
            raw = b""
            async for chunk in resp.aiter_bytes():
                raw += chunk
                if len(raw) >= MAX_PAGE_BYTES:
                    break  # the <head> is long past
            return page_image(raw.decode(resp.encoding or "utf-8", "replace"), str(resp.url))


def bigger(url: str) -> str:
    for pattern, larger in _BIGGER:
        url = pattern.sub(larger, url)
    return url


async def _shrunk(url: str, base: str, transport: httpx.AsyncBaseTransport | None
                  ) -> tuple[bytes | None, bytes]:
    data, _ = await reader.image(urljoin(base, url), transport)
    return await asyncio.to_thread(shrink, data)


async def _picture(row: Any, transport: httpx.AsyncBaseTransport | None
                   ) -> tuple[bytes | None, bytes]:
    """The feed's picture; the page's og:image when the feed has none, or only
    one too small for a lead (NU.nl's feed carries thumbnails)."""
    found = await _shrunk(bigger(row["image"]), row["url"], transport) if row["image"] else None
    if found is None or found[0] is None:
        try:
            page = await _page_image(row["url"], transport)
            if page and page != row["image"]:
                return await _shrunk(page, row["url"], transport)
        except Exception:
            if found is None:
                raise
    if found is None:
        raise LookupError("no picture")
    return found


def _stored(store: Store, article_id: str) -> Any:
    with store.connect() as conn:
        return conn.execute(
            "SELECT article_id, lead IS NOT NULL AS has_lead, thumb IS NOT NULL AS has_thumb "
            "FROM headline_image WHERE article_id = ?", (article_id,)).fetchone()


async def _ensure_picture(store: Store, row: Any, now: datetime,
                          transport: httpx.AsyncBaseTransport | None) -> Any:
    """The stored picture's row, fetching it the first time only."""
    known = _stored(store, row["id"])
    if known is not None:
        return known
    lead = thumb = error = None
    try:
        lead, thumb = await _picture(row, transport)
    except Exception as exc:
        # The class only: an address in the message could be long or odd.
        error = type(exc).__name__
        log.info("no headline picture for %s: %s", row["source"], error)
    with store.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO headline_image (article_id, checked_at, lead, thumb, error) "
            "VALUES (?, ?, ?, ?, ?)", (row["id"], now.isoformat(), lead, thumb, error))
    return _stored(store, row["id"])


def picture(store: Store, article_id: str, size: Literal["lead", "thumb"]) -> bytes | None:
    with store.connect() as conn:
        row = conn.execute(f"SELECT {size} FROM headline_image WHERE article_id = ?",
                           (article_id,)).fetchone()
    return row[0] if row else None


TOP_STORIES = 6


def _article_rows(store: Store, ids: list[str]) -> dict[str, Any]:
    marks = ",".join("?" * len(ids))
    with store.connect() as conn:
        rows = conn.execute(f"SELECT * FROM article WHERE id IN ({marks})", ids).fetchall()
    return {r["id"]: r for r in rows}


async def _grouped(store: Store, kept: list[dict[str, Any]], now: datetime,
                   transport: httpx.AsyncBaseTransport | None) -> list[Headline]:
    """The top stories: most feeds first, then the newest; each led by its newest
    article with a lead picture (else its newest), the others as its sources."""
    rows = _article_rows(store, [i for s in kept for i in s["ids"]])
    names = {g.id: g.title for g in news.groups(store)}
    ranked = []
    for story in kept:
        found = sorted((rows[i] for i in story["ids"] if i in rows),
                       key=lambda r: r["published"], reverse=True)
        if found:
            ranked.append((len({r["source"] for r in found}), found[0]["published"], found,
                           story["summary"]))
    ranked.sort(key=lambda s: (s[0], s[1]), reverse=True)
    picked = []
    for _, _, found, summary in ranked[:TOP_STORIES]:
        images = {r["id"]: await _ensure_picture(store, r, now, transport) for r in found}
        lead = next((r for r in found if images[r["id"]]["has_lead"]), found[0])
        stored = images[lead["id"]]
        others, seen = [], {lead["source"]}
        for r in found:
            if r["source"] not in seen:
                seen.add(r["source"])
                others.append(HeadlineSource(id=r["id"], source=r["source"], url=r["url"]))
        picked.append(Headline(
            id=lead["id"], group_id=lead["group_id"], group=names.get(lead["group_id"], ""),
            title=lead["title"], source=lead["source"], url=lead["url"],
            published=lead["published"], summary=lead["summary"],
            image="lead" if stored["has_lead"] else "thumb" if stored["has_thumb"] else None,
            story=summary, sources=others))
    return picked


async def collect(store: Store, transport: httpx.AsyncBaseTransport | None = None,
                  now: datetime | None = None, cfg: dict[str, Any] | None = None) -> Headlines:
    now = now or datetime.now(UTC)
    kept = stories.fresh(cfg or {}, store, now)
    if kept:
        top = await _grouped(store, kept, now, transport)
        if top:
            return Headlines(as_of=now, stale=False, items=top, grouped=True)
    picked: list[Headline] = []
    for group in news.groups(store):
        with store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM article WHERE group_id = ? ORDER BY published DESC, id LIMIT 1",
                (group.id,)).fetchone()
        if row is None:
            continue
        stored = await _ensure_picture(store, row, now, transport)
        image = "lead" if stored["has_lead"] else "thumb" if stored["has_thumb"] else None
        picked.append(Headline(
            id=row["id"], group_id=group.id, group=group.title, title=row["title"],
            source=row["source"], url=row["url"], published=row["published"],
            summary=row["summary"], image=image))
    picked.sort(key=lambda h: h.published, reverse=True)
    # The newest with a lead-sized picture goes first; the rest stay newest first.
    lead = next((h for h in picked if h.image == "lead"), None)
    if lead is not None:
        picked.remove(lead)
        picked.insert(0, lead)
    return Headlines(as_of=now, stale=False, items=picked)
