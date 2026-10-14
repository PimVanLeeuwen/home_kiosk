"""Lights: the living room through the Hue Bridge's local API (CLIP v2).

A deliberate write (plan.md M17): the hub switches and dims the living room's
lights and sets the kitchen spots' white. Nothing else in the house is touched,
and no Hue cloud is involved.

The bridge is reached by its reserved address over HTTPS. Its certificate must
be signed by one of Signify's roots (hue_ca.pem) and name the bridge's own id,
so another device on the LAN cannot pose as the bridge and learn the key. The
application key (HUE_APPLICATION_KEY in .env) travels in a header only and is
never logged.

State: a full read every minute, kept live in between by the bridge's event
stream, so a change from the switch, Siri or the Home app shows at once.
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from ..models import Envelope
from ..store import Store

log = logging.getLogger(__name__)

CACHE_KEY = "lights"
CA_FILE = Path(__file__).with_name("hue_ca.pem")
TIMEOUT_SECONDS = 10
# The whites offered for lights that have them: warm to cool.
KELVINS = (2200, 2700, 3500, 4500, 6500)
RECONNECT_SECONDS = (5, 15, 60)


class Light(BaseModel):
    id: str
    name: str
    on: bool
    brightness: float  # 0 to 100, as the bridge reports it
    kelvin: int | None = None  # None: a light without whites (filament)
    reachable: bool = True


class LightGroup(BaseModel):
    id: str
    name: str
    kind: Literal["ambiance", "white"]  # ambiance: whites from warm to cool
    on: bool  # any of its lights
    brightness: int  # of the lights that are on, else the last level
    kelvin: int | None = None
    lights: list[Light]


class Lights(Envelope):
    room: str
    groups: list[LightGroup]
    kelvins: list[int] = list(KELVINS)


class HueError(Exception):
    """A failure with a short reason fit for the page; never the key."""


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    hue = cfg.get("hue") or {}
    key = (hue.get("key") or "").strip()
    return {
        "enabled": bool(key and hue.get("bridge") and hue.get("bridge_id")),
        "bridge": str(hue.get("bridge") or ""),
        "bridge_id": str(hue.get("bridge_id") or "").lower(),
        "key": key,
        "room": hue.get("room") or "",
        "groups": hue.get("groups") or [],
    }


def tls_context() -> ssl.SSLContext:
    """Trusts only Signify's roots; the name checked is the bridge id (see Bridge)."""
    return ssl.create_default_context(cafile=str(CA_FILE))


def kelvin_of(mirek: int | None) -> int | None:
    """The bridge's mirek as kelvin, rounded to 100 K."""
    return round(1_000_000 / mirek / 100) * 100 if mirek else None


def mirek_of(kelvin: int, schema: dict[str, int] | None = None) -> int:
    schema = schema or {"mirek_minimum": 153, "mirek_maximum": 500}
    return max(schema["mirek_minimum"], min(schema["mirek_maximum"], round(1_000_000 / kelvin)))


class Bridge:
    def __init__(self, cfg: dict[str, Any],
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        s = settings(cfg)
        self.base = f"https://{s['bridge']}"
        self.bridge_id = s["bridge_id"]
        self.key = s["key"]
        self.transport = transport

    def _client(self, timeout: float | None = TIMEOUT_SECONDS) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base, timeout=timeout, transport=self.transport,
            verify=tls_context() if self.transport is None else True,
            headers={"hue-application-key": self.key})

    # The certificate names the bridge id, not its address: check that name.
    def _ext(self) -> dict[str, str]:
        return {"sni_hostname": self.bridge_id}

    async def get(self, kind: str) -> list[dict[str, Any]]:
        async with self._client() as http:
            resp = await http.get(f"/clip/v2/resource/{kind}", extensions=self._ext())
            return _data(resp)

    async def put(self, kind: str, rid: str, body: dict[str, Any]) -> None:
        async with self._client() as http:
            resp = await http.put(f"/clip/v2/resource/{kind}/{rid}", json=body,
                                  extensions=self._ext())
            _data(resp)

    async def events(self) -> AsyncIterator[list[dict[str, Any]]]:
        """The bridge's event stream: each message is a list of events."""
        async with self._client(timeout=None) as http:
            async with http.stream("GET", "/eventstream/clip/v2", extensions=self._ext(),
                                   headers={"Accept": "text/event-stream"}) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        try:
                            yield json.loads(line[5:].strip())
                        except ValueError:
                            continue


def _data(resp: httpx.Response) -> list[dict[str, Any]]:
    if resp.status_code in (401, 403):
        raise HueError("The bridge refused the key")
    if resp.status_code >= 400:
        raise HueError(f"The bridge answered {resp.status_code}")
    body = resp.json()
    if body.get("errors"):
        # The bridge's own words, such as "device (light) is unreachable".
        raise HueError(str(body["errors"][0].get("description") or "The bridge refused it")[:120])
    return body.get("data") or []


def reason(exc: Exception) -> str:
    if isinstance(exc, HueError):
        return str(exc)
    if isinstance(exc, httpx.TimeoutException):
        return "The bridge did not answer in time"
    if isinstance(exc, httpx.ConnectError):
        return "The bridge is not reachable"
    return "The bridge gave an unexpected answer"


# --- reading the state ---------------------------------------------------------------


def _light(raw: dict[str, Any], reachable: bool) -> Light:
    return Light(
        id=raw["id"], name=(raw.get("metadata") or {}).get("name") or raw["id"],
        on=bool((raw.get("on") or {}).get("on")),
        brightness=float((raw.get("dimming") or {}).get("brightness") or 0),
        kelvin=kelvin_of((raw.get("color_temperature") or {}).get("mirek"))
        if "color_temperature" in raw else None,
        reachable=reachable)


def _group(spec: dict[str, Any], lights: list[Light], ambiance: bool) -> LightGroup:
    lit = [x for x in lights if x.on]
    shown = lit or lights
    level = round(sum(x.brightness for x in shown) / len(shown)) if shown else 0
    kelvin = next((x.kelvin for x in shown if x.kelvin), None) if ambiance else None
    return LightGroup(id=spec["id"], name=spec["name"], kind="ambiance" if ambiance else "white",
                      on=bool(lit), brightness=max(level, 1) if lit else level, kelvin=kelvin,
                      lights=lights)


def build(cfg: dict[str, Any], raw_lights: list[dict[str, Any]],
          unreachable: set[str], now: datetime) -> Lights:
    """The page's answer from the bridge's lights, grouped as in config.yaml.
    `unreachable` holds the ids of devices that have lost their Zigbee link."""
    s = settings(cfg)
    by_name = {(x.get("metadata") or {}).get("name"): x for x in raw_lights}
    groups = []
    for spec in s["groups"]:
        found = [by_name[n] for n in spec.get("lights") or [] if n in by_name]
        lights = [_light(x, (x.get("owner") or {}).get("rid") not in unreachable)
                  for x in found]
        ambiance = bool(found) and all("color_temperature" in x for x in found)
        groups.append(_group(spec, lights, ambiance))
    return Lights(as_of=now, stale=False, room=s["room"], groups=groups)


async def collect(cfg: dict[str, Any], bridge: Bridge | None = None,
                  now: datetime | None = None) -> Lights:
    bridge = bridge or Bridge(cfg)
    raw = await bridge.get("light")
    links = await bridge.get("zigbee_connectivity")
    unreachable = {(x.get("owner") or {}).get("rid") for x in links
                   if x.get("status") not in (None, "connected")}
    return build(cfg, raw, unreachable, now or datetime.now(UTC))


# --- live updates ---------------------------------------------------------------------


def apply_events(payload: dict[str, Any], events: list[dict[str, Any]],
                 now: datetime) -> bool:
    """Patch a cached answer with the bridge's light updates. Returns whether it changed."""
    changed = False
    lights = {x["id"]: x for g in payload.get("groups") or [] for x in g["lights"]}
    for event in events:
        if event.get("type") != "update":
            continue
        for item in event.get("data") or []:
            light = lights.get(item.get("id"))
            if item.get("type") != "light" or light is None:
                continue
            if "on" in item:
                light["on"] = bool(item["on"].get("on"))
            if "dimming" in item:
                light["brightness"] = float(item["dimming"].get("brightness") or 0)
            if (item.get("color_temperature") or {}).get("mirek"):
                light["kelvin"] = kelvin_of(item["color_temperature"]["mirek"])
            changed = True
    if changed:
        for g in payload["groups"]:
            fresh = _group(g, [Light.model_validate(x) for x in g["lights"]],
                           g["kind"] == "ambiance")
            g.update(fresh.model_dump(mode="json", include={"on", "brightness", "kelvin"}))
        payload["as_of"] = now.isoformat()
    return changed


async def listen(cfg: dict[str, Any], store: Store, bridge: Bridge | None = None) -> None:
    """Keep the cached answer live from the event stream; reconnects for ever."""
    bridge = bridge or Bridge(cfg)
    failures = 0
    while True:
        try:
            async for events in bridge.events():
                failures = 0
                payload = store.get_cache(CACHE_KEY)
                if payload and apply_events(payload, events, datetime.now(UTC)):
                    store.put_cache(CACHE_KEY, payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("hue event stream dropped: %s", type(exc).__name__)
        wait = RECONNECT_SECONDS[min(failures, len(RECONNECT_SECONDS) - 1)]
        failures += 1
        await asyncio.sleep(wait)


# --- changes --------------------------------------------------------------------------


async def change(cfg: dict[str, Any], store: Store, group_id: str, *, on: bool | None = None,
                 brightness: int | None = None, kelvin: int | None = None,
                 bridge: Bridge | None = None) -> Lights:
    """Switch, dim or set the white of one configured group, then read back what
    the bridge has, so the answer is the bridge's state and not a guess."""
    bridge = bridge or Bridge(cfg)
    spec = next((g for g in settings(cfg)["groups"] if g["id"] == group_id), None)
    if spec is None:
        raise KeyError(group_id)
    raw = {(x.get("metadata") or {}).get("name"): x for x in await bridge.get("light")}
    targets = [raw[n] for n in spec.get("lights") or [] if n in raw]
    if kelvin is not None and not all("color_temperature" in x for x in targets):
        raise ValueError("these lights have no whites to choose from")
    for light in targets:
        body: dict[str, Any] = {}
        if on is not None:
            body["on"] = {"on": on}
        if brightness is not None:
            body["dimming"] = {"brightness": brightness}
            body.setdefault("on", {"on": True})
        if kelvin is not None:
            schema = (light.get("color_temperature") or {}).get("mirek_schema")
            body["color_temperature"] = {"mirek": mirek_of(kelvin, schema)}
            body.setdefault("on", {"on": True})
        await bridge.put("light", light["id"], body)
    return await _refresh(cfg, store, bridge)


async def switch_room(cfg: dict[str, Any], store: Store, on: bool,
                      bridge: Bridge | None = None) -> Lights:
    """All the room's configured lights on or off at once."""
    bridge = bridge or Bridge(cfg)
    names = {n for g in settings(cfg)["groups"] for n in g.get("lights") or []}
    for light in await bridge.get("light"):
        if (light.get("metadata") or {}).get("name") in names:
            await bridge.put("light", light["id"], {"on": {"on": on}})
    return await _refresh(cfg, store, bridge)


async def _refresh(cfg: dict[str, Any], store: Store, bridge: Bridge) -> Lights:
    fresh = await collect(cfg, bridge)
    store.put_cache(CACHE_KEY, fresh.model_dump(mode="json"))
    return fresh
