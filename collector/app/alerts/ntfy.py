"""A minimal ntfy publisher for the NAS's own ntfy (plan.md M31).

The hub publishes to one topic per alert category with a write-only token; the
iPhone's ntfy app reads them. The token is only in a header, never logged, and
errors are reduced to a short reason without the request.
"""

from __future__ import annotations

import html
import re
from typing import Any

import httpx

TIMEOUT_SECONDS = 15
# ntfy turns a longer message into a file attachment; stay under it.
MAX_BYTES = 4000
TOPIC_PREFIX = "hub-"

# ntfy priorities: 2 is quiet (no sound), 3 normal, 4 Time Sensitive on iOS.
QUIET, NORMAL, URGENT = 2, 3, 4

# One colour dot per severity in front of the title (the iOS app's emoji tags).
DOT = {"error": "red_circle", "warning": "orange_circle", "ok": "green_circle",
       "info": "white_circle"}

_TAG = re.compile(r"<[^>]+>")
_BLANKS = re.compile(r"\n{3,}")


class NtfyError(Exception):
    """A failure with a message fit for the Alerts log."""


def describe(exc: Exception) -> str:
    if isinstance(exc, NtfyError):
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            detail = exc.response.json().get("error") or ""
        except ValueError:
            detail = ""
        suffix = f": {detail}" if detail else ""
        return f"ntfy answered {exc.response.status_code}{suffix}"[:200]
    if isinstance(exc, httpx.TimeoutException):
        return "ntfy timed out"
    if isinstance(exc, httpx.TransportError):
        return "ntfy not reachable"
    return "Unexpected answer from ntfy"


def plain(text: str) -> str:
    """Telegram HTML as plain text: tags dropped (a link keeps its text, a table
    its lines), entities read, at most one blank line in a row."""
    return _BLANKS.sub("\n\n", html.unescape(_TAG.sub("", text))).strip()


def clip(text: str, limit: int = MAX_BYTES) -> str:
    """At most `limit` bytes of UTF-8, cut on a character and ended with "…"."""
    data = text.encode()
    if len(data) <= limit:
        return text
    return data[: limit - len("…".encode())].decode(errors="ignore").rstrip() + "…"


def topic(category: str) -> str:
    return f"{TOPIC_PREFIX}{category}"


class Ntfy:
    def __init__(self, url: str, token: str,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        if not (url or "").strip():
            raise NtfyError("No ntfy address set (ntfy.url)")
        if not (token or "").strip():
            raise NtfyError("No ntfy token set (NTFY_TOKEN)")
        self._url = url.strip().rstrip("/")
        self._token = token.strip()
        self._transport = transport

    async def publish(self, topic: str, title: str, message: str, priority: int = NORMAL,
                      tags: list[str] | None = None, click: str | None = None) -> dict[str, Any]:
        """Publishes one message as JSON (UTF-8 safe, unlike headers); returns ntfy's
        answer, with the message's `id`."""
        payload: dict[str, Any] = {"topic": topic, "title": title, "message": clip(message),
                                   "priority": priority}
        if tags:
            payload["tags"] = tags
        if click:
            payload["click"] = click
        async with httpx.AsyncClient(transport=self._transport,
                                     timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(self._url, json=payload,
                                     headers={"Authorization": f"Bearer {self._token}"})
            resp.raise_for_status()
            body = resp.json()
        if not isinstance(body, dict) or not body.get("id"):
            raise NtfyError("ntfy answered without a message id")
        return body
