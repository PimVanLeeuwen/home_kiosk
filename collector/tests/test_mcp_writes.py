from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any

import pytest
from mcp.client import Client

from app import mcp_server, reminders
from app.alerts import core
from app.sources import hue, music

CFG = {"timezone": "Europe/Amsterdam",
       "hue": {"key": "k", "bridge": "192.0.2.1", "bridge_id": "abc"},
       "music": {"client_id": "id"}}


def lights(on: bool = True) -> hue.Lights:
    spot = hue.Light(id="l1", name="Spot 1", on=on, brightness=60.0, kelvin=2700)
    return hue.Lights(as_of=datetime(2026, 11, 12, tzinfo=UTC), room="Living room", groups=[
        hue.LightGroup(id="spots", name="Spots", kind="ambiance", on=on, brightness=60,
                       kelvin=2700, lights=[spot])])


def call(store, name: str, args: dict[str, Any], cfg: dict[str, Any] | None = None):
    server = mcp_server.build(lambda: store, lambda: cfg or CFG, writes=True)

    async def ask():
        async with Client(server) as client:
            return await client.call_tool(name, args)

    return asyncio.run(ask())


def test_write_tools_say_they_change_something_but_nothing_for_good(store):
    server = mcp_server.build(lambda: store, lambda: CFG, writes=True)

    async def ask():
        async with Client(server) as client:
            return (await client.list_tools()).tools

    writes = {t.name: t for t in asyncio.run(ask()) if not t.annotations.read_only_hint}

    assert set(writes) == {"lights_room", "lights_change", "music_control", "music_volume",
                           "music_play_favourite", "add_reminder", "tick_reminder",
                           "send_test_message"}
    assert not any(t.annotations.destructive_hint for t in writes.values())


def test_lights_room_switches_and_answers_with_the_bridge_state(store, monkeypatch):
    asked = []

    async def switch_room(cfg, s, on, bridge=None):
        asked.append(on)
        return lights(on)

    monkeypatch.setattr(hue, "switch_room", switch_room)

    out = call(store, "lights_room", {"on": False}).structured_content

    assert asked == [False]
    assert out["groups"][0]["on"] is False and out["groups"][0]["id"] == "spots"


def test_lights_change_checks_the_white_before_asking_the_bridge(store, monkeypatch):
    asked = []

    async def change(cfg, s, group, **kw):
        asked.append((group, kw))
        return lights()

    monkeypatch.setattr(hue, "change", change)

    wrong = call(store, "lights_change", {"group": "spots", "kelvin": 3000})
    right = call(store, "lights_change", {"group": "spots", "brightness": 40, "kelvin": 2700})

    assert wrong.is_error and "kelvin" in wrong.content[0].text
    assert not right.is_error
    assert asked == [("spots", {"on": None, "brightness": 40, "kelvin": 2700})]


def test_lights_change_names_an_unknown_group(store, monkeypatch):
    async def change(cfg, s, group, **kw):
        raise KeyError(group)

    monkeypatch.setattr(hue, "change", change)

    result = call(store, "lights_change", {"group": "kitchen", "on": True})

    assert result.is_error and "'kitchen'" in result.content[0].text


def test_lights_without_a_bridge_set_up_say_so(store):
    result = call(store, "lights_room", {"on": True}, cfg={"timezone": "UTC"})

    assert result.is_error and "not set up" in result.content[0].text


def test_music_tools_reach_spotify_through_the_hub(store, monkeypatch):
    done = []

    async def control(cfg, s, action):
        done.append(("control", action))

    async def volume(cfg, s, percent):
        done.append(("volume", percent))

    async def play_favourite(cfg, s, position):
        done.append(("favourite", position))
        return "tv-1"

    monkeypatch.setattr(music, "control", control)
    monkeypatch.setattr(music, "volume", volume)
    monkeypatch.setattr(music, "play_favourite", play_favourite)

    assert not call(store, "music_control", {"action": "pause"}).is_error
    assert call(store, "music_volume", {"percent": 101}).is_error
    assert not call(store, "music_volume", {"percent": 30}).is_error
    played = call(store, "music_play_favourite", {"position": 2}).structured_content

    assert done == [("control", "pause"), ("volume", 30), ("favourite", 2)]
    assert played == {"ok": True, "device_id": "tv-1"}


def test_add_and_tick_off_a_reminder(store):
    reminders.ensure_tables(store)

    made = call(store, "add_reminder", {"title": "Call the plumber", "on": "2026-11-20",
                                        "at": "09:30", "notify": "hour"}).structured_content
    ticked = call(store, "tick_reminder", {"reminder_id": made["id"], "on": "2026-11-20"})
    other_day = call(store, "tick_reminder", {"reminder_id": made["id"], "on": "2026-11-21"})

    assert made["on"] == "2026-11-20" and made["at"] == "09:30"
    assert reminders.today(store, date(2026, 11, 20))[0]["done"] is True
    assert ticked.structured_content["done"] is True
    assert other_day.is_error and "does not fall" in other_day.content[0].text


def test_a_reminder_an_hour_before_needs_a_time(store):
    reminders.ensure_tables(store)

    result = call(store, "add_reminder", {"title": "Bins", "on": "2026-11-20",
                                          "notify": "hour"})

    assert result.is_error and "time" in result.content[0].text
    assert reminders.all_reminders(store) == []


def test_tick_an_unknown_reminder_says_so(store):
    reminders.ensure_tables(store)

    result = call(store, "tick_reminder", {"reminder_id": 99})

    assert result.is_error and "99" in result.content[0].text


@pytest.mark.parametrize(("text", "body"),
                         [("Hello", "Hello"), ("   ", "Claude can reach the hub.")])
def test_send_test_message_goes_out_also_in_quiet_hours(store, monkeypatch, text, body):
    sent = []

    async def notify(s, cfg, **kw):
        sent.append(kw)
        return core.AlertMessage(id=1, ts=datetime.now(UTC), source=kw["source"],
                                 category=kw["category"], severity="info", title=kw["title"],
                                 body=kw["body"], chat="nas", status="sent", error=None,
                                 sent_at=datetime.now(UTC), channel="ntfy")

    monkeypatch.setattr(core, "notify", notify)

    out = call(store, "send_test_message", {"text": text}).structured_content

    assert out == {"ok": True, "status": "sent", "channel": "ntfy"}
    assert sent[0]["category"] == "manual" and sent[0]["bypass_quiet"] is True
    assert sent[0]["body"] == body
