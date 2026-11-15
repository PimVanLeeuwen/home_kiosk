"""Write protection without a login.

The hub has no accounts: the network is the boundary. What still has to be
stopped is another website, open in the same browser, sending requests to the
hub on your behalf. Browsers attach an Origin header to cross-site requests,
so writes are refused unless they come from the hub's own origin, and they
must be JSON, which a plain HTML form cannot send.

That check compares the Origin with the Host, and DNS rebinding makes the two
match: a website points its own name at the NAS, and the browser then sends
that name as both. So the hub also answers only to names it knows
(`KnownHosts`): IP addresses, which a rebinding page cannot use, and its own
names.
"""

from __future__ import annotations

import ipaddress
import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .store import Store

log = logging.getLogger(__name__)

# Always the hub: development (localhost) and the NAS's own containers, which post
# to http://host.docker.internal:8000 (Watchtower, rclone's backup.sh).
BUILT_IN_HOSTS = {"localhost", "host.docker.internal"}
NAMES_SECONDS = 60  # how long the known names are kept before reading them again


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


def host_name(host: str) -> str:
    """A Host header's name: no port, no IPv6 brackets, no trailing dot, lower case."""
    try:
        name = urlsplit(f"//{host.strip()}").hostname or ""
    except ValueError:  # a broken IPv6 address, like "[::1"
        return ""
    return name.rstrip(".").lower()


def _is_ip(name: str) -> bool:
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return False
    return True


def allowed_host(host: str, names: set[str]) -> bool:
    """True for a Host header the hub answers to. An IP address always passes: a
    rebinding page reaches the hub under its own domain name, never an address."""
    name = host_name(host)
    if not name:
        return not host.strip()  # no Host at all (HTTP/1.0); a browser always sends one
    return (_is_ip(name) or name in BUILT_IN_HOSTS or name.endswith(".localhost")
            or name in names)


def hub_names(cfg: dict[str, Any], store: Store | None) -> set[str]:
    """The names the hub is reached by: `hub.url`'s, the NAS's Tailscale name (full
    and short) as the `hosts` job last read it, and any `hub.host_names`."""
    hub = cfg.get("hub") or {}
    names = {host_name(str(n)) for n in hub.get("host_names") or []}
    tailscale = []
    if hub.get("url"):
        names.add(host_name(urlsplit(hub["url"]).netloc))
    if store is not None:
        hosts = store.get_cache("hosts") or {}
        tailscale.append(host_name((hosts.get("tailscale") or {}).get("dns_name") or ""))
    for name in [*tailscale, *(n for n in names if n.endswith(".ts.net"))]:
        if name:
            names.update({name, name.split(".")[0]})  # MagicDNS also answers the short name
    names.discard("")
    return names


class KnownHosts:
    """ASGI middleware: 421 for a request to a name the hub does not know."""

    def __init__(self, app: ASGIApp, names: Callable[[], set[str]]) -> None:
        self.app, self.names = app, names
        self._kept: tuple[float, set[str]] | None = None

    def _known(self) -> set[str]:
        now = time.monotonic()
        if self._kept is None or now - self._kept[0] > NAMES_SECONDS:
            try:
                names = self.names()
            except Exception:  # an unreadable store: keep the last names, not a 500
                log.exception("could not read the hub's host names")
                names = self._kept[1] if self._kept else set()
            self._kept = (now, names)
        return self._kept[1]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            host = next((v.decode("latin-1") for k, v in scope["headers"] if k == b"host"), "")
            if not allowed_host(host, self._known()):
                log.warning("refused a request for the unknown host name %r", host_name(host)[:100])
                response = JSONResponse({"detail": "Unknown host name."}, status_code=421)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
