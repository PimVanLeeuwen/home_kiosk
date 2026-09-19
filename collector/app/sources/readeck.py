"""Save-to-Readeck for tap-to-save on the news view.

The only write path in the project. Readeck does its own article extraction, so
this just forwards the URL with a bearer token.

Contract verified against Readeck 0.23.4:

    POST /api/bookmarks
    Authorization: Bearer <token>        token needs the bookmarks:write role
    {"url": "...", "title": "...", "labels": ["desk-dashboard"]}

    -> 202 Accepted, header Bookmark-Id, body {"status":202,...}
    -> 401 missing or invalid token
    -> 422 missing url

Note the 202: Readeck *queues* the link and fetches it afterwards. A success
here means accepted, not extracted — a paywalled page still returns 202 and
fails later, out of view of the screen.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

SAVE_TIMEOUT_SECONDS = 10
LABEL = "desk-dashboard"


class SaveError(Exception):
    """Readeck refused or could not be reached. Message is shown on screen."""


async def save(cfg: dict[str, Any], url: str, title: str | None = None) -> str | None:
    """Queue a URL in Readeck. Returns the bookmark id when Readeck reports one."""
    readeck = cfg.get("readeck") or {}
    base = (readeck.get("base_url") or "").rstrip("/")
    token = readeck.get("api_token") or ""

    if not base:
        raise SaveError("Readeck not configured")
    if not token:
        raise SaveError("Readeck token missing")

    payload: dict[str, Any] = {"url": url, "labels": [LABEL]}
    if title:
        payload["title"] = title

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base}/api/bookmarks",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=SAVE_TIMEOUT_SECONDS,
            )
    except httpx.RequestError as exc:
        log.warning("readeck unreachable: %s", exc)
        raise SaveError("Readeck unreachable") from exc

    if resp.status_code in (200, 201, 202):
        return resp.headers.get("Bookmark-Id")
    if resp.status_code == 401:
        raise SaveError("Readeck rejected the token")
    if resp.status_code == 422:
        raise SaveError("Readeck rejected the link")

    log.warning("readeck returned %s: %s", resp.status_code, resp.text[:200])
    raise SaveError(f"Readeck error {resp.status_code}")
