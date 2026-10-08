from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app import scheduler
from app.alerts import core
from app.portfolio import report

from .test_alerts import CFG as ALERT_CFG
from .test_alerts import FakeTelegram

CFG = {**ALERT_CFG, "portfolio": {"report": {"schedule": "30 8,18 * * mon-fri"}}}
AMS = ZoneInfo("Europe/Amsterdam")
MORNING = datetime(2026, 10, 2, 6, 30, tzinfo=UTC)  # Fri 08:30 in Amsterdam

PORTFOLIO = {
    "as_of": "2026-10-02T06:20:00+00:00",
    "stale": False,
    "total_value": 12345.67,
    "holdings": [
        {"symbol": "NVDA", "day_pct": -5.0, "day_abs": -184.21},
        {"symbol": "ASML.AS", "day_pct": 1.27, "day_abs": 100.32},
        {"symbol": "VUSA.AS", "day_pct": 0.0, "day_abs": 0.0},
    ],
}
INDICES = {"indices": [
    {"symbol": "^GSPC", "label": "S&P 500", "day_pct": 0.19},
    {"symbol": "^AEX", "label": "AEX", "day_pct": -1.1},
]}


def test_report_reads_like_stock_bot():
    title, text = report.build(PORTFOLIO, INDICES, CFG, MORNING)
    assert title == "Morning report"
    assert text == "\n".join([
        "<b>Morning report</b> · Fri 02 Oct, 08:30",
        # 12345.67 - (-83.89) = 12429.56 before the move.
        "<b>€ 12.346</b>  −€ 83,89 (−0,67%) today",
        # One table: names, % and euros line up across holdings and indices.
        "<pre>ASML.AS  +1,27%  +€ 100,32",
        "VUSA.AS  +0,00%    +€ 0,00",
        "NVDA     −5,00%  −€ 184,21",
        "",
        "S&amp;P 500  +0,19%",
        "AEX      −1,10%</pre>",
    ])


def test_evening_title_and_stale_note():
    evening = datetime(2026, 10, 2, 16, 30, tzinfo=UTC)
    title, text = report.build({**PORTFOLIO, "stale": True}, None, CFG, evening)
    assert title == "Evening report"
    assert "Figures from Fri 08:20; Ghostfolio is not answering." in text
    assert "S&amp;P" not in text  # no index line without quotes
    assert "−€ 184,21</pre>" in text  # and no blank line left in the table


def test_old_figures_get_the_note_too():
    later = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    assert "Figures from" in report.build(PORTFOLIO, INDICES, CFG, later)[1]
    assert "Figures from" not in report.build(PORTFOLIO, INDICES, CFG, MORNING)[1]


def test_send_goes_to_the_portfolio_chat_and_logs_plain_text(store):
    core.ensure_tables(store)
    store.put_cache("portfolio", PORTFOLIO)
    store.put_cache("indices", INDICES)
    fake = FakeTelegram()

    asyncio.run(report.send(store, CFG, MORNING, telegram=fake.client()))

    ((_, payload),) = fake.sent
    assert payload["chat_id"] == "-1002"
    assert payload["text"].startswith("<b>Morning report</b>")
    (logged,) = core.messages(store)
    assert (logged.category, logged.title, logged.status) == ("portfolio", "Morning report", "sent")
    assert logged.body.startswith("€ 12.346") and "<b>" not in logged.body
    assert "S&P 500" in logged.body


def test_send_without_data_logs_why(store):
    core.ensure_tables(store)
    fake = FakeTelegram()
    asyncio.run(report.send(store, CFG, MORNING, telegram=fake.client()))
    assert fake.sent == []
    (logged,) = core.messages(store)
    assert (logged.status, logged.error) == ("failed", "No portfolio data yet")


def test_schedule_is_weekdays_in_local_time():
    def after(*when):
        return report.trigger(CFG).get_next_fire_time(None, datetime(*when, tzinfo=AMS))

    assert after(2026, 10, 2, 18, 31) == datetime(2026, 10, 5, 8, 30, tzinfo=AMS)  # Fri to Mon
    assert after(2026, 10, 5, 12, 0) == datetime(2026, 10, 5, 18, 30, tzinfo=AMS)


def test_scheduler_adds_the_report_unless_disabled(store):
    jobs = {j.id: j for j in scheduler.build(CFG, store).get_jobs()}
    assert isinstance(jobs["portfolio-report"].trigger, CronTrigger)
    # Startup only kicks the refreshes (main.py), so a restart sends no report.
    assert all(isinstance(j.trigger, IntervalTrigger) for k, j in jobs.items()
               if k != "portfolio-report")

    off = {**CFG, "portfolio": {"report": {"enabled": False}}}
    assert "portfolio-report" not in {j.id for j in scheduler.build(off, store).get_jobs()}
