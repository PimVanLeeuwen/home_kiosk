"""Write protection without a login.

The hub has no accounts: the network is the boundary. What still has to be
stopped is another website, open in the same browser, sending requests to the
hub on your behalf. Browsers attach an Origin header to cross-site requests,
so writes are refused unless they come from the hub's own origin, and they
must be JSON, which a plain HTML form cannot send.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request


def same_origin_json(request: Request) -> None:
    """FastAPI dependency for every endpoint that changes something."""
    origin = request.headers.get("origin")
    if origin is not None:
        # Behind Caddy and the Vite proxy the Host header is the address the
        # browser used, so it is what the Origin has to match.
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        if urlsplit(origin).netloc.lower() != host.lower():
            raise HTTPException(status_code=403, detail="Cross-site requests are not allowed.")

    content_type = request.headers.get("content-type", "")
    if request.method in ("POST", "PUT", "PATCH") and not content_type.startswith(
        "application/json"
    ):
        raise HTTPException(status_code=415, detail="Send JSON.")
