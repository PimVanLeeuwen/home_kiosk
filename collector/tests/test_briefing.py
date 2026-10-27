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
    "opening": "Your train is on time from platform 4; rain from 16:00, so take a coat.",
    "line": "A quiet night. Train on time, dry until 16:00.",
    "facts": ["Backup done 03:41", "Sonarr updated", "Train on time, platform 4",
              "Stand-up 09:30", "A fifth fact that is cut"],
}

# The message for the `house` fixture, without an overnight section.
MESSAGE = (
    f"<b>Morning briefing · Thursday</b>\n{ANSWER['opening']}\n\n"
    "<b>Your day</b>\n"
    "<i>Train</i> · 07:16 to Beta, on time, platform 4\n"
    "<i>09:30</i> · Stand-up\n"
    "<i>14:00</i> · Dentist\n"
    "<i>Weather</i> · 8 °C now, Half bewolkt; 7 to 12 °C today; rain likely from 16:00\n\n"
    "<b>Markets · last session</b>\n"
    "<i>Portfolio</i> · € 9.119, +€ 31,00 (+0,34%)\n"
    "<i>Best</i> · NVDA +2,10% (+€ 30,10)\n"
    "<i>Worst</i> · VWRL −0,40% (−€ 4,10)\n"
    "<i>Indices</i> · S&amp;P 500 +0,52%, AEX +0,31%\n"
    "<blockquote expandable><b>NVDA</b> +2,10% · +€ 30,10\n"
    "<b>ASML</b> +0,50% · +€ 5,00\n"
    "<b>VWRL</b> −0,40% · −€ 4,10</blockquote>\n\n"
    "<b>House</b>\n"
    "<i>Backup</i> · finished at 03:41\n"
    "<i>Storage</i> · 71% used; volume2 is 93% full\n"
    "<i>Disks</i> · all healthy\n"
    "<i>Updated</i> · sonarr\n"
    "<i>Pinned</i> · immich at v3.3.1, newest v3.4.0")


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
    store.put_cache("portfolio", {
        "as_of": "2026-10-29T05:15:00+00:00", "total_value": 9119.0, "holdings": [
            {"symbol": "NVDA", "day_pct": 2.1, "day_abs": 30.1},
            {"symbol": "VWRL", "day_pct": -0.4, "day_abs": -4.1},
            {"symbol": "ASML", "day_pct": 0.5, "day_abs": 5.0}]})
    store.put_cache("indices", {"indices": [{"label": "S&P 500", "day_pct": 0.52},
                                            {"label": "AEX", "day_pct": 0.31}]})
    return store


def test_the_facts_come_from_the_cache_and_only_the_first_event(house):
    lines = briefing.facts(CFG, house, NOW)

    assert lines == [
        "Train: 07:16 to Beta, on time, platform 4",
        "First event: 09:30 Stand-up",
        "Weather: 8 °C now, Half bewolkt; 7 to 12 °C today; rain likely from 16:00",
        "Backup: finished at 03:41",
        "Storage: 71% used; volume2 is 93% full",
        "Disks: all healthy",
        "Updated: sonarr",
        "Pinned: immich at v3.3.1, newest v3.4.0",
    ]
    assert not any("Dentist" in f or "9.119" in f or "NVDA" in f for f in lines)


def test_the_message_has_the_whole_agenda(house):
    assert briefing.your_day(CFG, house, NOW)[1:3] == [("09:30", "Stand-up"),
                                                       ("14:00", "Dentist")]


def test_an_empty_house_still_gives_facts(store):
    rules.ensure_tables(store)

    assert briefing.facts(CFG, store, NOW) == ["Disks: all healthy"]


def open_incident(store, key, rule, severity, title):
    with store.connect() as conn:
        conn.execute("INSERT INTO alert_incident (key, rule, severity, title, opened_at, "
                     "last_seen_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (key, rule, severity, title, NOW.isoformat(), NOW.isoformat()))


def test_open_alerts_lead_the_house_but_train_alerts_stay_out(house):
    open_incident(house, "train:x", "train", "warning", "Tomorrow, on your route: A - B; C - D")
    open_incident(house, "outside:transip", "outside", "warning", "TransIP: incident")

    assert briefing.house(CFG, house, NOW)[0] == ("WARNING", "TransIP: incident")
    assert not any("Tomorrow" in f for f in briefing.facts(CFG, house, NOW))


def test_works_on_the_route_in_ns_words(house):
    train = house.get_cache("train")
    house.put_cache("train", train | {"disruptions": [{
        "id": "1", "kind": "MAINTENANCE", "title": "Utrecht - Arnhem; Amsterdam - Köln.",
        "text": "Door werkzaamheden rijden er minder treinen.",
        "until": "Dit duurt tot ongeveer 10:00 uur."}]})

    assert briefing.your_day(CFG, house, NOW)[1] == (
        "Works", "on your route: Door werkzaamheden rijden er minder treinen. "
                 "Dit duurt tot ongeveer 10:00 uur.")


def test_a_late_or_moved_train(house):
    train = house.get_cache("train")
    house.put_cache("train", train | {"train": {
        "status": "late", "delay_minutes": 6, "actual_departure": "2026-10-29T06:22:00+00:00",
        "planned_track": "4", "actual_track": "6",
        "stops": [{"name": "Alpha"}, {"name": "Gamma", "cancelled": True}]}})

    assert briefing.your_day(CFG, house, NOW)[:2] == [
        ("Train", "07:16 to Beta, 6 min late, leaves 07:22, platform 6 (not 4)"),
        ("Skips", "Gamma")]


def test_a_cancelled_train_names_the_next_one(house):
    train = house.get_cache("train")
    house.put_cache("train", train | {"train": {"status": "cancelled"}, "next_direct": {
        "planned_departure": "2026-10-29T07:46:00+01:00", "planned_track": "6", "stops": []}})

    assert briefing.your_day(CFG, house, NOW)[:2] == [
        ("Train", "07:16 to Beta is CANCELLED"),
        ("Instead", "Next direct train: 07:46 from platform 6")]


def test_an_evening_check_is_not_this_morning(house):
    house.put_cache("train", house.get_cache("train") | {"mode": "evening"})

    assert briefing.your_day(CFG, house, NOW)[0] == ("09:30", "Stand-up")


def test_asks_sonnet_once_for_all_three_forms(house):
    claude = FakeClaude()

    made = asyncio.run(briefing.make(CFG, house, NOW, claude))

    assert made.line == "A quiet night. Train on time, dry until 16:00."
    assert made.facts == ["Backup done 03:41", "Sonarr updated", "Train on time, platform 4",
                          "Stand-up 09:30"]
    assert made.date == "2026-10-29"
    assert made.until == datetime(2026, 10, 29, 9, 0, tzinfo=made.until.tzinfo)
    call = claude.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": briefing.SCHEMA}
    assert call["messages"][0]["content"].startswith("Thursday 29 October 2026, 06:30.")
    assert "- Train: 07:16 to Beta, on time, platform 4" in call["messages"][0]["content"]
    # Markets are the hub's own: no amounts or tickers go to Claude.
    assert "9.119" not in call["messages"][0]["content"]
    assert "NVDA" not in call["messages"][0]["content"]


def test_long_answers_are_cut_to_fit_the_panel(house):
    long = ANSWER | {"opening": "z" * 400, "line": "x" * 200, "facts": ["y" * 80] * 4}

    made = asyncio.run(briefing.make(CFG, house, NOW, FakeClaude(long)))

    assert len(made.paragraph) == briefing.OPENING_MAX
    assert len(made.line) == briefing.LINE_MAX
    assert all(len(f) == briefing.FACT_MAX for f in made.facts)


def test_sends_it_in_quiet_hours_and_keeps_it_for_the_panel(house):
    sent = Sent()

    asyncio.run(briefing.run(CFG, house, NOW, FakeClaude(), sent.client()))

    assert sent.texts == [MESSAGE]
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
        f"{MESSAGE}\n\n<b>Overnight · 1 warning, 1 info, 2 OK</b>\nWARNING · volume2 is 91% full"]
    # Nothing is left for "While you slept" at 07:00.
    assert core.held(house) == []
    assert asyncio.run(core.send_digests(house, CFG, SEVEN, sent.client())) == 0
    assert len(sent.texts) == 1


def test_a_quiet_night_adds_no_overnight_section(house):
    sent = Sent()

    asyncio.run(briefing.run(CFG, house, NOW, FakeClaude(), sent.client()))

    assert sent.texts == [MESSAGE]


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

    assert sent.texts == [f"<b>Briefing Thursday</b>\n{ANSWER['opening']}"]
    assert len(core.held(house)) == 1


def test_a_warning_still_open_is_only_counted_overnight(house):
    hold(house, "warning", "volume2 is 91% full")
    open_incident(house, "disk_space:volume2", "disk_space", "warning", "volume2 is 91% full")
    sent = Sent()

    asyncio.run(briefing.run(CFG, house, NOW, FakeClaude(), sent.client()))

    (text,) = sent.texts
    assert "<i>WARNING</i> · volume2 is 91% full" in text
    assert text.endswith("<b>Overnight · 1 warning</b>")


def test_many_warnings_are_cut_with_a_note():
    held = [{"severity": "warning", "title": f"w{i}"} for i in range(core.DIGEST_LIMIT + 2)]

    values = briefing.overnight(held)

    assert values["overnight"] == (f"Overnight · {core.DIGEST_LIMIT + 2} warnings "
                                   f"(the first {core.DIGEST_LIMIT} here, all on the Alerts page)")
    assert len(values["held"]) == core.DIGEST_LIMIT


def test_without_portfolio_data_there_is_no_markets_section(house):
    house.put_cache("portfolio", {})
    sent = Sent()

    asyncio.run(briefing.run(CFG, house, NOW, FakeClaude(), sent.client()))

    (text,) = sent.texts
    assert "Markets" not in text and "blockquote" not in text
    assert "16:00\n\n<b>House</b>" in text


def test_old_figures_say_when_they_are_from(house):
    house.put_cache("portfolio", house.get_cache("portfolio") | {"stale": True})

    (portfolio, *_) = briefing.markets(CFG, house, NOW)["market_lines"]

    assert portfolio["text"] == "€ 9.119, +€ 31,00 (+0,34%); figures from Thu 06:15"


def test_one_holding_has_no_best_or_worst(house):
    house.put_cache("portfolio", {"total_value": 100.0, "holdings": [
        {"symbol": "NVDA", "day_pct": 1.0, "day_abs": 1.0}]})
    house.put_cache("indices", {})

    lines = briefing.markets(CFG, house, NOW)["market_lines"]

    assert [line["label"] for line in lines] == ["Portfolio"]
