from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ai, briefing, main, scheduler
from app.alerts import core, rules, templates
from app.alerts.telegram import Telegram

CFG = {
    "timezone": "Europe/Amsterdam",
    "ai": {"api_key": "sk-test"},
    "telegram": {"token": "t", "chats": {"nas": {"id": "-1", "label": "NAS"}}},
}
NOW = datetime(2026, 10, 29, 5, 30, tzinfo=UTC)  # Thursday 06:30 in Amsterdam
ANSWER = {
    "paragraph": "Good morning. A quiet night: the backup finished at 03:41 and Sonarr was "
                 "updated. Your train is on time from platform 4.",
    "line": "A quiet night. Train on time, dry until 16:00.",
    "facts": ["Backup done 03:41", "Sonarr updated", "Train on time, platform 4",
              "Stand-up 09:30", "A fifth fact that is cut"],
}


class FakeClaude:
    def __init__(self, answer=ANSWER):
        self.answer, self.calls = answer, []

    def __call__(self, api_key):
        return SimpleNamespace(messages=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = SimpleNamespace(input_tokens=1500, output_tokens=200,
                                cache_read_input_tokens=0, cache_creation_input_tokens=0)
        text = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return SimpleNamespace(stop_reason="end_turn", usage=usage,
                               content=[SimpleNamespace(type="text", text=text)])


class Sent:
    def __init__(self):
        self.texts = []

    def client(self):
        def handler(request):
            self.texts.append(json.loads(request.content)["text"])
            return httpx.Response(200, json={"ok": True, "result": {}})

        return Telegram("t", transport=httpx.MockTransport(handler))


@pytest.fixture
def house(store):
    """The cache as the hub has it at 06:30 on a weekday."""
    ai.ensure_tables(store)
    core.ensure_tables(store)
    rules.ensure_tables(store)
    ai.set_switches(store, {"briefing": True})
    store.put_cache("nas", {
        "backup": {"status": "ok", "at": "2026-10-29T02:41:00+00:00"},
        "storage": {"used_pct": 71.4, "pools": [{"name": "volume2", "used_pct": 93.2}]},
        "disks": [{"name": "sda", "smart": "ok"}]})
    store.add_container_update(NOW - timedelta(hours=3), "sonarr", "lscr.io/linuxserver/sonarr",
                               "sha256:a", "sha256:b")
    store.add_container_update(NOW - timedelta(days=2), "radarr", "x", "sha256:c", "sha256:d")
    store.put_cache("pinned", {"pins": [
        {"repo": "immich-app/immich", "container": "immich_server", "current": "v3.3.1",
         "latest": "v3.4.0", "behind": 2},
        {"repo": "louislam/uptime-kuma", "container": "uptime-kuma", "current": "2.2.1",
         "latest": None, "behind": 0}]})
    store.put_cache("weather", {"temperature": 8.4, "description": "Half bewolkt"})
    hours = [{"hour": 7, "temperature": 7, "rain_chance": 10},
             {"hour": 16, "temperature": 11, "rain_chance": 70}]
    store.put_cache("forecast", {"days": [{"date": "2026-10-29", "high": 12.2, "low": 6.6,
                                           "hours": hours}]})
    store.put_cache("train", {"date": "2026-10-29", "mode": "morning", "departure": "07:16",
                              "route": "Alpha to Beta",
                              "train": {"status": "on_time", "planned_track": "4",
                                        "actual_track": None, "delay_minutes": 0}})
    store.put_cache("calendar", {"date": "2026-10-29", "all_day": [], "events": [
        {"title": "Stand-up", "start": "2026-10-29T08:30:00+00:00"},
        {"title": "Dentist", "start": "2026-10-29T13:00:00+00:00"}]})
    store.put_cache("portfolio", {"total_value": 123456.78})
    return store


def test_the_facts_come_from_the_cache_and_only_the_first_event(house):
    lines = briefing.facts(CFG, house, NOW)

    assert lines == [
        "Backup to Hetzner: finished at 03:41",
        "Storage: 71% used",
        "Pool volume2 is 93% full",
        "Disks: all healthy",
        "Updated overnight: sonarr",
        "Pinned immich at v3.3.1, newest v3.4.0",
        "Now outside: 8 °C, Half bewolkt",
        "Today: 7 to 12 °C",
        "Rain likely from 16:00",
        "Train 07:16 to Beta: on time, platform 4",
        "First event: 09:30 Stand-up",
    ]
    assert not any("Dentist" in f or "123456" in f for f in lines)


def test_an_empty_house_still_gives_facts(store):
    rules.ensure_tables(store)

    assert briefing.facts(CFG, store, NOW) == ["Disks: all healthy"]


def test_asks_haiku_once_for_all_three_forms(house):
    claude = FakeClaude()

    made = asyncio.run(briefing.make(CFG, house, NOW, claude))

    assert made.line == "A quiet night. Train on time, dry until 16:00."
    assert made.facts == ["Backup done 03:41", "Sonarr updated", "Train on time, platform 4",
                          "Stand-up 09:30"]
    assert made.date == "2026-10-29"
    assert made.until == datetime(2026, 10, 29, 9, 0, tzinfo=made.until.tzinfo)
    call = claude.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": briefing.SCHEMA}
    assert call["messages"][0]["content"].startswith("Thursday 29 October 2026, 06:30.")
    assert "- Train 07:16 to Beta: on time, platform 4" in call["messages"][0]["content"]


def test_long_answers_are_cut_to_fit_the_panel(house):
    long = ANSWER | {"line": "x" * 200, "facts": ["y" * 80] * 4}

    made = asyncio.run(briefing.make(CFG, house, NOW, FakeClaude(long)))

    assert len(made.line) == briefing.LINE_MAX
    assert all(len(f) == briefing.FACT_MAX for f in made.facts)


def test_sends_it_in_quiet_hours_and_keeps_it_for_the_panel(house):
    sent = Sent()

    asyncio.run(briefing.run(CFG, house, NOW, FakeClaude(), sent.client()))

    assert sent.texts == [f"<b>Morning briefing · Thursday</b>\n{ANSWER['paragraph']}"]
    kept = house.get_cache(briefing.CACHE_KEY)
    assert kept["line"] == ANSWER["line"] and len(kept["facts"]) == 4


def test_switched_off_or_unreadable_it_sends_nothing(house):
    sent = Sent()
    ai.set_switches(house, {"briefing": False})
    assert asyncio.run(briefing.run(CFG, house, NOW, FakeClaude(), sent.client())) is None

    ai.set_switches(house, {"briefing": True})
    assert asyncio.run(briefing.run(CFG, house, NOW, FakeClaude("not json"), sent.client())) is None
    assert sent.texts == [] and house.get_cache(briefing.CACHE_KEY) is None


def test_scheduled_on_weekday_mornings(store):
    job = next(j for j in scheduler.build(CFG | {"nas": {"docker_socket": "/x"}}, store).get_jobs()
               if j.id == "briefing")

    assert str(job.trigger) == "cron[day_of_week='mon-fri', hour='6', minute='30']"


def test_write_one_now_from_settings(house, monkeypatch):
    main.app.state.store = house
    main.app.state.config = CFG
    client = TestClient(main.app)
    origin = {"Origin": "http://testserver"}

    ai.set_switches(house, {"briefing": False})
    assert client.post("/api/ai/briefing/now", json={}, headers=origin).status_code == 409
    assert client.get("/api/briefing").status_code == 503


NIGHT = datetime(2026, 10, 29, 1, 0, tzinfo=UTC)  # 02:00 in Amsterdam: quiet hours
SEVEN = datetime(2026, 10, 29, 6, 0, tzinfo=UTC)  # 07:00: the digest's turn


def hold(store, severity, title, chat=None):
    return asyncio.run(core.notify(store, CFG, source="test", category="rules",
                                   severity=severity, title=title, chat=chat, now=NIGHT))


def test_takes_over_what_quiet_hours_held(house):
    sent = Sent()
    hold(house, "ok", "NAS backup done")
    hold(house, "warning", "volume2 is 91% full")
    hold(house, "info", "3 images updated")
    hold(house, "ok", "Resolved: sonarr down")

    asyncio.run(briefing.run(CFG, house, NOW, FakeClaude(), sent.client()))

    assert sent.texts == [
        f"<b>Morning briefing · Thursday</b>\n{ANSWER['paragraph']}\n\n"
        "<b>Overnight · 1 warning, 1 info, 2 OK</b>\nWARNING · volume2 is 91% full"]
    # Nothing is left for "While you slept" at 07:00.
    assert core.held(house) == []
    assert asyncio.run(core.send_digests(house, CFG, SEVEN, sent.client())) == 0
    assert len(sent.texts) == 1


def test_a_quiet_night_adds_no_overnight_section(house):
    sent = Sent()

    asyncio.run(briefing.run(CFG, house, NOW, FakeClaude(), sent.client()))

    assert sent.texts == [f"<b>Morning briefing · Thursday</b>\n{ANSWER['paragraph']}"]


def test_another_chat_keeps_its_own_digest(house):
    cfg = CFG | {"telegram": {"token": "t", "chats": {"nas": {"id": "-1"},
                                                      "portfolio": {"id": "-2"}}}}
    hold(house, "info", "Portfolio moved 3%", chat="portfolio")
    sent = Sent()

    asyncio.run(briefing.run(cfg, house, NOW, FakeClaude(), sent.client()))

    assert [m["title"] for m in core.held(house)] == ["Portfolio moved 3%"]
    assert asyncio.run(core.send_digests(house, cfg, SEVEN, sent.client())) == 1


def test_a_briefing_that_fails_to_send_leaves_the_digest(house):
    hold(house, "warning", "volume2 is 91% full")

    def refuse(request):
        return httpx.Response(500, json={"ok": False})

    asyncio.run(briefing.run(CFG, house, NOW, FakeClaude(),
                             Telegram("t", transport=httpx.MockTransport(refuse))))

    assert [m["title"] for m in core.held(house)] == ["volume2 is 91% full"]


def test_a_template_without_overnight_leaves_the_digest(house):
    templates.save(house, "briefing", "<b>Briefing {day}</b>\n{paragraph}")
    hold(house, "warning", "volume2 is 91% full")
    sent = Sent()

    asyncio.run(briefing.run(CFG, house, NOW, FakeClaude(), sent.client()))

    assert sent.texts == [f"<b>Briefing Thursday</b>\n{ANSWER['paragraph']}"]
    assert len(core.held(house)) == 1


def test_many_warnings_are_cut_with_a_note():
    held = [{"severity": "warning", "title": f"w{i}"} for i in range(core.DIGEST_LIMIT + 2)]

    values = briefing.overnight(held)

    assert values["overnight"] == (f"Overnight · {core.DIGEST_LIMIT + 2} warnings "
                                   f"(the first {core.DIGEST_LIMIT} here, all on the Alerts page)")
    assert len(values["held"]) == core.DIGEST_LIMIT
