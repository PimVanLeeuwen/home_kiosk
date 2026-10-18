"""Waking the living room Apple TV for music (plan.md M18).

A deliberate write: when a favourite should start on the Apple TV and Spotify
does not list it (asleep, or the Spotify app closed), the hub switches it on
and opens the Spotify app over pyatv's Companion protocol, with credentials
from a one-time PIN pairing (APPLE_TV_LIVING_ROOM_COMPANION in .env). Nothing
else is ever sent to the TV.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10
SPOTIFY = "com.spotify.client"


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    wake = (cfg.get("music") or {}).get("wake") or {}
    credentials = (wake.get("credentials") or "").strip()
    return {"enabled": bool(credentials and wake.get("address")),
            "address": str(wake.get("address") or ""), "credentials": credentials,
            "app": wake.get("app") or SPOTIFY}


async def _wake(address: str, credentials: str, app: str) -> None:
    import pyatv
    from pyatv.const import PowerState, Protocol

    loop = asyncio.get_running_loop()
    found = await pyatv.scan(loop, hosts=[address], timeout=3)
    if not found:
        raise ConnectionError("the Apple TV did not answer")
    conf = found[0]
    conf.set_credentials(Protocol.Companion, credentials)
    atv = await pyatv.connect(conf, loop)
    try:
        if atv.power.power_state != PowerState.On:
            await atv.power.turn_on()
        await atv.apps.launch_app(app)
    finally:
        atv.close()


async def wake_spotify(cfg: dict[str, Any]) -> bool:
    """Switch the Apple TV on and open Spotify. Returns whether it was done;
    False without credentials, or when the TV could not be reached."""
    s = settings(cfg)
    if not s["enabled"]:
        return False
    try:
        await asyncio.wait_for(_wake(s["address"], s["credentials"], s["app"]), TIMEOUT_SECONDS)
    except Exception as exc:
        # The class only: pyatv's messages can carry addresses and identifiers.
        log.warning("waking the Apple TV failed: %s", type(exc).__name__)
        return False
    return True
