"""Request helpers shared by the widget adapters."""

from __future__ import annotations

from typing import Any

import httpx


async def get(client: httpx.AsyncClient, url: str, headers: dict[str, str], **params: Any) -> Any:
    resp = await client.get(url, headers=headers, params=params or None)
    resp.raise_for_status()
    return resp.json()


def expect[T](value: Any, kind: type[T]) -> T:
    """Fail with a clear reason when an app answers with the wrong JSON shape."""
    if not isinstance(value, kind):
        raise ValueError(f"expected a JSON {kind.__name__}")
    return value
