"""The in-app reader: fetch an article, extract its text with trafilatura,
and turn it into plain blocks the web app renders as text.

No HTML from a news site ever reaches the browser: only headings,
paragraphs, quotes, lists and images, as data. Images are proxied by the hub
(the browser never contacts the news site) and only those found in the
extracted article can be fetched, by position.

Every fetch, including each redirect, must go to a public internet address,
so a feed link or image cannot make the hub reach into the LAN.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import socket
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

import httpx
import trafilatura
from pydantic import BaseModel

from ..store import Store

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; home-hub/1.0; reader)"
TIMEOUT_SECONDS = 20
MAX_PAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MIN_TEXT_CHARS = 200
# Where sites like NU.nl (DPG Media) send visitors without a consent cookie.
CONSENT_WALL = re.compile(r"(consent|privacy-gate|cookiewall)", re.IGNORECASE)

class Block(BaseModel):
    type: Literal["heading", "paragraph", "quote", "list", "image"]
    text: str = ""
    items: list[str] = []
    # For images: the hub's own proxy URL, and the alt text in `text`.
    src: str = ""


class ArticleContent(BaseModel):
    ok: bool
    reason: str | None = None  # why there is nothing to read, when not ok
    title: str | None = None
    author: str | None = None
    date: str | None = None
    site: str | None = None
    blocks: list[Block] = []
    # Original image URLs by position; never sent to the browser.
    images: list[str] = []


class Blocked(Exception):
    """The address is not on the public internet."""


# --- safe fetching ----------------------------------------------------------------------


async def check_public(url: str) -> None:
    """Refuse anything but http(s) to hosts that resolve only to public addresses."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise Blocked("not an http(s) address")
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo, parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise httpx.ConnectError(f"cannot resolve {parts.hostname}") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise Blocked(f"{parts.hostname} is a private address")


async def _guard(request: httpx.Request) -> None:
    await check_public(str(request.url))


def client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    """An HTTP client that checks every request, redirects included."""
    return httpx.AsyncClient(
        transport=transport, timeout=TIMEOUT_SECONDS, follow_redirects=True, max_redirects=5,
        headers={"User-Agent": USER_AGENT}, event_hooks={"request": [_guard]},
    )


async def read_capped(resp: httpx.Response, limit: int) -> bytes:
    chunks, size = [], 0
    async for chunk in resp.aiter_bytes():
        size += len(chunk)
        if size > limit:
            raise ValueError("too large")
        chunks.append(chunk)
    return b"".join(chunks)


def reason(exc: Exception) -> str:
    if isinstance(exc, Blocked):
        return "Blocked: the link points to a private address"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"The site answered {exc.response.status_code}"
    if isinstance(exc, httpx.TimeoutException):
        return "The site timed out"
    if isinstance(exc, httpx.TransportError):
        return "The site is not reachable"
    if isinstance(exc, ValueError) and str(exc) == "too large":
        return "The page is too large"
    return "The page could not be read"


# --- extraction ---------------------------------------------------------------------------


def alt_text(alt: str | None) -> str:
    """Alt text, unless it is a file name ("53420776536_b9dede69df_k")."""
    alt = " ".join((alt or "").split())
    return "" if re.fullmatch(r"[\w.-]{12,}", alt) and not alt.isalpha() else alt


def tidy(blocks: list[Block], title: str | None) -> list[Block]:
    """Drop the page's own copies of the title (the reader shows it already)
    and blocks that repeat the one before, which teaser markup often causes."""
    kept: list[Block] = []
    for block in blocks:
        if block.type == "heading" and title and block.text.split() == title.split():
            continue
        if kept and block.type != "image" and block == kept[-1]:
            continue
        kept.append(block)
    return kept


def to_blocks(xml: str, article_id: str) -> ArticleContent:
    """trafilatura's XML (with metadata) to plain blocks. Text only: every
    element is flattened with itertext, so no markup survives."""
    root = ET.fromstring(xml)
    blocks: list[Block] = []
    images: list[str] = []

    def text(el: ET.Element) -> str:
        return " ".join("".join(el.itertext()).split())

    main = root.find("main")
    for el in (main if main is not None else root):
        if el.tag == "head" and text(el):
            blocks.append(Block(type="heading", text=text(el)))
        elif el.tag == "p" and text(el):
            blocks.append(Block(type="paragraph", text=text(el)))
        elif el.tag == "quote" and text(el):
            blocks.append(Block(type="quote", text=text(el)))
        elif el.tag == "list":
            items = [text(i) for i in el.findall("item") if text(i)]
            if items:
                blocks.append(Block(type="list", items=items))
        elif (
            el.tag == "graphic"
            and el.get("src", "").startswith(("http://", "https://"))
            and el.get("src") not in images
            # A byline headshot, not part of the story.
            and not (el.get("alt") and el.get("alt") == root.get("author"))
        ):
            images.append(el.get("src", ""))
            blocks.append(Block(type="image", text=alt_text(el.get("alt")),
                                src=f"/api/news/articles/{article_id}/images/{len(images) - 1}"))

    blocks = tidy(blocks, root.get("title"))
    title = root.get("title")
    # A paywall or cookie wall leaves a sentence or two: not worth reading here.
    if sum(len(b.text) for b in blocks if b.type == "paragraph") < MIN_TEXT_CHARS:
        return ArticleContent(ok=False, reason="No readable text (paywall or app-only page)")
    return ArticleContent(
        ok=True, title=title, author=root.get("author"), date=root.get("date"),
        site=root.get("sitename"), blocks=blocks, images=images,
    )


async def extract(url: str, article_id: str,
                  transport: httpx.AsyncBaseTransport | None = None) -> ArticleContent:
    try:
        async with client(transport) as http:
            async with http.stream("GET", url) as resp:
                resp.raise_for_status()
                raw = await read_capped(resp, MAX_PAGE_BYTES)
                encoding = resp.encoding or "utf-8"
                final = str(resp.url)
    except Exception as exc:
        log.warning("reader fetch failed: %s", type(exc).__name__)
        return ArticleContent(ok=False, reason=reason(exc))

    if CONSENT_WALL.search(final):
        return ArticleContent(ok=False, reason="The site asks for cookie consent first")
    page = raw.decode(encoding, errors="replace")
    xml = await asyncio.to_thread(
        trafilatura.extract, page, url=url, output_format="xml", include_images=True,
        include_links=False, include_tables=False, include_comments=False, with_metadata=True,
    )
    if not xml:
        return ArticleContent(ok=False, reason="No readable text (paywall or app-only page)")
    return to_blocks(xml, article_id)


# --- cache ------------------------------------------------------------------------------------


def cached(store: Store, article_id: str) -> ArticleContent | None:
    with store.connect() as conn:
        row = conn.execute("SELECT content FROM article_content WHERE id = ?",
                           (article_id,)).fetchone()
    return ArticleContent.model_validate(json.loads(row["content"])) if row else None


def remember(store: Store, article_id: str, content: ArticleContent) -> None:
    # Failures are not kept: the next open tries again.
    if not content.ok:
        return
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO article_content (id, fetched_at, content) VALUES (?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET fetched_at = excluded.fetched_at, "
            "content = excluded.content",
            (article_id, datetime.now(UTC).isoformat(), content.model_dump_json()))


async def image(url: str, transport: httpx.AsyncBaseTransport | None = None
                ) -> tuple[bytes, str]:
    """An image's bytes and type; raises for anything that is not a small image."""
    async with client(transport) as http:
        async with http.stream("GET", url) as resp:
            resp.raise_for_status()
            kind = resp.headers.get("content-type", "").split(";")[0].strip().lower()
            if not kind.startswith("image/") or kind == "image/svg+xml":
                # SVG can carry script; the reader only shows raster images.
                raise ValueError("not an image")
            return await read_capped(resp, MAX_IMAGE_BYTES), kind
