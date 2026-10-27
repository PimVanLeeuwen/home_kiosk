from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app import ai
from app.news import store as news
from app.portfolio import notes, report

CFG = {"timezone": "Europe/Amsterdam", "ai": {"api_key": "sk-test"}}
NOW = datetime(2026, 10, 29, 5, 30, tzinfo=UTC)
PORTFOLIO = {
    "as_of": "2026-10-29T05:15:00+00:00", "total_value": 9119.0, "holdings": [
        {"symbol": "NVDA", "name": "NVIDIA Corp", "day_pct": 4.2, "day_abs": 60.5},
        {"symbol": "VWRL", "name": "Vanguard FTSE All-World", "day_pct": -0.4, "day_abs": -4.1},
        {"symbol": "ASML", "name": "ASML Holding NV", "day_pct": -2.5, "day_abs": -31.0},
        {"symbol": "SHELL", "name": "Shell plc", "day_pct": 1.8, "day_abs": 9.0}]}
INDICES = {"indices": [{"label": "S&P 500", "day_pct": 0.52}]}
ANSWER = {"notes": [
    {"symbol": "ASML", "note": "Fell after it lowered its outlook for next year."},
    {"symbol": "NVDA", "note": "Rose after the US eased export rules for chips."},
    {"symbol": "SHELL", "note": "Not a mover, so left out."}]}


class FakeClaude:
    def __init__(self, answer=ANSWER):
        self.answer, self.calls = answer, []

    def __call__(self, api_key):
        return SimpleNamespace(messages=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = SimpleNamespace(input_tokens=3000, output_tokens=100,
                                cache_read_input_tokens=0, cache_creation_input_tokens=0)
        text = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return SimpleNamespace(stop_reason="end_turn", usage=usage,
                               content=[SimpleNamespace(type="text", text=text)])


@pytest.fixture
def feeds(store):
    ai.ensure_tables(store)
    news.ensure_tables(store)
    ai.set_switches(store, {"market_notes": True})
    news.save_articles(store, "world", [
        {"url": "https://example.org/a", "title": "VS versoepelt exportregels voor chips",
         "source": "NOS", "published": NOW - timedelta(hours=3),
         "summary": "Nvidia en AMD mogen weer meer verkopen aan China."},
        {"url": "https://example.org/b", "title": "ASML lowers its 2027 outlook",
         "source": "Reuters", "published": NOW - timedelta(hours=20)},
        {"url": "https://example.org/c", "title": "Too old to count", "source": "NOS",
         "published": NOW - timedelta(hours=30)}], NOW)
    return store


def test_the_two_biggest_moves_over_one_percent():
    assert [h["symbol"] for h in notes.movers(PORTFOLIO)] == ["NVDA", "ASML"]
    exactly = {"holdings": [{"symbol": "X", "day_pct": 1.0}, {"symbol": "Y", "day_pct": -0.9}]}
    assert notes.movers(exactly) == []


def test_asks_haiku_with_tickers_moves_and_headlines_but_no_amounts(feeds):
    claude = FakeClaude()

    found = asyncio.run(notes.notes(CFG, feeds, PORTFOLIO, INDICES, NOW, claude))

    # In the movers' order, and only theirs.
    assert found == {"NVDA": "Rose after the US eased export rules for chips.",
                     "ASML": "Fell after it lowered its outlook for next year."}
    (call,) = claude.calls
    assert call["model"] == "claude-haiku-5-5"
    prompt = call["messages"][0]["content"]
    assert "- NVDA (NVIDIA Corp): +4.20%" in prompt
    assert "- ASML (ASML Holding NV): -2.50%" in prompt
    assert "Indices: S&P 500 +0.52%" in prompt
    assert ("1. [NOS] VS versoepelt exportregels voor chips | Nvidia en AMD mogen weer meer "
            "verkopen aan China.") in prompt
    assert "2. [Reuters] ASML lowers its 2027 outlook" in prompt
    assert "Too old" not in prompt and "SHELL" not in prompt
    for amount in ("9119", "60.5", "60,5", "€", "-31"):
        assert amount not in prompt


def test_switched_off_or_no_movers_asks_nothing(feeds):
    claude = FakeClaude()
    calm = {"holdings": [{"symbol": "VWRL", "day_pct": 0.3}]}
    assert asyncio.run(notes.notes(CFG, feeds, calm, INDICES, NOW, claude)) == {}

    ai.set_switches(feeds, {"market_notes": False})
    assert asyncio.run(notes.notes(CFG, feeds, PORTFOLIO, INDICES, NOW, claude)) == {}
    assert claude.calls == []


def test_an_unreadable_answer_gives_no_notes(feeds):
    assert asyncio.run(notes.notes(CFG, feeds, PORTFOLIO, INDICES, NOW,
                                   FakeClaude("not json"))) == {}
    blank = {"notes": [{"symbol": "NVDA", "note": "  "}]}
    assert asyncio.run(notes.notes(CFG, feeds, PORTFOLIO, None, NOW, FakeClaude(blank))) == {}


def test_long_notes_are_cut(feeds):
    long = {"notes": [{"symbol": "NVDA", "note": "x" * 400}]}

    found = asyncio.run(notes.notes(CFG, feeds, PORTFOLIO, INDICES, NOW, FakeClaude(long)))

    assert len(found["NVDA"]) == notes.NOTE_MAX


def test_the_portfolio_report_adds_a_line_per_note():
    _, text = report.build(PORTFOLIO, INDICES, CFG, NOW, notes={
        "NVDA": "Rose after the US eased export rules for chips."})

    assert text.endswith("</pre>\n<i>NVDA</i> · Rose after the US eased export rules for chips.")
    _, plain = report.build(PORTFOLIO, INDICES, CFG, NOW)
    assert plain.endswith("</pre>")
