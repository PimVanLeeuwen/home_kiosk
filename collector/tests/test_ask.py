from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import ai, ask, main, mcp_server, reminders
from app.sources import hue

CFG = {"timezone": "Europe/Amsterdam", "ai": {"api_key": "sk-test", "cap_eur": 10}}
NOW = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)


def text(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=value)


def use(name: str, args: dict, call_id: str = "t1") -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", name=name, input=args, id=call_id)


class Script:
    """A fake Claude that answers with the given turns, one per call, and keeps the asks."""

    def __init__(self, *turns: list[SimpleNamespace]):
        self.turns, self.calls = list(turns), []

    def __call__(self, api_key):
        return SimpleNamespace(messages=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        content = self.turns.pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        usage = SimpleNamespace(input_tokens=2000, output_tokens=150,
                                cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return SimpleNamespace(stop_reason=stop, usage=usage, content=content)


@pytest.fixture
def hub(store):
    ai.ensure_tables(store)
    reminders.ensure_tables(store)
    ai.set_switches(store, {"ask": True})
    read = mcp_server.build(lambda: store, lambda: CFG)
    write = mcp_server.build(lambda: store, lambda: CFG, writes=True)
    return store, read, write


def run(hub, script: Script, *messages: tuple[str, str], cfg=CFG) -> ask.Answer:
    store, read, write = hub
    question = ask.Question(messages=[ask.Message(role=r, text=t) for r, t in messages])
    return asyncio.run(ask.answer(cfg, store, question, read, write, now=NOW, client=script))


def test_answers_with_the_tools_it_used(hub):
    store, _, _ = hub
    store.put_cache("nas", {"as_of": "t", "cpu_pct": 12.0})
    script = Script([use("nas", {})], [text("The NAS is fine: **12%** CPU.")])

    out = run(hub, script, ("user", "How is the NAS?"))

    assert out.text == "The NAS is fine: **12%** CPU."
    assert out.used == ["nas"] and out.proposals == []
    # Claude got the tool's answer, and the house tools without the developer ones.
    result = script.calls[1]["messages"][-1]["content"][0]
    assert result["tool_use_id"] == "t1" and '"cpu_pct": 12.0' in result["content"]
    names = {t["name"] for t in script.calls[0]["tools"]}
    assert "nas" in names and "lights_change" in names
    assert not names & {"hub_logs", "container_logs", "send_test_message"}
    assert out.spent > 0 and out.cap == 10


def test_a_change_comes_back_as_a_proposal_and_is_not_made(hub, monkeypatch):
    store, _, _ = hub
    store.put_cache(hue.CACHE_KEY, {"groups": [{"id": "spots", "name": "Spots", "on": True,
                                                "brightness": 80}]})

    async def never(*a, **kw):
        raise AssertionError("a proposal must not change the lights")

    monkeypatch.setattr(hue, "change", never)
    script = Script([use("lights_change", {"group": "spots", "brightness": 40})],
                    [text("I proposed dimming the Spots to 40%.")])

    out = run(hub, script, ("user", "Dim the spots to 40%"))

    assert [(p.tool, p.title, p.detail) for p in out.proposals] == [
        ("lights_change", "Dim the Spots to 40%", "now at 80%")]
    assert out.proposals[0].args == {"group": "spots", "brightness": 40}
    assert "not done yet" in script.calls[1]["messages"][-1]["content"][0]["content"]


def test_the_conversation_goes_along_and_ends_with_the_question(hub):
    script = Script([text("Tomorrow too.")])

    run(hub, script, ("assistant", "Hello"), ("user", "Train today?"), ("assistant", "On time."),
        ("user", "And tomorrow?"))

    sent = script.calls[0]["messages"]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[-1]["content"] == "And tomorrow?"
    assert "Thursday 12 November 2026, 16:00" in script.calls[0]["system"]


def test_refusals_before_any_call(hub):
    store, _, _ = hub
    with pytest.raises(ask.AskError) as no_key:
        run(hub, Script(), ("user", "x"), cfg={"timezone": "UTC"})
    ai.set_switches(store, {"ask": False})
    with pytest.raises(ask.AskError) as off:
        run(hub, Script(), ("user", "x"))
    ai.set_switches(store, {"ask": True})
    ai._record(store, NOW, "ask", ask.MODEL, SimpleNamespace(
        input_tokens=200_000_000, output_tokens=0, cache_read_input_tokens=0,
        cache_creation_input_tokens=0))
    with pytest.raises(ask.AskError) as capped:
        run(hub, Script(), ("user", "x"))

    assert (no_key.value.status, off.value.status, capped.value.status) == (503, 409, 429)


def test_a_conversation_must_end_with_a_question(hub):
    with pytest.raises(ask.AskError):
        run(hub, Script(), ("user", "Hi"), ("assistant", "Hello"))


def test_too_many_tool_rounds_stop(hub):
    script = Script(*[[use("nas", {}, f"t{i}")] for i in range(ask.MAX_ROUNDS)])

    out = run(hub, script, ("user", "Loop"))

    assert len(script.calls) == ask.MAX_ROUNDS
    assert "too many steps" in out.text


def test_describe_a_reminder_and_music():
    class Store:
        def get_cache(self, key):
            return None

    title, detail = ask.describe("add_reminder", {"title": "Bins out", "on": "2026-11-19"},
                                 Store())

    assert title == "Add a reminder: Bins out"
    assert detail == "Thursday 19 November, message at 08:00"
    assert ask.describe("music_volume", {"percent": 30}, Store())[0] == \
        "Set the music's volume to 30%"


def test_confirm_runs_the_change_and_only_known_ones(hub):
    store, _, write = hub

    made = asyncio.run(ask.confirm(write, "add_reminder",
                                   {"title": "Bins out", "on": "2026-11-19"}))
    with pytest.raises(ask.AskError) as test_message:
        asyncio.run(ask.confirm(write, "send_test_message", {}))
    with pytest.raises(ask.AskError) as bad:
        asyncio.run(ask.confirm(write, "add_reminder", {"title": "x", "on": "19-11"}))

    assert made["ok"] and reminders.all_reminders(store)[0].title == "Bins out"
    assert test_message.value.status == 422
    assert "YYYY-MM-DD" in str(bad.value)


def test_the_routes_are_same_origin_and_answer(hub):
    store, read, write = hub
    main.app.state.store, main.app.state.config = store, CFG
    main.app.state.mcp_read, main.app.state.mcp_write = read, write
    main.app.state.ask_client = Script([text("Hello.")])
    client = TestClient(main.app)
    try:
        cross = client.post("/api/ask", headers={"Origin": "https://evil.example"},
                            json={"messages": [{"role": "user", "text": "Hi"}]})
        ok = client.post("/api/ask", json={"messages": [{"role": "user", "text": "Hi"}]})
        unknown = client.post("/api/ask/confirm", json={"tool": "nope", "args": {}})
    finally:
        del main.app.state.ask_client

    assert cross.status_code == 403
    assert ok.status_code == 200 and ok.json()["text"] == "Hello."
    assert unknown.status_code == 422
