"""A minimal Telegram Bot API client.

The token is part of every request URL, so URLs are never logged (httpx's own
request logging is turned down in main.py) and errors are reduced to a short
reason without the request.
"""

from __future__ import annotations

from typing import Any

import httpx

API = "https://api.telegram.org"
TIMEOUT_SECONDS = 15
# Telegram rejects messages longer than this.
MAX_LENGTH = 4096


class TelegramError(Exception):
    """A failure with a message fit for the Alerts log."""


def describe(exc: Exception) -> str:
    if isinstance(exc, TelegramError):
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            detail = exc.response.json().get("description") or ""
        except ValueError:
            detail = ""
        suffix = f": {detail}" if detail else ""
        return f"Telegram answered {exc.response.status_code}{suffix}"[:200]
    if isinstance(exc, httpx.TimeoutException):
        return "Telegram timed out"
    if isinstance(exc, httpx.TransportError):
        return "Telegram not reachable"
    return "Unexpected answer from Telegram"


class Telegram:
    def __init__(self, token: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if not token:
            raise TelegramError("No bot token set (TELEGRAM_BOT_TOKEN)")
        self._base = f"{API}/bot{token}"
        self._transport = transport

    async def call(
        self, method: str, payload: dict[str, Any], timeout: float = TIMEOUT_SECONDS
    ) -> Any:
        async with httpx.AsyncClient(transport=self._transport, timeout=timeout) as client:
            resp = await client.post(f"{self._base}/{method}", json=payload)
            resp.raise_for_status()
            body = resp.json()
        if not body.get("ok"):
            reason = body.get("description", "unknown reason")
            raise TelegramError(f"Telegram refused: {reason}"[:200])
        return body.get("result")

    async def send(self, chat_id: str | int, html: str, silent: bool = False) -> None:
        if len(html) > MAX_LENGTH:
            html = html[: MAX_LENGTH - 1] + "…"
        await self.call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": html,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "disable_notification": silent,
            },
        )
