"""The Now panel's train screen (plan.md M20): the hub's train card (web
TrainCard, lib/train.ts) as ready-to-draw values. It shows when Home shows the
card: this weekday morning's train until it has left, and tomorrow's the
evening before only when it has a problem.

The minutes to go change every minute, so the screen carries the moment the
followed train leaves (`leaves_at`, seconds since 1970) and the panel counts
down on its own clock, as the day view's now line does.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .models import Train, TrainRun
from .panel_text import latin1
from .sources import ns
from .store import Store

MAX_STOPS = 6

def _hm(at: datetime | None, zone: ZoneInfo) -> str:
    return at.astimezone(zone).strftime("%H:%M") if at else ""


def shows(train: Train, local: datetime) -> bool:
    """As trainShows in web/src/lib/train.ts: a payload for another day never shows."""
    if not train.watching or train.mode == "idle":
        return False
    day = local.date() + (timedelta(days=1) if train.mode == "evening" else timedelta())
    return train.date == day.isoformat()


def status(train: Train) -> tuple[str, str]:
    """The large line and its tone (up, warn, down), worded as on Home."""
    run = train.train
    if run is None or run.status == "not_found":
        return "Not in NS's planner", "down"
    if run.status == "cancelled":
        return "Cancelled", "down"
    skipped = [s.name for s in run.stops[1:] if s.cancelled]
    if train.mode == "evening":
        return (f"Skips {', '.join(skipped)}" if skipped else "Works on the route"), "warn"
    if run.status == "late":
        return f"{run.delay_minutes} min late", "warn"
    if skipped:
        return f"Skips {', '.join(skipped)}", "warn"
    return "On time", "up"


def _platform(run: TrainRun) -> dict[str, Any]:
    track = run.actual_track or run.planned_track or "?"
    changed = bool(run.planned_track and run.actual_track and run.planned_track != run.actual_track)
    return {"platform": track, "platform_was": run.planned_track if changed else None}


def train_screen(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    cached = store.get_cache(ns.CACHE_KEY)
    local = now.astimezone(zone)
    if not cached:
        return {"kind": "train", "stale": False, "present": False}
    train = Train.model_validate(cached)
    if not shows(train, local):
        return {"kind": "train", "stale": False, "present": False}

    run = train.train
    evening = train.mode == "evening"
    word, tone = status(train)
    gone = run is None or run.status in ("cancelled", "not_found")
    followed = train.next_direct if gone else run
    destination = (run.stops[-1].name if run and run.stops
                   else train.route.split(" to ")[-1])
    late = bool(run and run.status == "late" and run.actual_departure)

    screen: dict[str, Any] = {
        "kind": "train", "stale": train.stale, "present": True,
        "title": "Tomorrow's train · direct" if evening else "Your train · direct",
        "departure": train.departure,
        # Late: the planned time struck through beside the new one.
        "departure_now": _hm(run.actual_departure, zone) if late and run else None,
        "gone": gone, "status": word, "tone": tone,
        # The line under the status; "" when the panel words it from leaves_at.
        "sub": "", "platform": None, "platform_was": None,
        "leaves_at": None, "ring_label": "min to next" if gone else "min to go",
        "stops": [], "next": None, "notice": None,
    }
    if gone:
        screen["sub"] = (f"The {train.departure} to {destination} does not run"
                         + (" tomorrow" if evening else ""))
    else:
        screen |= _platform(run)
        if evening:
            screen["sub"] = f"Tomorrow at {train.departure} from platform"
    if followed and not evening:
        leaves = followed.actual_departure or followed.planned_departure
        screen["leaves_at"] = round(leaves.timestamp())
    if run:
        screen["stops"] = [
            {"time": _hm(s.actual or s.planned, zone), "name": latin1(s.name),
             "shifted": bool(not gone and s.actual and s.actual != s.planned),
             "cancelled": s.cancelled}
            for s in run.stops[:MAX_STOPS]]
    if gone and train.next_direct:
        nxt = train.next_direct
        last = nxt.stops[-1] if nxt.stops else None
        screen["next"] = {"departure": _hm(nxt.planned_departure, zone),
                          "platform": nxt.actual_track or nxt.planned_track or "?",
                          "arrives": _hm((last.actual or last.planned) if last else None, zone)}
    if train.disruptions:
        d = train.disruptions[0]
        screen["notice"] = {"title": latin1(d.title),
                            "text": latin1(" ".join(x for x in (d.text, d.until) if x) + " (NS)")}
    return screen
