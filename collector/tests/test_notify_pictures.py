"""Pictures with notifications (plan.md M31 step 4)."""

from __future__ import annotations

import asyncio
import io
import json
from datetime import UTC, datetime, timedelta
from email.header import decode_header

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import briefing, main, paint_notify
from app.alerts import core, page, pictures, rules
from app.alerts.ntfy import Ntfy, header
from app.portfolio import report

CFG = {"timezone": "Europe/Amsterdam", "hub": {"url": "https://hub.example.ts.net"}}
NOW = datetime(2026, 11, 2, 5, 30, tzinfo=UTC)  # Monday 06:30 in Amsterdam
DAY = datetime(2026, 11, 2, 11, 0, tzinfo=UTC)  # 12:00, outside quiet hours
PORTFOLIO = {"as_of": NOW.isoformat(), "total_value": 10000.0, "change": {"day_pct": 0.8},
             "holdings": [{"symbol": "NVDA", "day_pct": 3.1, "day_abs": 60.0},
                          {"symbol": "ASML", "day_pct": -0.4, "day_abs": -10.0}]}


class FakeNtfy:
    def __init__(self):
        self.requests = []

    def client(self):
        def handler(request):
            self.requests.append(request)
            return httpx.Response(200, json={"id": f"n{len(self.requests)}"})

        return Ntfy("http://ntfy.test", "tk_x", transport=httpx.MockTransport(handler))


@pytest.fixture
def alerts(store):
    core.ensure_tables(store)
    rules.ensure_tables(store)
    return store


def send(store, fake, picture, now=DAY, **fields):
    defaults = {"source": "rule.disk_space", "category": "rules", "severity": "warning",
                "title": "volume2 is 91% full", "body": "500 GB left; grows 4 GB a week."}
    return asyncio.run(core.notify(store, CFG, now=now, ntfy=fake.client(), picture=picture,
                                   **(defaults | fields)))


def card() -> Image.Image:
    return paint_notify.gauge("Storage box", 87, "130 GB", "1 TB", 85)


# --- the painter -------------------------------------------------------------------------


@pytest.mark.parametrize("image", [
    paint_notify.disk("volume2", 91, "500 GB", 90, [80 + i * 0.4 for i in range(30)]),
    paint_notify.disk("volume2", 91, "500 GB", 90, []),  # no history yet
    paint_notify.gauge("Storage box", 87, "130 GB", "1 TB", 85),
    paint_notify.move(-3.4, [("NVDA", -6.2), ("ADYEN", 1.3)], "Mon 2 Nov"),
    paint_notify.report("Evening report", "Mon 2 Nov", 0.8, [("NVDA", 3.1)], [("AEX", 0.3)]),
    paint_notify.report("Evening report", "Mon 2 Nov", 0.0, [], []),
    paint_notify.briefing("Monday 2 November", "07:16 on time", "Platform 5",
                          [paint_notify.Tile("House", "all quiet", "ok")]),
])
def test_every_picture_is_a_small_landscape_jpeg(image):
    data = paint_notify.jpeg(image)

    assert image.size == (1200, 800)
    assert data[:2] == b"\xff\xd8" and len(data) <= paint_notify.MAX_BYTES


def test_pictures_are_the_same_for_the_same_figures():
    first = paint_notify.jpeg(paint_notify.gauge("Storage box", 87, "130 GB", "1 TB", 85))

    assert paint_notify.jpeg(paint_notify.gauge("Storage box", 87, "130 GB", "1 TB", 85)) == first


# --- ntfy ----------------------------------------------------------------------------------


def test_headers_carry_utf8_and_line_breaks_as_one_encoded_word():
    assert header("Plain ASCII") == "Plain ASCII"
    encoded = header("Platform 5 · 9 °C\nNVDA −6,2%")
    assert encoded.startswith("=?utf-8?b?")
    [(raw, charset)] = decode_header(encoded)
    assert raw.decode(charset) == "Platform 5 · 9 °C\nNVDA −6,2%"


def test_a_message_with_a_picture_is_uploaded_with_its_fields_in_headers(alerts):
    fake = FakeNtfy()

    message = send(alerts, fake, card)

    request = fake.requests[0]
    assert (request.method, request.url.path) == ("PUT", "/hub-rules")
    assert request.content[:2] == b"\xff\xd8"
    assert request.headers["title"] == "volume2 is 91% full"
    assert request.headers["message"] == "500 GB left; grows 4 GB a week."
    assert (request.headers["priority"], request.headers["tags"]) == ("3", "orange_circle")
    assert request.headers["click"] == f"https://hub.example.ts.net/alerts/{message.id}"
    assert request.headers["filename"] == "picture.jpg"
    assert core.picture(alerts, message.id) == request.content


def test_without_a_picture_the_message_goes_as_json(alerts):
    fake = FakeNtfy()

    send(alerts, fake, None)

    assert fake.requests[0].method == "POST"
    assert json.loads(fake.requests[0].content)["topic"] == "hub-rules"


def test_a_picture_that_fails_leaves_the_message_as_it_was(alerts, caplog):
    fake = FakeNtfy()

    def broken():
        raise ValueError("no data")

    message = send(alerts, fake, broken)

    assert message.status == "sent" and fake.requests[0].method == "POST"
    assert core.picture(alerts, message.id) is None
    assert "picture for message" in caplog.text


def test_pictures_older_than_a_page_are_dropped(alerts):
    fake = FakeNtfy()
    old = send(alerts, fake, card, now=DAY - timedelta(days=9))

    send(alerts, fake, card)

    assert core.picture(alerts, old.id) is None


# --- the page ----------------------------------------------------------------------------


def test_the_page_has_its_picture_while_it_lasts(alerts):
    message = send(alerts, FakeNtfy(), card, now=datetime.now(UTC))
    plain = send(alerts, FakeNtfy(), None, now=datetime.now(UTC))
    main.app.state.store, main.app.state.config = alerts, CFG
    client = TestClient(main.app)

    got = client.get(f"/api/alerts/messages/{message.id}/picture")

    assert got.status_code == 200 and got.headers["content-type"] == "image/jpeg"
    assert got.content == core.picture(alerts, message.id)
    assert page.page(CFG, alerts, message.id)["picture"] is True
    assert page.page(CFG, alerts, plain.id)["picture"] is False
    assert client.get(f"/api/alerts/messages/{plain.id}/picture").status_code == 404
    assert page.picture(alerts, message.id, datetime.now(UTC) + timedelta(days=8)) is None


# --- which messages get one --------------------------------------------------------------


def test_disk_space_paints_the_pools_last_30_days(alerts, monkeypatch):
    alerts.put_cache("nas", {"storage": {"pools": [
        {"name": "volume2", "used_pct": 91.0, "total_bytes": 1000, "free_bytes": 90}]}})
    for day in range(40):
        alerts.put_storage_sample(f"2026-09-{day % 30 + 1:02d}" if day < 30 else
                                  f"2026-10-{day - 29:02d}", "/volume2", 800 + day)
    seen = {}
    monkeypatch.setattr(paint_notify, "disk",
                        lambda *args: seen.setdefault("args", args) and Image.new("RGB", (1, 1)))
    problem = rules.Problem("disk_space:volume2", "disk_space", "warning", "disk_space",
                            {"pool": "volume2", "free": "90 B"})

    painter = pictures.for_problem(CFG, alerts, problem, {"threshold_pct": 90}, NOW)

    assert painter is not None and painter() is not None
    pool, used, free, limit, history = seen["args"]
    assert (pool, used, free, limit) == ("volume2", 91.0, "90 B", 90)
    assert len(history) == 30 and history[-1] == pytest.approx(83.9)


def test_a_pool_the_hub_does_not_know_paints_nothing(alerts):
    assert pictures.disk(alerts, "volume9", "1 GB", 90) is None


def test_only_figure_rules_get_a_picture(alerts):
    problem = rules.Problem("down:sonarr", "container_health", "error", "container_down", {})

    assert pictures.for_problem(CFG, alerts, problem, {}, NOW) is None


def test_the_portfolio_move_and_report_use_percentages(alerts, monkeypatch):
    alerts.put_cache("portfolio", PORTFOLIO)
    seen = {}
    monkeypatch.setattr(paint_notify, "move", lambda *a: seen.setdefault("move", a))
    monkeypatch.setattr(paint_notify, "report", lambda *a: seen.setdefault("report", a))

    pictures.move(CFG, alerts, NOW)
    report.picture(PORTFOLIO, {"indices": [{"label": "AEX", "day_pct": 0.3}]}, CFG, NOW)

    assert seen["move"] == (0.5, [("NVDA", 3.1), ("ASML", -0.4)], "Mon 2 Nov")
    assert seen["report"] == ("Morning report", "Mon 2 Nov", 0.5,
                              [("NVDA", 3.1), ("ASML", -0.4)], [("AEX", 0.3)])


# --- the briefing card --------------------------------------------------------------------


@pytest.fixture
def morning(alerts):
    alerts.put_cache("weather", {"temperature": 8.6, "description": "half bewolkt"})
    alerts.put_cache("forecast", {"days": [{"date": "2026-11-02", "low": 6, "high": 12,
                                            "hours": [{"hour": 16, "rain_chance": 70}]}]})
    alerts.put_cache("calendar", {"date": "2026-11-02", "events": [{"start": "x"}] * 2,
                                  "all_day": [{"title": "y"}]})
    alerts.put_cache("portfolio", PORTFOLIO)
    return alerts


def briefing_args(store, monkeypatch):
    seen = {}
    monkeypatch.setattr(paint_notify, "briefing", lambda *a: seen.setdefault("a", a))
    briefing.card(CFG, store, NOW)
    return seen["a"]


def test_the_briefing_card_leads_with_the_train(morning, monkeypatch):
    morning.put_cache("train", {"date": "2026-11-02", "mode": "morning", "departure": "07:16",
                                "train": {"status": "late", "delay_minutes": 6,
                                          "planned_track": "5"}})

    day, headline, detail, tiles, tone = briefing_args(morning, monkeypatch)

    assert (day, headline, tone) == ("Monday 2 November", "07:16 6 min late", "warning")
    assert detail == "Platform 5 · 9 °C, rain from 16:00"
    assert [(t.label, t.value, t.tone) for t in tiles] == [
        ("Portfolio", "+0,50%", "ok"), ("Today", "3 events", None), ("House", "all quiet", "ok")]


def test_without_a_train_the_weather_leads(morning, monkeypatch):
    _, headline, detail, _, tone = briefing_args(morning, monkeypatch)

    assert (headline, detail, tone) == ("9 °C", "Half bewolkt, rain from 16:00", "info")


def test_a_cancelled_train_is_red(morning, monkeypatch):
    morning.put_cache("train", {"date": "2026-11-02", "mode": "morning", "departure": "07:16",
                                "train": {"status": "cancelled"}})

    _, headline, _, _, tone = briefing_args(morning, monkeypatch)

    assert (headline, tone) == ("07:16 cancelled", "error")


def test_the_real_card_paints(morning):
    assert briefing.card(CFG, morning, NOW).size == (1200, 800)


def test_jpeg_decodes():
    data = paint_notify.jpeg(card())

    assert Image.open(io.BytesIO(data)).size == (1200, 800)
