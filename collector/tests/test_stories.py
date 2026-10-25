from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest

from app import ai
from app.alerts import core
from app.desk_headlines import badge
from app.news import headlines, stories
from app.news import store as news
from tests.test_headlines import NOW, Web, public_dns  # noqa: F401 (the fixture is used)

CFG = {"timezone": "Europe/Amsterdam", "ai": {"api_key": "sk-test"}}


class FakeClaude:
    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def __call__(self, api_key):
        return SimpleNamespace(messages=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][0]["content"])
        usage = SimpleNamespace(input_tokens=3000, output_tokens=400,
                                cache_read_input_tokens=0, cache_creation_input_tokens=0)
        text = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return SimpleNamespace(stop_reason="end_turn", usage=usage,
                               content=[SimpleNamespace(type="text", text=text)])


@pytest.fixture
def feeds(store):
    news.ensure_tables(store)
    ai.ensure_tables(store)
    core.ensure_tables(store)
    ai.set_switches(store, {"headlines": True})
    return {title: news.add_group(store, title) for title in ("Nederland", "Tech")}


def add(store, group, source, path, minutes_ago, image=None):
    url = f"https://{source.lower().replace('.', '')}.example{path}"
    news.save_articles(store, group, [{
        "url": url, "title": f"{source}: {path.strip('/')}", "source": source,
        "published": NOW - timedelta(minutes=minutes_ago), "image": image,
        "summary": f"First line of {path}"}], NOW)
    return news.article_id(url)


@pytest.fixture
def articles(store, feeds):
    """Newest first, as the prompt numbers them."""
    nl, tech = feeds["Nederland"], feeds["Tech"]
    return [
        add(store, tech, "Tweakers", "/ios", 10),                              # 1
        add(store, nl, "NOS", "/housing", 20),                                 # 2
        add(store, nl, "NU.nl", "/housing-plan", 30, "https://news.example/big.jpg"),  # 3
        add(store, tech, "Tweakers", "/housing-tech", 40),                     # 4
        add(store, nl, "NOS", "/strike", 50),                                  # 5
        add(store, nl, "NU.nl", "/strike-off", 60),                            # 6
        add(store, tech, "The Verge", "/old", 60 * 13),                        # outside the window
    ]


GROUPED = {"stories": [
    {"articles": [1], "summary": "ignored for one article"},
    {"articles": [2, 3, 4], "summary": "The cabinet presents a plan for 100,000 homes a year."},
    {"articles": [5, 6, 6, 99], "summary": "Monday's rail strike is called off."},
]}


def group(store, answer=GROUPED):
    claude = FakeClaude(answer)
    kept = asyncio.run(stories.group(CFG, store, NOW, claude))
    return kept, claude


def test_asks_with_the_last_hours_numbered_newest_first(store, articles):
    _, claude = group(store)

    (prompt,) = claude.prompts
    assert prompt.splitlines()[:3] == [
        "Articles:",
        "1. [Tweakers] Tweakers: ios | First line of /ios",
        "2. [NOS] NOS: housing | First line of /housing",
    ]
    assert "The Verge" not in prompt


def test_keeps_the_stories_by_id_without_repeats_or_strangers(store, articles):
    kept, _ = group(store)

    assert kept["stories"] == [
        {"ids": [articles[0]], "summary": None},
        {"ids": articles[1:4], "summary": "The cabinet presents a plan for 100,000 homes a year."},
        {"ids": articles[4:6], "summary": "Monday's rail strike is called off."},
    ]
    assert store.get_cache(stories.CACHE_KEY) == kept


def test_the_top_stories_rank_by_feeds_then_newest_with_every_source(store, articles):
    group(store)

    result = asyncio.run(headlines.collect(store, httpx.MockTransport(Web().handler), NOW, CFG))

    assert result.grouped is True
    assert [(h.title, len(h.sources)) for h in result.items] == [
        ("NU.nl: housing-plan", 2),  # three feeds; led by the one with a lead picture
        ("NOS: strike", 1),          # two feeds
        ("Tweakers: ios", 0),        # one feed fills the list
    ]
    lead = result.items[0]
    assert lead.image == "lead" and lead.story.startswith("The cabinet")
    assert [s.source for s in lead.sources] == ["NOS", "Tweakers"]
    assert result.items[2].story is None


def test_without_a_fresh_grouping_the_headlines_are_as_before(store, articles):
    group(store)
    web = httpx.MockTransport(Web().handler)

    ai.set_switches(store, {"headlines": False})
    assert asyncio.run(headlines.collect(store, web, NOW, CFG)).grouped is False

    ai.set_switches(store, {"headlines": True})
    later = NOW + stories.FRESH + timedelta(minutes=1)
    assert asyncio.run(headlines.collect(store, web, later, CFG)).grouped is False


def test_an_unreadable_answer_groups_nothing(store, articles):
    assert group(store, "no json")[0] is None
    assert store.get_cache(stories.CACHE_KEY) is None


def test_the_same_articles_are_not_asked_twice(store, articles):
    _, claude = group(store)
    again, _ = group(store, "would not be asked")

    assert again["stories"][1]["summary"].startswith("The cabinet")
    assert len(claude.prompts) == 1


def test_the_panel_badge_counts_the_other_feeds():
    assert badge({"source": "NOS", "sources": [{"id": "a"}, {"id": "b"}]}) == "NOS +2"
    assert badge({"source": "NU.nl", "sources": []}) == "NU.nl"
