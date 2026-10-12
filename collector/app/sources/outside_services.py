"""The outside services the house depends on, from their public status pages.

Three kinds of page:

    statuspage   <url>/api/v2/summary.json (Atlassian Statuspage, also served by
                 Docker's and Tailscale's pages): components, unresolved incidents
                 and scheduled maintenance
    hetzner      status.hetzner.com has no API; its page carries the systems and
                 incidents as JSON in the __NEXT_DATA__ script tag
    transnoc     TransIP's TransNOC is plain HTML that says "Al onze diensten zijn
                 beschikbaar." when all is well; anything else counts as a problem

Only the components named in config.yaml count: Cloudflare's headline status is
almost always "Partial System Outage" for some far-away colo. Planned maintenance
only shows while it runs. Only the collector talks to these pages.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import OutsideIncident, OutsideService, OutsideServices, OutsideUpdate
from ..store import Store

log = logging.getLogger(__name__)

CACHE_KEY = "outside_services"
TIMEOUT_SECONDS = 15
MAX_UPDATES = 5
MAX_TEXT = 600

RANK = {"ok": 0, "maintenance": 1, "degraded": 2, "outage": 3}
COMPONENT_STATE = {
    "operational": "ok",
    "under_maintenance": "maintenance",
    "degraded_performance": "degraded",
    "partial_outage": "degraded",
    "major_outage": "outage",
}
NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


class PageError(ValueError):
    """The page answered, but not in the shape this module knows."""


def settings(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in cfg.get("outside_services") or [] if s.get("key") and s.get("url")]


def worst(states: list[str]) -> str:
    return max(states, key=lambda s: RANK.get(s, 0), default="ok")


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _text(value: str | None) -> str:
    text = " ".join((value or "").split())
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1].rstrip() + "…"


# --- Statuspage ------------------------------------------------------------------


def parse_statuspage(data: dict[str, Any], watched: list[str], url: str
                     ) -> tuple[str, list[OutsideIncident]]:
    components = data.get("components") or []
    if watched:
        names = {n.lower() for n in watched}
        chosen = [c for c in components if str(c.get("name", "")).lower() in names]
        if not chosen:
            raise PageError("none of the watched components are on the page")
    else:
        chosen = [c for c in components if not c.get("group")]
    ids = {c["id"] for c in chosen}
    for c in chosen:  # a watched group covers its members
        ids.update(c.get("components") or [])

    def counts(item: dict[str, Any]) -> bool:
        affected = {c.get("id") for c in item.get("components") or []}
        return not watched or bool(affected & ids)

    incidents = []
    for inc in data.get("incidents") or []:
        if inc.get("status") in ("resolved", "postmortem") or not counts(inc):
            continue
        impact = "outage" if inc.get("impact") in ("major", "critical") else "degraded"
        incidents.append(_statuspage_incident(inc, impact, url))
    for m in data.get("scheduled_maintenances") or []:
        if m.get("status") == "in_progress" and counts(m):
            incidents.append(_statuspage_incident(m, "maintenance", url))

    states = [COMPONENT_STATE.get(c.get("status"), "ok") for c in components
              if c.get("id") in ids]
    return worst(states + [i.impact for i in incidents]), incidents


def _statuspage_incident(inc: dict[str, Any], impact: str, url: str) -> OutsideIncident:
    updates = [
        OutsideUpdate(at=at, status=u.get("status") or "", text=_text(u.get("body")))
        for u in inc.get("incident_updates") or []
        if (at := _when(u.get("display_at") or u.get("created_at")))
    ]
    updates.sort(key=lambda u: u.at)
    return OutsideIncident(
        title=inc.get("name") or "Incident", impact=impact, status=inc.get("status") or "",
        started_at=_when(inc.get("started_at") or inc.get("created_at")),
        url=inc.get("shortlink") or f"{url.rstrip('/')}/incidents/{inc.get('id')}",
        updates=updates[-MAX_UPDATES:])


# --- Hetzner ---------------------------------------------------------------------

HETZNER_IMPACT = {"outage": "outage", "warning": "degraded", "maintenance": "maintenance"}


def parse_hetzner(html: str, watched: list[str], skip_titles: list[str], url: str,
                  now: datetime) -> tuple[str, list[OutsideIncident]]:
    found = NEXT_DATA.search(html)
    if not found:
        raise PageError("no __NEXT_DATA__ on the Hetzner status page")
    try:
        props = json.loads(found.group(1))["props"]["pageProps"]
        systems, lists = props["systems"], props["incidents"]
    except (ValueError, KeyError, TypeError) as exc:
        raise PageError("the Hetzner status page changed shape") from exc

    parent = {s.get("@id"): s.get("parent") for s in systems}
    names = {n.lower() for n in watched}
    roots = {s.get("@id") for s in systems if str(s.get("titleEn", "")).lower() in names}
    if watched and not roots:
        raise PageError("none of the watched systems are on the page")

    def counts(system: str | None) -> bool:
        seen = set()
        while system and system not in seen:
            if system in roots:
                return True
            seen.add(system)
            system = parent.get(system)
        return not watched

    skip = re.compile(r"\b(" + "|".join(map(re.escape, skip_titles)) + r")\b", re.I) \
        if skip_titles else None
    incidents, seen_ids = [], set()
    for inc in (i for group in lists.values() for i in group or []):
        if inc.get("id") in seen_ids:
            continue
        seen_ids.add(inc.get("id"))
        impact = HETZNER_IMPACT.get(inc.get("incidentType"))
        start, end = _when(inc.get("startTime")), _when(inc.get("endTime"))
        title = inc.get("titleEn") or inc.get("titleDe") or "Incident"
        if (impact is None or inc.get("incidentState") == "resolved"
                or (start and start > now) or (end and end <= now)
                or not counts(inc.get("system")) or (skip and skip.search(title))):
            continue
        updates = [
            OutsideUpdate(at=at, status=u.get("incidentState") or "",
                          text=_text(u.get("descriptionEn") or u.get("descriptionDe")))
            for u in inc.get("incidentUpdates") or []
            if u.get("visible", True) and (at := _when(u.get("createdAt")))
        ]
        updates.sort(key=lambda u: u.at)
        incidents.append(OutsideIncident(
            title=title, impact=impact, status=inc.get("incidentState") or "",
            started_at=start, url=f"{url.rstrip('/')}/incident/{inc.get('uuid')}",
            updates=updates[-MAX_UPDATES:]))
    return worst([i.impact for i in incidents]), incidents


# --- TransNOC --------------------------------------------------------------------


def parse_transnoc(html: str, ok_text: str, url: str) -> tuple[str, list[OutsideIncident]]:
    if ok_text.lower() in " ".join(html.split()).lower():
        return "ok", []
    return "degraded", [OutsideIncident(
        title="TransNOC reports a problem", impact="degraded", status="open", url=url)]


# --- Collect ---------------------------------------------------------------------


async def _check(client: httpx.AsyncClient, svc: dict[str, Any], now: datetime
                 ) -> tuple[str, list[OutsideIncident]]:
    kind, url = svc.get("kind", "statuspage"), svc["url"]
    if kind == "statuspage":
        resp = await client.get(f"{url.rstrip('/')}/api/v2/summary.json")
        resp.raise_for_status()
        return parse_statuspage(resp.json(), svc.get("components") or [], url)
    resp = await client.get(url)
    resp.raise_for_status()
    if kind == "hetzner":
        return parse_hetzner(resp.text, svc.get("systems") or [],
                             svc.get("skip_titles") or [], url, now)
    if kind == "transnoc":
        return parse_transnoc(resp.text, svc.get("ok_text", "Al onze diensten zijn beschikbaar"),
                              url)
    raise PageError(f"unknown kind {kind}")


def _reason(exc: BaseException) -> str:
    if isinstance(exc, PageError):
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        return f"the status page answered {exc.response.status_code}"
    if isinstance(exc, httpx.HTTPError):
        return "the status page could not be reached"
    return "the status page could not be read"


async def collect(cfg: dict[str, Any], store: Store,
                  transport: httpx.AsyncBaseTransport | None = None,
                  now: datetime | None = None) -> OutsideServices:
    """`transport` and `now` are for tests."""
    now = now or datetime.now(UTC)
    services = settings(cfg)
    previous = {s["key"]: s for s in (store.get_cache(CACHE_KEY) or {}).get("services", [])}
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport,
                                 follow_redirects=True) as client:
        results = await asyncio.gather(*(_check(client, s, now) for s in services),
                                       return_exceptions=True)

    out = []
    for svc, result in zip(services, results, strict=True):
        base = {"key": svc["key"], "name": svc.get("name", svc["key"]), "url": svc["url"]}
        if not isinstance(result, BaseException):
            state, incidents = result
            out.append(OutsideService(**base, state=state, incidents=incidents, as_of=now))
            continue
        reason = _reason(result)
        log.warning("status page of %s failed: %s", svc["key"], reason)
        last = previous.get(svc["key"])
        if last:
            out.append(OutsideService.model_validate(
                {**last, **base, "stale": True, "error": reason}))
        else:
            out.append(OutsideService(**base, state="unknown", as_of=now, stale=True,
                                      error=reason))
    return OutsideServices(as_of=now, services=out)
