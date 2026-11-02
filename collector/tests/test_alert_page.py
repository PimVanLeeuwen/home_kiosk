"""A message's own page, /alerts/{id} (plan.md M31 step 3)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ai, main
from app.alerts import core, page, rules, templates
from app.alerts.ntfy import Ntfy

CFG = {
    "timezone": "Europe/Amsterdam",
    "ai": {"api_key": "sk-test"},
    "hub": {"url": "https://hub.example.ts.net"},
    "telegram": {"token": "t", "chats": {"nas": {"id": "-1", "label": "NAS alerts"}}},
}
NOW = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
ANSWER = {"alerts": [{"n": 1, "cause": "The container was killed for memory.",
                      "todo": "Start it again and watch its memory."}]}


class FakeClaude:
    def __init__(self, answer=ANSWER):
        self.answer, self.calls = answer, []

    def __call__(self, api_key):
        # The beta path: the explainer asks with Sonnet's server-side fallback.
        create = self.create
        return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)),
                               messages=SimpleNamespace(create=create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = SimpleNamespace(input_tokens=500, output_tokens=80,
                                cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return SimpleNamespace(stop_reason="end_turn", usage=usage, model="claude-sonnet-5-5",
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answer))])


class FakeNtfy:
    def __init__(self):
        self.published = []

    def client(self):
        def handler(request):
            self.published.append(json.loads(request.content))
            return httpx.Response(200, json={"id": f"n{len(self.published)}"})

        return Ntfy("http://ntfy.test", "tk_x", transport=httpx.MockTransport(handler))


@pytest.fixture
def alerts(store):
    core.ensure_tables(store)
    rules.ensure_tables(store)
    ai.ensure_tables(store)
    return store


def send(store, ntfy=None, now=NOW, **fields):
    defaults = {"source": "rule.container_health", "category": "rules", "severity": "error",
                "title": "sonarr is down", "body": "Exit code 137.",
                "formatted": "<b>ERROR</b> · <b>sonarr is down</b>\nExit code <code>137</code>.",
                "incident": "down:sonarr"}
    return asyncio.run(core.notify(store, CFG, now=now, ntfy=(ntfy or FakeNtfy()).client(),
                                   **(defaults | fields)))


def open_incident(store, key, opened, resolved=None):
    with store.connect() as conn:
        conn.execute("INSERT INTO alert_incident (key, rule, severity, title, opened_at, "
                     "last_seen_at, resolved_at) VALUES (?, 'container_health', 'error', "
                     "'sonarr is down', ?, ?, ?)",
                     (key, opened.isoformat(), opened.isoformat(),
                      resolved.isoformat() if resolved else None))


# --- the tap ---------------------------------------------------------------------


def test_a_notification_taps_through_to_its_own_page(alerts):
    fake = FakeNtfy()

    message = send(alerts, fake)

    assert fake.published[0]["click"] == f"https://hub.example.ts.net/alerts/{message.id}"
    assert (message.status, message.incident) == ("sent", "down:sonarr")
    assert message.html.startswith("<b>ERROR</b>")


def test_a_message_without_a_template_keeps_the_hubs_own_html(alerts):
    message = send(alerts, formatted=None, incident=None, source="hub", category="manual",
                   severity="info", title="Hello <you>", body="")

    assert message.html == "<b>INFO</b> · <b>Hello &lt;you&gt;</b>"


# --- the page --------------------------------------------------------------------


def test_the_page_has_the_text_the_state_the_links_and_the_earlier_messages(alerts):
    open_incident(alerts, "down:sonarr", NOW - timedelta(minutes=30))
    first = send(alerts, now=NOW - timedelta(days=2))
    send(alerts, now=NOW - timedelta(days=9))  # too old for "earlier"
    send(alerts, incident="down:radarr", title="radarr is down")  # another incident
    message = send(alerts)

    found = page.page(CFG, alerts, message.id, NOW + timedelta(minutes=5))

    assert found["html"] == "<b>ERROR</b> · <b>sonarr is down</b>\nExit code <code>137</code>."
    assert found["state"] == {"open": True, "opened_at": (NOW - timedelta(minutes=30)).isoformat(),
                              "resolved_at": None}
    assert [m["id"] for m in found["earlier"]] == [message.id, first.id]
    assert found["links"] == [
        {"label": "Logs in Dozzle", "service": "dozzle", "path": "/show?name=sonarr",
         "hint": "sonarr"},
        {"label": "Docker page", "page": "/docker", "hint": ""}]
    assert found["expires_at"] == (NOW + timedelta(days=7)).isoformat()
    assert found["expired"] is False and found["explanation"] is None


def test_a_resolved_problem_says_when(alerts):
    open_incident(alerts, "down:sonarr", NOW - timedelta(hours=2), resolved=NOW)
    message = send(alerts, now=NOW - timedelta(hours=2))

    state = page.page(CFG, alerts, message.id, NOW)["state"]

    assert state["open"] is False and state["resolved_at"] == NOW.isoformat()


@pytest.mark.parametrize(("source", "category", "first"), [
    ("rule.disk_space", "rules", {"label": "NAS page", "page": "/nas", "hint": "storage"}),
    ("backup", "backup", {"label": "Backups page", "page": "/backups", "hint": ""}),
    ("hub", "portfolio", {"label": "Portfolio page", "page": "/portfolio", "hint": ""}),
    ("uptime-kuma", "uptime", {"label": "Uptime Kuma", "service": "uptime-kuma", "path": "/",
                               "hint": ""}),
    ("briefing", "briefing", {"label": "Home", "page": "/", "hint": ""}),
])
def test_links_lead_to_what_the_message_is_about(source, category, first):
    assert page.links({"source": source, "category": category, "incident": None})[0] == first


def test_a_week_on_the_page_has_expired_and_a_wrong_id_is_none(alerts):
    message = send(alerts, now=NOW - timedelta(days=8))

    assert page.page(CFG, alerts, message.id, NOW) == {
        "id": message.id, "ts": (NOW - timedelta(days=8)).isoformat(), "expired": True}
    assert page.page(CFG, alerts, 999, NOW) is None


# --- explaining ------------------------------------------------------------------


def test_explain_asks_once_and_keeps_the_answer(alerts):
    ai.set_switches(alerts, {"explainer": True})
    open_incident(alerts, "down:sonarr", NOW - timedelta(minutes=30))
    message = send(alerts)
    claude = FakeClaude()

    first = asyncio.run(page.explain(CFG, alerts, message.id, NOW, claude))
    again = asyncio.run(page.explain(CFG, alerts, message.id, NOW, claude))

    assert first == again == {"cause": "The container was killed for memory.",
                              "todo": "Start it again and watch its memory.",
                              "asked_at": NOW.isoformat()}
    assert len(claude.calls) == 1
    prompt = claude.calls[0]["messages"][0]["content"]
    assert "1. [ERROR, open 30 min] sonarr is down" in prompt
    assert page.page(CFG, alerts, message.id, NOW)["explanation"] == first


def test_only_warnings_and_errors_with_the_switch_on_are_explained(alerts):
    info = send(alerts, severity="info", incident=None, title="Backup OK")
    error = send(alerts)

    assert page.page(CFG, alerts, error.id, NOW)["can_explain"] is False  # switch off
    ai.set_switches(alerts, {"explainer": True})
    assert page.page(CFG, alerts, error.id, NOW)["can_explain"] is True
    assert page.page(CFG, alerts, info.id, NOW)["can_explain"] is False
    with pytest.raises(page.ExplainError, match="warnings and errors"):
        asyncio.run(page.explain(CFG, alerts, info.id, NOW, FakeClaude()))


def test_an_unreadable_answer_is_not_kept(alerts):
    ai.set_switches(alerts, {"explainer": True})
    message = send(alerts)

    with pytest.raises(page.ExplainError, match="could not be read"):
        asyncio.run(page.explain(CFG, alerts, message.id, NOW, FakeClaude({"alerts": []})))

    assert page.page(CFG, alerts, message.id, NOW)["explanation"] is None


# --- the endpoints ---------------------------------------------------------------


@pytest.fixture
def client(alerts):
    main.app.state.store = alerts
    main.app.state.config = CFG
    main.app.state.claude_test = FakeClaude()
    yield TestClient(main.app)
    del main.app.state.claude_test


def test_the_page_and_explain_over_http(client, alerts):
    ai.set_switches(alerts, {"explainer": True})
    message = send(alerts, now=datetime.now(UTC))
    origin = {"origin": "http://testserver"}

    found = client.get(f"/api/alerts/messages/{message.id}")
    explained = client.post(f"/api/alerts/messages/{message.id}/explain", json={},
                            headers=origin)

    assert found.status_code == 200 and found.json()["title"] == "sonarr is down"
    assert explained.status_code == 200
    assert explained.json()["cause"] == "The container was killed for memory."
    assert client.get("/api/alerts/messages/999").status_code == 404
    assert client.post(f"/api/alerts/messages/{message.id}/explain", json={},
                       headers={"origin": "https://evil.example"}).status_code == 403


def test_explain_refuses_with_a_reason(client, alerts):
    message = send(alerts, now=datetime.now(UTC))

    resp = client.post(f"/api/alerts/messages/{message.id}/explain", json={},
                       headers={"origin": "http://testserver"})

    assert resp.status_code == 409 and "Alert explainer" in resp.json()["detail"]


def test_rule_messages_carry_their_incident_open_and_resolved(alerts):
    problem = rules.Problem("down:sonarr", "container_health", "error", "container_down",
                            templates.sample_values("container_down"))
    cfg = {"timezone": "Europe/Amsterdam"}  # no channel: logged as failed, no network

    asyncio.run(rules.apply(alerts, cfg, {"container_health": [problem]}, NOW))
    asyncio.run(rules.apply(alerts, cfg, {"container_health": []}, NOW + timedelta(hours=1)))

    assert [m.incident for m in core.messages(alerts)] == ["down:sonarr", "down:sonarr"]
