from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pyatv
import pytest
from pyatv.const import PowerState, Protocol

from app.sources import apple_tv

CFG = {"music": {"wake": {"address": "10.0.0.217", "credentials": "secret-creds"}}}


class FakeTV:
    def __init__(self, power=PowerState.Off):
        self.actions: list[str] = []
        self.power = SimpleNamespace(power_state=power, turn_on=self._on)
        self.apps = SimpleNamespace(launch_app=self._launch)
        self.closed = False

    async def _on(self):
        self.actions.append("on")

    async def _launch(self, bundle):
        self.actions.append(f"launch {bundle}")

    def close(self):
        self.closed = True


@pytest.fixture
def tv(monkeypatch):
    fake = FakeTV()
    conf = SimpleNamespace(credentials={})
    conf.set_credentials = lambda protocol, value: conf.credentials.update({protocol: value})
    found = {"hosts": None}

    async def scan(loop, hosts=None, timeout=None):
        found["hosts"] = hosts
        return [conf]

    async def connect(c, loop):
        assert c.credentials == {Protocol.Companion: "secret-creds"}
        return fake

    monkeypatch.setattr(pyatv, "scan", scan)
    monkeypatch.setattr(pyatv, "connect", connect)
    fake.found = found
    return fake


def test_switches_the_tv_on_and_opens_spotify(tv):
    assert asyncio.run(apple_tv.wake_spotify(CFG)) is True

    assert tv.actions == ["on", "launch com.spotify.client"]
    assert tv.found["hosts"] == ["10.0.0.217"] and tv.closed


def test_a_tv_that_is_on_only_gets_spotify_opened(tv):
    tv.power.power_state = PowerState.On

    asyncio.run(apple_tv.wake_spotify(CFG))

    assert tv.actions == ["launch com.spotify.client"]


def test_does_nothing_without_credentials(tv):
    cfg = {"music": {"wake": {"address": "10.0.0.217", "credentials": ""}}}

    assert asyncio.run(apple_tv.wake_spotify(cfg)) is False
    assert tv.actions == [] and tv.found["hosts"] is None


def test_a_failure_is_false_and_logs_only_its_kind(monkeypatch, caplog):
    async def scan(loop, hosts=None, timeout=None):
        raise OSError("10.0.0.217 secret-creds unreachable")

    monkeypatch.setattr(pyatv, "scan", scan)
    with caplog.at_level(logging.WARNING):
        assert asyncio.run(apple_tv.wake_spotify(CFG)) is False

    assert "OSError" in caplog.text
    assert "secret-creds" not in caplog.text and "10.0.0.217" not in caplog.text
