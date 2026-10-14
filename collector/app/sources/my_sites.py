"""My sites: the owner's own websites, 30 days of uptime, from Uptime Kuma.

Kuma already checks each site (an HTTP monitor) and messages the hub when one
goes down. Its public status page for the sites (slug in config.yaml) gives the
groups and names, and the latest 100 heartbeats per monitor: under two hours at
one a minute. So the hub keeps its own record: every minute it adds the time
between each new heartbeat and the one before to that site's local day, as up
or down seconds. From those days come the 30 segments of the Services section
and the House panel's rings, and the 30-day uptime.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel

from ..models import Envelope
from ..store import Store

log = logging.getLogger(__name__)

CACHE_KEY = "sites"
DAYS = 30
# Kuma's heartbeat statuses (src/util.ts).
DOWN, UP = 0, 1
# A day with more than this down counts as an outage; anything less, a blip.
OUTAGE = timedelta(minutes=5)
# A longer gap between heartbeats (the hub or Kuma stopped) counts as unknown.
MAX_GAP = timedelta(minutes=10)
TIMEOUT_SECONDS = 8

TABLES = """
CREATE TABLE IF NOT EXISTS site_day (
    monitor_id   INTEGER NOT NULL,
    day          TEXT NOT NULL,      -- local date, YYYY-MM-DD
    up_seconds   REAL NOT NULL DEFAULT 0,
    down_seconds REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (monitor_id, day)
);
CREATE TABLE IF NOT EXISTS site_last_beat (
    monitor_id INTEGER PRIMARY KEY,
    at         TEXT NOT NULL,        -- UTC, ISO
    status     INTEGER NOT NULL
);
"""

Day = Literal["up", "blip", "down", "none"]


class Site(BaseModel):
    id: int
    name: str
    group: str
    up: bool | None  # None: no heartbeat yet
    down_since: datetime | None = None
    ping_ms: int | None = None
    uptime_pct: float | None  # over the recorded part of the last 30 days
    days: list[Day]  # DAYS of them, oldest first, today last


class Sites(Envelope):
    sites: list[Site]


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


def settings(cfg: dict[str, Any], store: Store) -> dict[str, Any]:
    slug = ((cfg.get("my_sites") or {}).get("kuma_slug") or "").strip()
    port = next((s.port for s in store.list_services() if s.widget == "uptimekuma" and s.port),
                None)
    host = (cfg.get("widgets") or {}).get("host", "localhost")
    return {"enabled": bool(slug and port), "slug": slug,
            "url": f"http://{host}:{port}" if port else "",
            "timezone": ZoneInfo(cfg.get("timezone", "Europe/Amsterdam"))}


def _beat_time(value: str) -> datetime:
    """Kuma writes UTC without a zone: "2026-10-14 09:15:02"."""
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def record(store: Store, monitor_id: int, beats: list[dict[str, Any]], tz: ZoneInfo) -> None:
    """Add the time between each heartbeat not seen before and the one before
    it to that one's local day. Pending and maintenance beats count as neither."""
    with store.connect() as conn:
        row = conn.execute("SELECT at, status FROM site_last_beat WHERE monitor_id = ?",
                           (monitor_id,)).fetchone()
        last = (datetime.fromisoformat(row["at"]), row["status"]) if row else None
        for beat in sorted(beats, key=lambda b: b["time"]):
            at, status = _beat_time(beat["time"]), int(beat["status"])
            if last and at <= last[0]:
                continue
            if last and at - last[0] <= MAX_GAP and status in (UP, DOWN):
                gap = (at - last[0]).total_seconds()
                column = "down_seconds" if status == DOWN else "up_seconds"
                # `column` is one of two fixed names, never input.
                conn.execute(
                    f"INSERT INTO site_day (monitor_id, day, {column}) VALUES (?, ?, ?) "
                    f"ON CONFLICT(monitor_id, day) DO UPDATE SET "
                    f"{column} = {column} + excluded.{column}",
                    (monitor_id, at.astimezone(tz).date().isoformat(), gap))
            last = (at, status)
        if last:
            conn.execute(
                "INSERT INTO site_last_beat (monitor_id, at, status) VALUES (?, ?, ?) "
                "ON CONFLICT(monitor_id) DO UPDATE SET at = excluded.at, status = excluded.status",
                (monitor_id, last[0].isoformat(), last[1]))


def history(store: Store, monitor_id: int, today: date) -> tuple[list[Day], float | None]:
    """The last DAYS days, oldest first, and the uptime over what was recorded."""
    first = today - timedelta(days=DAYS - 1)
    with store.connect() as conn:
        rows = {r["day"]: r for r in conn.execute(
            "SELECT day, up_seconds, down_seconds FROM site_day WHERE monitor_id = ? AND day >= ?",
            (monitor_id, first.isoformat()))}
    days: list[Day] = []
    up = down = 0.0
    for offset in range(DAYS):
        row = rows.get((first + timedelta(days=offset)).isoformat())
        if row is None or row["up_seconds"] + row["down_seconds"] == 0:
            days.append("none")
            continue
        up, down = up + row["up_seconds"], down + row["down_seconds"]
        days.append("down" if row["down_seconds"] > OUTAGE.total_seconds()
                    else "blip" if row["down_seconds"] > 0 else "up")
    total = up + down
    return days, (round(up / total * 100, 2) if total else None)


def _current(beats: list[dict[str, Any]]) -> tuple[bool | None, datetime | None, int | None]:
    """Up now, since when it is down (from the beats Kuma still returns), the last ping."""
    judged = [b for b in sorted(beats, key=lambda b: b["time"]) if b.get("status") in (UP, DOWN)]
    if not judged:
        return None, None, None
    latest = judged[-1]
    ping = int(latest["ping"]) if latest.get("ping") is not None else None
    if latest["status"] == UP:
        return True, None, ping
    since = latest
    for beat in reversed(judged):
        if beat["status"] != DOWN:
            break
        since = beat
    return False, _beat_time(since["time"]), ping


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  transport: httpx.AsyncBaseTransport | None = None) -> Sites:
    """Raises when Kuma cannot be read, so the last good answer stays cached,
    flagged stale (the day record simply has a gap)."""
    s = settings(cfg, store)
    now = now or datetime.now(UTC)
    async with httpx.AsyncClient(base_url=s["url"], timeout=TIMEOUT_SECONDS,
                                 transport=transport) as client:
        page = (await client.get(f"/api/status-page/{s['slug']}")).raise_for_status().json()
        beats = (await client.get(f"/api/status-page/heartbeat/{s['slug']}")
                 ).raise_for_status().json().get("heartbeatList") or {}

    today = now.astimezone(s["timezone"]).date()
    sites = []
    for group in page.get("publicGroupList") or []:
        for monitor in group.get("monitorList") or []:
            mid = int(monitor["id"])
            own = beats.get(str(mid)) or []
            record(store, mid, own, s["timezone"])
            up, since, ping = _current(own)
            days, uptime = history(store, mid, today)
            sites.append(Site(id=mid, name=(monitor.get("name") or "").strip(),
                              group=(group.get("name") or "").strip(), up=up, down_since=since,
                              ping_ms=ping, uptime_pct=uptime, days=days))
    return Sites(as_of=now, stale=False, sites=sites)
