"""The running overview (plan.md M28, step 3): the runs from Apple Health and Runna's plan put
together for the hub's Running page, its Home card and (step 4) the Now panel: the last run,
this week against the plan, the next session, the totals and the best efforts.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .sources import runna, runs, streets
from .store import Store

STREAK_RUNS = 3      # a week counts towards the streak with this many runs
MINI_POINTS = 40     # a run's route in miniature, above its day in the week
LAST_POINTS = 300


def _local_day(start: str, zone: ZoneInfo) -> date:
    return datetime.fromisoformat(start).astimezone(zone).date()


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def streak(days: list[date], today: date) -> int:
    """Weeks in a row with STREAK_RUNS runs or more, back from this week (or from last week
    while this one is still under way)."""
    per_week: dict[date, int] = {}
    for d in days:
        per_week[_monday(d)] = per_week.get(_monday(d), 0) + 1
    week = _monday(today)
    if per_week.get(week, 0) < STREAK_RUNS:
        week -= timedelta(days=7)
    count = 0
    while per_week.get(week, 0) >= STREAK_RUNS:
        count += 1
        week -= timedelta(days=7)
    return count


def bests(all_runs: list[dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    out: dict[str, dict[str, Any] | None] = {}
    for name in runs.BESTS:
        timed = [r for r in all_runs if r["bests"].get(name)]
        fastest = min(timed, key=lambda r: r["bests"][name], default=None)
        out[name] = ({"seconds": fastest["bests"][name], "start": fastest["start"],
                      "id": fastest["id"]} if fastest else None)
    with_distance = [r for r in all_runs if r["distance_m"]]
    longest = max(with_distance, key=lambda r: r["distance_m"], default=None)
    out["longest"] = ({"metres": longest["distance_m"], "start": longest["start"],
                       "id": longest["id"]} if longest else None)
    return out


def overview(store: Store, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    today = now.astimezone(zone).date()
    year_ago = (now - timedelta(days=400)).astimezone(UTC).isoformat()  # runs are kept in UTC
    all_runs = runs.since(store, year_ago)
    days = {r["id"]: _local_day(r["start"], zone) for r in all_runs}
    plan = store.get_cache(runna.CACHE_KEY) or {}
    planned = {d["date"]: d for d in plan.get("week") or []}

    monday = _monday(today)
    week = []
    for i in range(7):
        day = monday + timedelta(days=i)
        ran = [r for r in all_runs if days[r["id"]] == day]
        week.append({
            "date": day.isoformat(),
            "planned_m": (planned.get(day.isoformat()) or {}).get("planned_m") or 0,
            "sessions": (planned.get(day.isoformat()) or {}).get("sessions") or [],
            "done_m": sum(r["distance_m"] or 0 for r in ran),
            "routes": [one["route"] for r in reversed(ran)
                       if (one := runs.one(store, r["id"], MINI_POINTS)) and one["route"]],
            "runs": [r["id"] for r in reversed(ran)],
        })

    def total(first: date, last: date) -> float:
        return round(sum(r["distance_m"] or 0 for r in all_runs if first <= days[r["id"]] <= last))

    sessions = plan.get("sessions") or []
    ran_today = any(days[r["id"]] == today for r in all_runs)
    # Today's session is next until today's run is in.
    upcoming = [s for s in sessions if s["date"] > today.isoformat()
                or (s["date"] == today.isoformat() and not ran_today)]
    last = runs.one(store, all_runs[0]["id"], LAST_POINTS) if all_runs else None
    if last:
        ran_on = days[last["id"]].isoformat()
        last["session"] = next((s["name"] for s in sessions if s["date"] == ran_on), None)
    return {
        "as_of": now.isoformat(),
        "stale": bool(plan.get("stale")),
        "has_plan": bool(plan),
        "last": last,
        "week": week,
        "totals": {
            "week_m": total(monday, today),
            "week_planned_m": round(sum(d["planned_m"] for d in week)),
            "last4_m": total(today - timedelta(days=27), today),
            "prev4_m": total(today - timedelta(days=55), today - timedelta(days=28)),
            "streak_weeks": streak(list(days.values()), today),
            "runs_this_year": sum(1 for d in days.values() if d.year == today.year),
            "year_m": round(sum(r["distance_m"] or 0 for r in all_runs
                                if days[r["id"]].year == today.year)),
        },
        "bests": bests(all_runs),
        "next": upcoming[0] if upcoming else None,
        "today": {"ran": ran_today,
                  "session": next((s for s in sessions if s["date"] == today.isoformat()), None)},
        "race": plan.get("race"),
        # When the town's streets were fetched (step 5); None until asked for in Settings.
        "streets_at": streets.status(store)["fetched_at"],
    }
