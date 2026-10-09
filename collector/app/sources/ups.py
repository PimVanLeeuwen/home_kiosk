"""The UPS on the NAS, read over NUT, with a record of every power cut.

UGOS runs a NUT server for the UGREEN US3000 on USB (ups0, port 3493, reading
needs no login). The collector asks for all variables every 15 seconds. The
US3000 is a DC UPS: its voltages say nothing about mains power and its runtime
always reads 65535 (no value), so neither is used.

The router is not on a UPS, so nothing can reach Telegram during a power cut.
Each outage is kept in SQLite instead, from the first reading on battery to the
first reading on mains again, and reported in one message once it is over. That
message is retried until it goes out, since the internet comes back later than
the NAS. Below battery.charge.low (15%) UGOS stops all services, the hub too,
so for a long outage the end is when the hub saw power again after its restart.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from ..alerts import core as alerts_core
from ..alerts import templates
from ..models import Ups, UpsOutage
from ..store import Store

log = logging.getLogger(__name__)

Status = Literal["online", "on_battery", "low_battery", "unknown"]

CACHE_KEY = "ups"
TIMEOUT_SECONDS = 5
MAX_OUTAGES = 10
REPORT_FOR = timedelta(hours=48)  # give up on a report that cannot be sent by then

TABLES = """
CREATE TABLE IF NOT EXISTS ups_outage (
    id            INTEGER PRIMARY KEY,
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    lowest_charge INTEGER,
    reached_low   INTEGER NOT NULL DEFAULT 0,
    reported      INTEGER NOT NULL DEFAULT 0
);
"""


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    ups = cfg.get("ups") or {}
    return {"host": ups.get("host", "host.docker.internal"), "port": int(ups.get("port", 3493)),
            "name": ups.get("name", "ups0"), "enabled": bool(ups.get("host"))}


async def read_vars(host: str, port: int, name: str) -> dict[str, str]:
    """All of the UPS's variables, by NUT's LIST VAR."""
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), TIMEOUT_SECONDS)
    try:
        writer.write(f"LIST VAR {name}\n".encode())
        await writer.drain()
        values: dict[str, str] = {}
        while True:
            line = (await asyncio.wait_for(reader.readline(), TIMEOUT_SECONDS)).decode().strip()
            if not line:
                raise ConnectionError("NUT closed the connection")
            if line.startswith("ERR"):
                raise ValueError(f"NUT answered {line}")
            if line.startswith("END LIST VAR"):
                return values
            if line.startswith("VAR "):
                # VAR ups0 battery.charge "100"
                _, _, key, value = line.split(" ", 3)
                values[key] = value.strip('"')
    finally:
        writer.write(b"LOGOUT\n")
        writer.close()


def _int(value: str | None) -> int | None:
    try:
        return round(float(value)) if value not in (None, "") else None
    except ValueError:
        return None


def status_of(values: dict[str, str]) -> tuple[Status, int | None, int | None]:
    flags = values.get("ups.status", "").split()
    charge = _int(values.get("battery.charge"))
    low = _int(values.get("battery.charge.low"))
    # The driver runs with ignorelb, so the charge is checked as well as LB.
    if "LB" in flags or ("OB" in flags and charge is not None and low is not None
                         and charge <= low):
        return "low_battery", charge, low
    if "OB" in flags:
        return "on_battery", charge, low
    if "OL" in flags:
        return "online", charge, low
    return "unknown", charge, low


def track(store: Store, status: str, charge: int | None, now: datetime) -> None:
    """Open, update or close the outage record for this reading."""
    with store.connect() as conn:
        current = conn.execute(
            "SELECT id, lowest_charge FROM ups_outage WHERE ended_at IS NULL").fetchone()
        if status in ("on_battery", "low_battery"):
            low = int(status == "low_battery")
            if current is None:
                conn.execute("INSERT INTO ups_outage (started_at, lowest_charge, reached_low) "
                             "VALUES (?, ?, ?)", (now.isoformat(), charge, low))
            else:
                known = [c for c in (current["lowest_charge"], charge) if c is not None]
                lowest = min(known) if known else None
                conn.execute("UPDATE ups_outage SET lowest_charge = ?, "
                             "reached_low = MAX(reached_low, ?) WHERE id = ?",
                             (lowest, low, current["id"]))
        elif status == "online" and current is not None:
            conn.execute("UPDATE ups_outage SET ended_at = ? WHERE id = ?",
                         (now.isoformat(), current["id"]))


def outages(store: Store, limit: int = MAX_OUTAGES) -> list[UpsOutage]:
    with store.connect() as conn:
        rows = conn.execute("SELECT * FROM ups_outage ORDER BY started_at DESC LIMIT ?",
                            (limit,)).fetchall()
    return [UpsOutage(started_at=r["started_at"], ended_at=r["ended_at"],
                      lowest_charge=r["lowest_charge"], reached_low=bool(r["reached_low"]))
            for r in rows]


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  values: dict[str, str] | None = None) -> Ups:
    """`values` is for tests; normally they are read from NUT."""
    now = now or datetime.now(UTC)
    ups = settings(cfg)
    if values is None:
        values = await read_vars(ups["host"], ups["port"], ups["name"])
    status, charge, low = status_of(values)
    track(store, status, charge, now)
    model = " ".join(v for v in (values.get("device.mfr"), values.get("device.model")) if v)
    return Ups(as_of=now, name=ups["name"], model=model or None, status=status,
               status_raw=values.get("ups.status", ""), charge=charge, charge_low=low,
               load=_int(values.get("ups.load")), outages=outages(store))


def _duration(start: datetime, end: datetime) -> str:
    minutes = max(1, round((end - start).total_seconds() / 60))
    hours, rest = divmod(minutes, 60)
    return f"{hours} h {rest} min" if hours else f"{minutes} min"


async def report_outages(store: Store, cfg: dict[str, Any], now: datetime | None = None,
                         telegram: Any = None) -> int:
    """Send one message per finished, unreported outage; keep trying until it
    goes out (the internet may come back well after the NAS). Returns how many
    went out."""
    now = now or datetime.now(UTC)
    with store.connect() as conn:
        rows = conn.execute("SELECT * FROM ups_outage WHERE ended_at IS NOT NULL "
                            "AND reported = 0 ORDER BY started_at").fetchall()
    sent = 0
    for row in rows:
        start, end = (datetime.fromisoformat(row["started_at"]),
                      datetime.fromisoformat(row["ended_at"]))
        if now - end > REPORT_FOR:
            status = "given up"
        else:
            start, end = alerts_core.local(start, cfg), alerts_core.local(end, cfg)
            msg = templates.message(store, "ups_outage", {
                "duration": _duration(start, end),
                "start": start.strftime("%a %d %b %H:%M"),
                "end": end.strftime("%H:%M" if start.date() == end.date() else "%a %d %b %H:%M"),
                "lowest": row["lowest_charge"] if row["lowest_charge"] is not None else "?",
                "stopped": ("The charge reached the 15% stop, so the NAS stopped its services."
                            if row["reached_low"] else ""),
            }, "warning")
            result = await alerts_core.notify(
                store, cfg, source="ups", category="rules", severity="warning",
                title=msg.title, body=msg.body, formatted=msg.html, now=now, telegram=telegram)
            if result.status == "failed":
                continue
            status, sent = result.status, sent + 1
        log.info("power cut report %s", status)
        with store.connect() as conn:
            conn.execute("UPDATE ups_outage SET reported = 1 WHERE id = ?", (row["id"],))
    return sent
