"""The Saved page: Readeck bookmarks, read in the hub's reader.

Contract checked against the Readeck 0.23.4 API docs:

    GET   /api/bookmarks?is_archived=false&limit=&offset=&sort=-created
          -> list of bookmarks, header Total-Count       (bookmarks:read)
    GET   /api/bookmarks/{id}            -> details with resources.thumbnail
    GET   /api/bookmarks/{id}/article    -> text/html fragment of the article
    PATCH /api/bookmarks/{id}  {"is_archived"|"read_progress"|"is_deleted"}
                                                         (bookmarks:write)

Delete sets is_deleted, like Readeck's own Delete button: Readeck removes the
bookmark a little later and can still undo it until then.

Readeck lives on the LAN, so its requests skip the reader's public-address
guard; images are only fetched from Readeck's own origin.
"""

from __future__ import annotations

import logging
import re
from collections import OrderedDict
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from pydantic import BaseModel

from . import html_blocks
from .reader import MAX_IMAGE_BYTES, ArticleContent, read_capped

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15
BOOKMARK_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
# Image URLs of recently opened bookmarks, for the image proxy.
_images: OrderedDict[str, list[str]] = OrderedDict()
IMAGE_MEMORY = 50


class ReadeckError(Exception):
    """A sentence for the screen, and the HTTP status the hub answers with."""

    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


class Bookmark(BaseModel):
    id: str
    url: str
    title: str
    site: str | None = None
    created: str | None = None
    published: str | None = None
    description: str | None = None
    reading_minutes: int | None = None
    progress: int = 0
    archived: bool = False
    # False while Readeck is still fetching the page, or when it failed.
    readable: bool = False
    thumbnail: bool = False


def _settings(cfg: dict[str, Any]) -> tuple[str, str]:
    readeck = cfg.get("readeck") or {}
    base = (readeck.get("base_url") or "").rstrip("/")
    token = readeck.get("api_token") or ""
    if not base:
        raise ReadeckError("Readeck is not configured", 503)
    if not token:
        raise ReadeckError("The Readeck token is missing", 503)
    return base, token


def check_id(bookmark_id: str) -> str:
    if not BOOKMARK_ID.match(bookmark_id):
        raise ReadeckError("No such bookmark", 404)
    return bookmark_id


async def _call(cfg: dict[str, Any], method: str, path: str,
                transport: httpx.AsyncBaseTransport | None = None, **kwargs: Any
                ) -> httpx.Response:
    base, token = _settings(cfg)
    try:
        async with httpx.AsyncClient(transport=transport, timeout=TIMEOUT_SECONDS) as client:
            resp = await client.request(method, f"{base}/api{path}",
                                        headers={"Authorization": f"Bearer {token}"}, **kwargs)
    except httpx.RequestError as exc:
        log.warning("readeck unreachable: %s", type(exc).__name__)
        raise ReadeckError("Readeck is not reachable") from exc
    if resp.status_code in (401, 403):
        raise ReadeckError("Readeck rejected the token (it needs bookmarks:read and write)")
    if resp.status_code == 404:
        raise ReadeckError("No such bookmark", 404)
    if resp.status_code >= 400:
        log.warning("readeck returned %s", resp.status_code)
        raise ReadeckError(f"Readeck error {resp.status_code}")
    return resp


def _bookmark(raw: dict[str, Any]) -> Bookmark:
    resources = raw.get("resources") or {}
    return Bookmark(
        id=raw["id"], url=raw.get("url") or "", title=raw.get("title") or raw.get("url") or "",
        site=raw.get("site_name") or raw.get("site"), created=raw.get("created"),
        published=raw.get("published"), description=raw.get("description") or None,
        reading_minutes=raw.get("reading_time") or None,
        progress=raw.get("read_progress") or 0, archived=bool(raw.get("is_archived")),
        readable=bool(raw.get("loaded")) and raw.get("state") == 0
        and bool(raw.get("has_article")),
        thumbnail="thumbnail" in resources,
    )


async def bookmarks(cfg: dict[str, Any], *, archived: bool = False, limit: int = 30,
                    offset: int = 0, transport: httpx.AsyncBaseTransport | None = None
                    ) -> tuple[list[Bookmark], int]:
    """Newest first. Bookmarks scheduled for deletion are left out."""
    resp = await _call(cfg, "GET", "/bookmarks", transport, params={
        "is_archived": str(archived).lower(), "limit": limit, "offset": offset,
        "sort": "-created"})
    items = [_bookmark(b) for b in resp.json() if not b.get("is_deleted")]
    total = int(resp.headers.get("Total-Count") or len(items))
    return items, total


def _remember_images(bookmark_id: str, images: list[str]) -> None:
    _images[bookmark_id] = images
    _images.move_to_end(bookmark_id)
    while len(_images) > IMAGE_MEMORY:
        _images.popitem(last=False)


async def article(cfg: dict[str, Any], bookmark_id: str,
                  transport: httpx.AsyncBaseTransport | None = None) -> ArticleContent:
    info = _bookmark((await _call(cfg, "GET", f"/bookmarks/{bookmark_id}", transport)).json())
    if not info.readable:
        return ArticleContent(ok=False, reason="Readeck has no readable text for this page",
                              title=info.title, site=info.site)
    html = (await _call(cfg, "GET", f"/bookmarks/{bookmark_id}/article", transport)).text
    blocks, images = html_blocks.to_blocks(html)
    base, _ = _settings(cfg)
    images = [urljoin(base + "/", src) for src in images]
    for block in blocks:
        if block.type == "image":
            block.src = f"/api/saved/{bookmark_id}/images/{block.src}"
    _remember_images(bookmark_id, images)
    return ArticleContent(ok=True, title=info.title, site=info.site, date=info.published,
                          blocks=blocks, images=images)


async def update(cfg: dict[str, Any], bookmark_id: str, fields: dict[str, Any],
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
    await _call(cfg, "PATCH", f"/bookmarks/{bookmark_id}", transport, json=fields)


async def _resource(cfg: dict[str, Any], url: str,
                    transport: httpx.AsyncBaseTransport | None) -> tuple[bytes, str]:
    base, token = _settings(cfg)
    if urlsplit(url)[:2] != urlsplit(base)[:2]:
        # Only Readeck's own stored copies: never an open proxy.
        raise ReadeckError("No such image", 404)
    async with httpx.AsyncClient(transport=transport, timeout=TIMEOUT_SECONDS) as client:
        async with client.stream("GET", url, headers={"Authorization": f"Bearer {token}"}) as resp:
            resp.raise_for_status()
            kind = resp.headers.get("content-type", "").split(";")[0].strip().lower()
            if not kind.startswith("image/") or kind == "image/svg+xml":
                raise ValueError("not an image")
            return await read_capped(resp, MAX_IMAGE_BYTES), kind


async def image(cfg: dict[str, Any], bookmark_id: str, index: int,
                transport: httpx.AsyncBaseTransport | None = None) -> tuple[bytes, str]:
    images = _images.get(bookmark_id)
    if images is None:
        images = (await article(cfg, bookmark_id, transport)).images
    if not 0 <= index < len(images):
        raise ReadeckError("No such image", 404)
    return await _resource(cfg, images[index], transport)


async def thumbnail(cfg: dict[str, Any], bookmark_id: str,
                    transport: httpx.AsyncBaseTransport | None = None) -> tuple[bytes, str]:
    raw = (await _call(cfg, "GET", f"/bookmarks/{bookmark_id}", transport)).json()
    src = ((raw.get("resources") or {}).get("thumbnail") or {}).get("src")
    if not src:
        raise ReadeckError("No thumbnail", 404)
    return await _resource(cfg, urljoin(_settings(cfg)[0] + "/", src), transport)
