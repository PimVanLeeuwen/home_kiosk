"""The hub's own alert rules, checked every minute against data it already has.

A rule turns its input into problems, each with a stable key (one per pool,
disk, container or volume). A new problem opens an incident and sends one
message; when the problem is gone the incident is resolved with one more
message. A rule whose input is missing or stale is skipped entirely, so a
collection hiccup never "resolves" a real problem.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from ..store import Store
from . import core

log = logging.getLogger(__name__)

TABLES = """
CREATE TABLE IF NOT EXISTS alert_incident (
    key          TEXT PRIMARY KEY,
    rule         TEXT NOT NULL,
    severity     TEXT NOT NULL,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL DEFAULT '',
    opened_at    TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    resolved_at  TEXT
);
"""

DEFAULT_RULES: dict[str, dict[str, Any]] = {
    "disk_space": {"enabled": True, "threshold_pct": 90},
    "container_health": {"enabled": True, "unhealthy_minutes": 5, "restarts": 3,
                         "restart_window_minutes": 10},
    "backup_missing": {"enabled": True, "hours": 26},
    "smart": {"enabled": True},
    "portfolio_move": {"enabled": False, "threshold_pct": 3},
}

RULE_LABELS = {
    "disk_space": "Disk space",
    "container_health": "Container health",
    "backup_missing": "Backup missing",
    "smart": "Disk SMART",
    "portfolio_move": "Portfolio move",
}

# Rules whose problems end on their own and need no "resolved" message.
NO_RESOLVE = {"portfolio_move"}

# Input older than this counts as missing: its rule is skipped.
FRESH = timedelta(minutes=15)


@dataclass(frozen=True)
class Problem:
    key: str
    rule: str
    severity: core.Severity
    title: str
    body: str = ""


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


def rule_settings(store: Store) -> dict[str, dict[str, Any]]:
    saved = core.get_setting(store, "rules", {})
    return {name: defaults | saved.get(name, {}) for name, defaults in DEFAULT_RULES.items()}


def _fresh(payload: dict[str, Any] | None, now: datetime) -> dict[str, Any] | None:
    """The cached payload if it is current enough to judge by, else None."""
    if not payload or payload.get("stale"):
        return None
    as_of = payload.get("as_of")
    if as_of and now - datetime.fromisoformat(as_of) > FRESH:
        return None
    return payload


def _size(n: float) -> str:
    for unit, factor in (("TB", 1e12), ("GB", 1e9), ("MB", 1e6)):
        if n >= factor:
            return f"{n / factor:.1f} {unit}".replace(".", ",")
    return f"{int(n)} B"


# --- the rules: each returns its problems, or None when it cannot judge ---------


def disk_space(nas: dict[str, Any] | None, settings: dict[str, Any]) -> list[Problem] | None:
    if nas is None:
        return None
    limit = settings["threshold_pct"]
    return [
        Problem(
            key=f"disk_space:{pool['name']}", rule="disk_space", severity="warning",
            title=f"{pool['name']} is {int(pool['used_pct'])}% full",
            body=f"{_size(pool['free_bytes'])} left of {_size(pool['total_bytes'])}",
        )
        for pool in nas["storage"]["pools"]
        if pool["used_pct"] >= limit
    ]


def smart(nas: dict[str, Any] | None, settings: dict[str, Any]) -> list[Problem] | None:
    if nas is None:
        return None
    problems = []
    for disk in nas.get("disks", []):
        if disk["smart"] == "fail":
            problems.append(Problem(f"smart:{disk['name']}", "smart", "error",
                                    f"Disk {disk['name']} is failing (SMART)",
                                    "Check Scrutiny and plan a replacement."))
        elif disk["smart"] == "warn":
            problems.append(Problem(f"smart:{disk['name']}", "smart", "warning",
                                    f"Disk {disk['name']} has SMART warnings", "Check Scrutiny."))
    return problems


def container_health(
    containers: dict[str, Any] | None,
    catalog: list[Any],
    dies: dict[str, int] | None,
    pending: dict[str, str],
    settings: dict[str, Any],
    now: datetime,
) -> list[Problem] | None:
    """Unhealthy or down for a while, or stuck restarting. `pending` holds when
    a condition was first seen (updated in place) so short blips stay quiet."""
    if containers is None:
        return None
    by_name = {c["name"]: c for c in containers.get("containers", [])}
    grace = timedelta(minutes=settings["unhealthy_minutes"])
    seen_now: set[str] = set()
    problems: list[Problem] = []

    def lasting(key: str) -> timedelta:
        seen_now.add(key)
        first = pending.setdefault(key, now.isoformat())
        return now - datetime.fromisoformat(first)

    for c in by_name.values():
        if c["state"] == "running" and c.get("health") == "unhealthy":
            key = f"unhealthy:{c['name']}"
            if (lasted := lasting(key)) >= grace:
                problems.append(Problem(key, "container_health", "warning",
                                        f"{c['name']} is unhealthy",
                                        f"for {int(lasted.total_seconds() // 60)} min"))

    # Services in the catalog are expected to run.
    for service in catalog:
        if not service.container:
            continue
        c = by_name.get(service.container)
        if c is None or c["state"] != "running":
            key = f"down:{service.container}"
            if lasting(key) >= grace:
                state = c["state"] if c else "no container"
                problems.append(Problem(key, "container_health", "error",
                                        f"{service.name} is down",
                                        f"container {service.container}: {state}"))

    for name, count in (dies or {}).items():
        if count >= settings["restarts"]:
            problems.append(Problem(
                f"restarting:{name}", "container_health", "warning",
                f"{name} keeps restarting",
                f"{count} restarts in {settings['restart_window_minutes']} min"))

    for key in [k for k in pending if k not in seen_now]:
        del pending[key]
    return problems


def backup_missing(
    backups: dict[str, Any] | None, nas: dict[str, Any] | None,
    settings: dict[str, Any], now: datetime,
) -> list[Problem] | None:
    limit = timedelta(hours=settings["hours"])
    volumes = (backups or {}).get("volumes") or []
    if volumes:
        lasts = {v["name"]: v.get("last_success") for v in volumes}
    elif nas is not None and nas["backup"].get("status") == "ok" and nas["backup"].get("at"):
        lasts = {"backup": nas["backup"]["at"]}
    elif nas is not None:
        lasts = {"backup": None}
    else:
        return None
    problems = []
    for name, last in lasts.items():
        if last is None or now - datetime.fromisoformat(last) > limit:
            label = "the NAS" if name == "backup" else name
            when = (
                datetime.fromisoformat(last).strftime("%a %d %b %H:%M") if last else "none recorded"
            )
            problems.append(Problem(f"backup_missing:{name}", "backup_missing", "error",
                                    f"No successful backup of {label} in {settings['hours']} h",
                                    f"Last success: {when}"))
    return problems


def portfolio_move(
    portfolio: dict[str, Any] | None, settings: dict[str, Any], today: str
) -> list[Problem] | None:
    if portfolio is None:
        return None
    pct = portfolio["change"]["day_pct"]
    if abs(pct) < settings["threshold_pct"]:
        return []
    sign = "+" if pct > 0 else "−"
    value = f"{portfolio['total_value']:,.0f}".replace(",", ".")
    return [Problem(f"portfolio_move:{today}", "portfolio_move", "info",
                    f"Portfolio moved {sign}{abs(pct):.1f}% today".replace(".", ","),
                    f"Now € {value}")]


# --- evaluation ----------------------------------------------------------------------


def open_incidents(store: Store) -> dict[str, dict[str, Any]]:
    with store.connect() as conn:
        rows = conn.execute("SELECT * FROM alert_incident WHERE resolved_at IS NULL")
        return {r["key"]: dict(r) for r in rows}


def incidents(store: Store, limit: int = 50) -> list[dict[str, Any]]:
    with store.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alert_incident ORDER BY resolved_at IS NOT NULL, opened_at DESC "
            "LIMIT ?", (limit,))
        return [dict(r) for r in rows]


def _duration(since: str, now: datetime) -> str:
    minutes = int((now - datetime.fromisoformat(since)).total_seconds() // 60)
    return f"{minutes} min" if minutes < 60 else f"{minutes // 60} h {minutes % 60} min"


async def apply(
    store: Store, cfg: dict[str, Any], judged: dict[str, list[Problem] | None],
    now: datetime, telegram: Any = None,
) -> list[str]:
    """Open incidents for new problems and resolve the ones that are gone, for
    every rule that could judge (not None). Returns the keys that changed."""
    open_now = open_incidents(store)
    changed: list[str] = []
    for rule, problems in judged.items():
        if problems is None:
            continue
        active = {p.key: p for p in problems}
        for key, problem in active.items():
            if key in open_now:
                with store.connect() as conn:
                    conn.execute("UPDATE alert_incident SET last_seen_at = ? WHERE key = ?",
                                 (now.isoformat(), key))
                continue
            with store.connect() as conn:
                conn.execute(
                    "INSERT INTO alert_incident (key, rule, severity, title, body, opened_at, "
                    "last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET "
                    "severity = excluded.severity, title = excluded.title, body = excluded.body, "
                    "opened_at = excluded.opened_at, last_seen_at = excluded.last_seen_at, "
                    "resolved_at = NULL",
                    (key, rule, problem.severity, problem.title, problem.body,
                     now.isoformat(), now.isoformat()))
            category = "portfolio" if rule == "portfolio_move" else "rules"
            await core.notify(store, cfg, source=f"rule.{rule}", category=category,
                              severity=problem.severity, title=problem.title, body=problem.body,
                              now=now, telegram=telegram)
            changed.append(key)
        for key, incident in open_now.items():
            if incident["rule"] != rule or key in active:
                continue
            with store.connect() as conn:
                conn.execute("UPDATE alert_incident SET resolved_at = ? WHERE key = ?",
                             (now.isoformat(), key))
            if rule not in NO_RESOLVE:
                await core.notify(store, cfg, source=f"rule.{rule}", category="rules",
                                  severity="ok", title=f"Resolved: {incident['title']}",
                                  body=f"after {_duration(incident['opened_at'], now)}",
                                  now=now, telegram=telegram)
            changed.append(key)
    return changed


async def check(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                telegram: Any = None, dies: dict[str, int] | None = None) -> list[str]:
    """Run every enabled rule once. `dies` is for tests; normally it is read
    from Docker's event log for the restart window."""
    from ..sources import docker  # noqa: PLC0415 (keeps app.alerts light to import)

    now = now or datetime.now(UTC)
    settings = rule_settings(store)
    nas = _fresh(store.get_cache("nas"), now)
    containers = _fresh(store.get_cache("containers"), now)

    health = settings["container_health"]
    if dies is None and health["enabled"]:
        window = timedelta(minutes=health["restart_window_minutes"])
        dies = await docker.die_counts(cfg["nas"]["docker_socket"], now - window, now)
    pending = core.get_setting(store, "rule_pending", {})

    judged: dict[str, list[Problem] | None] = {
        "disk_space": disk_space(nas, settings["disk_space"]),
        "smart": smart(nas, settings["smart"]),
        "container_health": container_health(containers, store.list_services(), dies,
                                              pending, health, now),
        "backup_missing": backup_missing(_fresh(store.get_cache("backups"), now), nas,
                                         settings["backup_missing"], now),
        "portfolio_move": portfolio_move(_fresh(store.get_cache("portfolio"), now),
                                         settings["portfolio_move"],
                                         core.local(now, cfg).date().isoformat()),
    }
    core.put_setting(store, "rule_pending", pending)
    # A disabled rule judges nothing: its open incidents resolve quietly.
    for name, rule in settings.items():
        if not rule["enabled"]:
            judged[name] = []
            for key, incident in open_incidents(store).items():
                if incident["rule"] == name:
                    with store.connect() as conn:
                        conn.execute("UPDATE alert_incident SET resolved_at = ? WHERE key = ?",
                                     (now.isoformat(), key))
    enabled = {k: v for k, v in judged.items() if settings[k]["enabled"]}
    return await apply(store, cfg, enabled, now, telegram)
