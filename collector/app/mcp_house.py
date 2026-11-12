"""What each MCP house tool returns (plan.md M33): the hub's own payloads, trimmed.

Every answer goes into a prompt at Anthropic, so each keeps only what answers a question
about the house: no ids, colours, poster or picture paths, chart history, chat ids or
message HTML. The cached payload is never changed; each summary builds a new dict.
"""

from __future__ import annotations

from typing import Any

Payload = dict[str, Any]


def missing(what: str) -> Payload:
    return {"available": False, "reason": f"The hub has no {what} data yet (just started?)."}


def _envelope(payload: Payload) -> Payload:
    return {"as_of": payload.get("as_of"), "stale": payload.get("stale", False)}


def _pick(item: Payload, *keys: str) -> Payload:
    return {k: item.get(k) for k in keys}


# --- train, backups, NAS ----------------------------------------------------------------


def _run(run: Payload | None, with_stops: bool) -> Payload | None:
    if not run:
        return None
    out = {
        **_pick(run, "name", "status", "planned_departure", "actual_departure"),
        "delay_minutes": run.get("delay_minutes", 0),
        "track": run.get("actual_track") or run.get("planned_track"),
    }
    if with_stops:
        out["stops"] = [stop.get("name") for stop in run.get("stops") or []]
    return out


def train(payload: Payload | None) -> Payload:
    """The weekday train as the Home card knows it; the stops by name only."""
    if payload is None:
        return missing("train")
    return {
        **_envelope(payload),
        **_pick(payload, "date", "route", "departure", "mode", "watching", "departed"),
        "train": _run(payload.get("train"), with_stops=True),
        "next_direct": _run(payload.get("next_direct"), with_stops=False),
    }


def backups(payload: Payload | None) -> Payload:
    """Per volume the last run and last success, the storage box's room and the next run."""
    if payload is None:
        return missing("backup")
    volumes = []
    for summary in payload.get("volumes") or []:
        run = summary.get("last_run") or {}
        mine = next((v for v in run.get("volumes") or [] if v.get("name") == summary.get("name")),
                    {})
        volumes.append({
            "name": summary.get("name"),
            "last_run_finished": run.get("finished"),
            "last_run_ok": mine.get("ok"),
            "last_run_errors": mine.get("errors"),
            "last_error": mine.get("last_error"),
            "last_success": summary.get("last_success"),
        })
    box = payload.get("storage_box")
    return {
        **_envelope(payload),
        "next_due": payload.get("next_due"),
        "volumes": volumes,
        "storage_box": box and {
            "used_pct": box.get("used_pct"),
            "free_bytes": box.get("free"),
            "months_until_full": box.get("projection_months"),
        },
    }


def nas(payload: Payload | None) -> Payload:
    """The NAS's health now: load, temperatures, storage, disks, containers; no history."""
    if payload is None:
        return missing("NAS")
    out = dict(payload)
    network = out.get("network")
    if isinstance(network, dict):
        out["network"] = {k: v for k, v in network.items() if k != "history"}
    return out


# --- the day: calendar, weather, air, laundry, reminders ----------------------------------


def _event(event: Any) -> Payload:
    event = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
    return _pick(event, "title", "start", "end", "all_day")


def _day(day: Payload) -> Payload:
    return {"date": day.get("date"),
            "all_day": [_event(e) for e in day.get("all_day") or []],
            "events": [_event(e) for e in day.get("events") or []]}


def calendar(payload: Payload | None, count: int = 2) -> Payload:
    """Today and tomorrow from the cache, the shown calendars' events: title and times only
    (no calendar names, attendees, places or notes; the hub does not keep those)."""
    if payload is None:
        return missing("calendar")
    found = [_day(payload), _day(payload.get("tomorrow") or {})]
    return {
        **_envelope(payload),
        "days": [d for d in found if d["date"]][:count],
        "unread_calendars": len(payload.get("errors") or {}),
    }


def calendar_days(answer: Payload) -> Payload:
    """Any range of days, read from the calendars on the spot (agenda.days)."""
    return {
        "as_of": answer.get("as_of"),
        "stale": False,
        "days": [_day(d) for d in answer.get("days") or []],
        "unread_calendars": len(answer.get("errors") or {}),
    }


def weather(payload: Payload | None) -> Payload:
    """The weather now and the rain over the next two hours (5-minute steps)."""
    if payload is None:
        return missing("weather")
    return {
        **_envelope(payload),
        **_pick(payload, "measured_at", "description", "temperature", "feel_temperature",
                "wind_bft", "wind_direction", "humidity", "rain_last_hour", "sunrise",
                "sunset"),
        "rain": payload.get("rain") or [],
    }


def forecast(payload: Payload | None, day: str | None = None) -> Payload:
    """The week ahead by the hour (Open-Meteo): per day the high, low, sky, chance of rain and
    expected rain, and per hour the temperature, chance of rain and expected rain."""
    if payload is None:
        return missing("forecast")
    days = [d for d in payload.get("days") or [] if day is None or d.get("date") == day]
    return {
        **_envelope(payload),
        "days": [
            {**_pick(d, "date", "high", "low", "code", "rain_max", "rain_mm", "sunrise",
                     "sunset"),
             "hours": [_pick(h, "hour", "temperature", "rain_chance", "rain_mm")
                       for h in d.get("hours") or []]}
            for d in days
        ],
        "known_days": [d.get("date") for d in payload.get("days") or []],
    }


def air(payload: Payload | None) -> Payload:
    """The living room's air now; no history."""
    if payload is None:
        return missing("air")
    return {k: v for k, v in payload.items() if k != "history"}


def laundry(payload: Payload | None) -> Payload:
    """The washer and dryer: state, program, time left, done."""
    if payload is None:
        return missing("laundry")
    return {
        **_envelope(payload),
        "machines": [
            _pick(m, "name", "kind", "state", "online", "program", "remaining_minutes",
                  "ready_at", "done_at", "door_open", "error")
            for m in payload.get("machines") or []
        ],
    }


def reminders(overview: Payload, days: list[tuple[str, list[Payload]]]) -> Payload:
    """Each asked day's reminders with their ticks, and every reminder's next day."""
    return {
        "today": overview.get("today"),
        "days": [{"date": day, "reminders": [_pick(r, "title", "at", "done") for r in found]}
                 for day, found in days],
        "reminders": [
            {**_pick(r, "title", "next", "at"), "repeats": (r.get("repeat") or {}).get("kind")}
            for r in overview.get("reminders") or []
        ],
    }


# --- the house's machinery: Docker, media, services, sites, outside, alerts -----------------


def docker(payload: Payload | None) -> Payload:
    """Every container's state and load; memory in MB."""
    if payload is None:
        return missing("Docker")

    def mb(value: Any) -> float | None:
        return round(value / 1_000_000, 1) if isinstance(value, int | float) else None

    return {
        **_envelope(payload),
        "cpu_pct": payload.get("cpu_pct"),
        "mem_mb": mb(payload.get("mem_bytes")),
        "containers": [
            {**_pick(c, "name", "project", "image", "state", "health", "status", "cpu_pct"),
             "mem_mb": mb(c.get("mem_bytes"))}
            for c in payload.get("containers") or []
        ],
    }


def _episode(item: Payload) -> Payload:
    return _pick(item, "series", "season", "episode", "title", "air_date")


def media(payload: Payload | None) -> Payload:
    """Downloads with progress, aired episodes that are missing, and the week ahead."""
    if payload is None:
        return missing("media")
    return {
        **_envelope(payload),
        "downloads": [
            _pick(d, "kind", "title", "detail", "progress_pct", "time_left_seconds", "client",
                  "state", "message")
            for d in payload.get("downloads") or []
        ],
        "missing": [_episode(e) for e in payload.get("missing") or []],
        "missing_total": payload.get("missing_total", 0),
        "upcoming": [_episode(e) for e in payload.get("upcoming") or []],
        "unread_sources": sorted((payload.get("errors") or {}).keys()),
    }


def services(catalog: Payload) -> Payload:
    """Every app in the catalog by group: up or not, and its live figures."""
    return {
        **_envelope(catalog),
        "groups": [
            {
                "name": group.get("name"),
                "services": [
                    {**_pick(s, "name", "description", "status", "container", "port",
                             "path", "url"),
                     "stats": [_pick(x, "label", "value", "unit") for x in s.get("stats") or []]}
                    for s in group.get("services") or []
                ],
            }
            for group in catalog.get("groups") or []
        ],
    }


def sites(payload: Payload | None) -> Payload:
    """The owner's websites: up now, since when down, ping and 30-day uptime."""
    if payload is None:
        return missing("websites")
    return {
        **_envelope(payload),
        "sites": [_pick(s, "name", "group", "up", "down_since", "ping_ms", "uptime_pct")
                  for s in payload.get("sites") or []],
    }


def outside(payload: Payload | None) -> Payload:
    """The outside services the house depends on, with any open incident's latest word."""
    if payload is None:
        return missing("outside services")

    def incident(i: Payload) -> Payload:
        updates = i.get("updates") or []
        return {**_pick(i, "title", "impact", "status", "started_at"),
                "latest": updates[-1].get("text") if updates else None}

    return {
        **_envelope(payload),
        "services": [
            {**_pick(s, "name", "state", "stale"),
             "incidents": [incident(i) for i in s.get("incidents") or []]}
            for s in payload.get("services") or []
        ],
    }


def alerts(messages: list[Any], incidents: list[Payload]) -> Payload:
    """The newest messages the hub sent, and the alert rules' open incidents."""

    def message(m: Any) -> Payload:
        m = m.model_dump(mode="json") if hasattr(m, "model_dump") else m
        return _pick(m, "id", "ts", "category", "severity", "title", "body", "status",
                     "channel")

    return {
        "messages": [message(m) for m in messages],
        "open_incidents": [
            _pick(i, "rule", "severity", "title", "body", "opened_at", "last_seen_at")
            for i in incidents
            if not i.get("resolved_at") and not i.get("dismissed_at")
        ],
    }
