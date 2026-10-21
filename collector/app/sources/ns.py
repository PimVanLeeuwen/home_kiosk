"""The owner's weekday morning train, from NS's travel information API.

Every weekday from the watch window's start until the train has left: the
direct trip at the configured time (delay, track, cancellation, stops), the
next direct train when it does not run, and disruptions on the stretch it
travels. The evening before (20:00 and 22:00 by default) the same for
tomorrow's train, so a cancellation is known in time to set an earlier alarm.
Three read-only calls with the key from the NS API portal (product Ns-App):
`trips` for the train, `journey` once a day for every station it passes, and
`disruptions`. Outside those times no call is made.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from ..models import Train, TrainDisruption, TrainRun, TrainStop
from ..store import Store

log = logging.getLogger(__name__)

API = "https://gateway.apiportal.ns.nl/reisinformatie-api/api"
CACHE_KEY = "train"
# Disruption kinds that change how trains run; calamities (a bus strike) and
# the like have no stretch to match.
KINDS = {"DISRUPTION", "MAINTENANCE"}
# A cancelled train with no direct replacement in sight stops being followed
# this long after its planned departure.
GIVE_UP = timedelta(hours=2)
# The evening checks (for tomorrow's train) stop here, before quiet hours.
EVENING_END = time(23, 0)


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    train = cfg.get("train") or {}
    return {
        "enabled": bool(train.get("api_key") and train.get("from") and train.get("to")),
        "api_key": train.get("api_key") or "",
        "from": train.get("from", ""),
        "to": train.get("to", ""),
        "departure": _hm(train.get("departure", "07:16")),
        "watch_from": _hm(train.get("watch_from", "06:00")),
        "evening": sorted(_hm(t) for t in train.get("evening", ["20:00", "22:00"])),
        "timezone": ZoneInfo(cfg.get("timezone", "Europe/Amsterdam")),
    }


def _hm(value: str) -> time:
    hour, minute = (int(part) for part in str(value).split(":"))
    return time(hour, minute)


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _minutes(late: timedelta) -> int:
    return max(0, int(late.total_seconds() // 60))


def parse_run(trip: dict[str, Any]) -> TrainRun:
    """A direct trip (one leg) as the card and the rule see it."""
    leg = (trip.get("legs") or [{}])[0]
    origin = leg.get("origin") or {}
    planned = _when(origin.get("plannedDateTime"))
    actual = _when(origin.get("actualDateTime"))
    if planned is None:
        raise ValueError("trip without a planned departure")
    stops = []
    for stop in leg.get("stops") or []:
        if stop.get("passing"):
            continue
        stops.append(TrainStop(
            name=stop.get("name") or "",
            planned=_when(stop.get("plannedDepartureDateTime")
                          or stop.get("plannedArrivalDateTime")) or planned,
            actual=_when(stop.get("actualDepartureDateTime") or stop.get("actualArrivalDateTime")),
            track=(stop.get("actualDepartureTrack") or stop.get("actualArrivalTrack")
                   or stop.get("plannedDepartureTrack") or stop.get("plannedArrivalTrack")),
            cancelled=bool(stop.get("cancelled")),
        ))
    cancelled = (bool(leg.get("cancelled")) or trip.get("status") == "CANCELLED"
                 or bool(stops and stops[0].cancelled))
    delay = _minutes(actual - planned) if actual else 0
    return TrainRun(
        name=leg.get("name") or "",
        status="cancelled" if cancelled else "late" if delay >= 1 else "on_time",
        planned_departure=planned,
        actual_departure=actual,
        delay_minutes=delay,
        planned_track=origin.get("plannedTrack"),
        actual_track=origin.get("actualTrack") or origin.get("plannedTrack"),
        stops=stops,
    )


def _direct(trips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in trips if t.get("transfers") == 0 and len(t.get("legs") or []) == 1]


def find_train(trips: list[dict[str, Any]], departure: datetime) -> TrainRun | None:
    """The direct trip planned to leave at `departure` (local, aware)."""
    for trip in _direct(trips):
        run = parse_run(trip)
        if run.planned_departure == departure:
            return run
    return None


def next_direct(trips: list[dict[str, Any]], after: datetime) -> TrainRun | None:
    """The first direct train planned after `after` that runs."""
    runs = sorted((parse_run(t) for t in _direct(trips)), key=lambda r: r.planned_departure)
    return next((r for r in runs if r.planned_departure > after and r.status != "cancelled"),
                None)


def parse_route(journey: dict[str, Any], from_name: str, to_name: str) -> list[str]:
    """UIC codes of every station from the first to the last stop of the route,
    passing ones included, from the journey details."""
    stops = (journey.get("payload") or {}).get("stops") or []
    codes, inside = [], False
    for stop in stops:
        station = stop.get("stop") or {}
        if station.get("name") == from_name:
            inside = True
        if inside and station.get("uicCode"):
            codes.append(str(station["uicCode"]))
        if inside and station.get("name") == to_name:
            break
    return codes


def _covers(item: dict[str, Any], at: datetime) -> bool:
    """Whether one of the disruption's time spans includes `at` (an open end counts)."""
    for span in item.get("timespans") or []:
        start, end = _when(span.get("start")), _when(span.get("end"))
        if (start is None or start <= at) and (end is None or at <= end):
            return True
    return False


def _title(title: str) -> str:
    """NS's title without repeats: works on several stretches can name one twice
    ("Utrecht - Arnhem; Utrecht - Rhenen.; Utrecht - Arnhem.")."""
    parts = list(dict.fromkeys(p.strip().rstrip(".").strip() for p in title.split(";")))
    parts = [p for p in parts if p]
    return "; ".join(parts) + ("." if parts and title.rstrip().endswith(".") else "")


def route_disruptions(items: list[dict[str, Any]], route: list[str],
                      at: datetime | None = None) -> list[TrainDisruption]:
    """Disruptions whose stretch covers at least two stations of the route: one
    shared station (a works from Utrecht to Leiden) is another line. Without
    `at` only active ones count; with it, those whose time spans include `at`
    (tomorrow's departure, for the evening check)."""
    wanted = set(route)
    found = []
    for item in items:
        if item.get("type") not in KINDS:
            continue
        if not (_covers(item, at) if at else item.get("isActive")):
            continue
        sections = item.get("publicationSections") or []
        if not any(len(wanted & {str(s.get("uicCode")) for s in
                                 (p.get("section") or {}).get("stations") or []}) >= 2
                   for p in sections):
            continue
        span = (item.get("timespans") or [{}])[0]
        text = ((span.get("situation") or {}).get("label")
                or ((sections[0].get("consequence") or {}).get("description") if sections else "")
                or "")
        found.append(TrainDisruption(
            id=str(item.get("id", "")),
            kind=item["type"],
            title=_title(item.get("title") or ""),
            text=text,
            until=(item.get("expectedDuration") or {}).get("description"),
        ))
    return found


def _gone(run: TrainRun | None, now: datetime) -> bool:
    if run is None:
        return False
    return now >= (run.actual_departure or run.planned_departure)


def has_problem(train: Train) -> bool:
    """Something worth knowing the evening before: it does not run (or not all
    the way), or works or a disruption on the route."""
    run = train.train
    return (run is None or run.status in ("cancelled", "not_found")
            or any(stop.cancelled for stop in run.stops) or bool(train.disruptions))


async def _get(client: httpx.AsyncClient, path: str, **params: str) -> Any:
    resp = await client.get(path, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _plan(s: dict[str, Any], local: datetime) -> tuple[str, Any]:
    """Which train to follow now: this morning's, tomorrow's (the evening
    before), or none, with the date of that train."""
    today = local.date()
    morning_end = (datetime.combine(today, s["departure"]) + GIVE_UP).time()
    if local.weekday() < 5 and s["watch_from"] <= local.time() < morning_end:
        return "morning", today
    tomorrow = today + timedelta(days=1)
    if tomorrow.weekday() < 5 and s["evening"] and s["evening"][0] <= local.time() < EVENING_END:
        return "evening", tomorrow
    return "idle", today


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  transport: httpx.AsyncBaseTransport | None = None) -> Train:
    """Raises when NS's trips cannot be read, so the last good answer stays
    cached, flagged stale. NS is only called while there is a train to follow:
    every run in the morning, at each evening check time in the evening."""
    s = settings(cfg)
    now = now or datetime.now(UTC)
    local = now.astimezone(s["timezone"])
    mode, day = _plan(s, local)
    departure = datetime.combine(day, s["departure"], s["timezone"])
    previous = store.get_cache(CACHE_KEY)
    if previous and previous.get("date") != day.isoformat():
        previous = None
    route = (previous or {}).get("route") or f"{s['from']} to {s['to']}"
    hhmm = s["departure"].strftime("%H:%M")

    if mode == "idle":
        return Train(as_of=now, date=day.isoformat(), route=route, departure=hhmm, mode="idle",
                     watching=False, departed=False, train=None)
    if previous and previous.get("mode") == mode:
        if mode == "morning" and previous.get("departed"):
            return Train.model_validate(previous | {"as_of": now.isoformat()})
        if mode == "evening":
            due = max(t for t in s["evening"] if t <= local.time())
            checked = _when(previous.get("checked_at"))
            if checked and checked.astimezone(s["timezone"]).time() >= due:
                return Train.model_validate(previous | {"as_of": now.isoformat()})

    async with httpx.AsyncClient(base_url=API, transport=transport,
                                 headers={"Ocp-Apim-Subscription-Key": s["api_key"]}) as client:
        since = (departure - timedelta(minutes=1)).isoformat()
        answer = await _get(client, "/v3/trips", fromStation=s["from"], toStation=s["to"],
                            dateTime=since)
        trips = answer.get("trips") or []
        run = find_train(trips, departure)
        if run is None and previous and previous.get("train"):
            # The planner dropped it: most likely cancelled.
            run = TrainRun.model_validate(previous["train"]).model_copy(
                update={"status": "not_found"})
        replacement = (next_direct(trips, departure)
                       if run is None or run.status in ("cancelled", "not_found") else None)

        origin = run.stops[0].name if run and run.stops else ""
        destination = run.stops[-1].name if run and run.stops else ""
        if origin and destination:
            route = f"{origin} to {destination}"

        codes = (previous or {}).get("route_codes") or []
        if not codes and run and run.status != "not_found":
            try:
                number = "".join(ch for ch in run.name if ch.isdigit())
                journey = await _get(client, "/v2/journey", train=number,
                                     dateTime=run.planned_departure.isoformat())
                codes = parse_route(journey, origin, destination)
            except Exception as exc:
                log.warning("ns journey unreadable: %s", type(exc).__name__)

        disruptions = [TrainDisruption.model_validate(d)
                       for d in (previous or {}).get("disruptions") or []]
        if codes:
            try:
                if mode == "evening":
                    # All of them, planned ones included; keep those covering the departure.
                    items = await _get(client, "/v3/disruptions")
                    at = departure
                else:
                    items = await _get(client, "/v3/disruptions", isActive="true")
                    at = None
                disruptions = route_disruptions(items if isinstance(items, list) else [],
                                                codes, at)
            except Exception as exc:
                log.warning("ns disruptions unreadable: %s", type(exc).__name__)

    train = Train(as_of=now, date=day.isoformat(), route=route, departure=hhmm, mode=mode,
                  watching=False,
                  departed=False, train=run, next_direct=replacement,
                  disruptions=disruptions, route_codes=codes, checked_at=now)
    if mode == "evening":
        return train.model_copy(update={"watching": has_problem(train)})
    followed = replacement if run is None or run.status in ("cancelled", "not_found") else run
    departed = _gone(followed, now) or now >= departure + GIVE_UP
    return train.model_copy(update={"watching": not departed, "departed": departed})
