"""The hub answers only to its own names (security.KnownHosts), against DNS rebinding."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main, security

TS = "dev-box.tail1234.ts.net"
CFG = {"hub": {"url": f"https://{TS}", "host_names": ["Hub.Example."]}}


@pytest.mark.parametrize("host", [
    "192.168.1.10:8083", "100.64.0.7", "[::1]:8000", "127.0.0.1:8000",
    "localhost:5173", "app.localhost", "host.docker.internal:8000",
    TS, f"{TS.upper()}.", "dev-box:8083", "hub.example",
])
def test_known_hosts_pass(host):
    assert security.allowed_host(host, security.hub_names(CFG, None))


@pytest.mark.parametrize("host", [
    "evil.example", "evil.example:8083", "dev-box.evil.example", f"{TS}.evil.example",
    "[::1", "rebind.192.168.1.10.nip.io",
])
def test_unknown_hosts_are_refused(host):
    assert not security.allowed_host(host, security.hub_names(CFG, None))


def test_no_host_header_passes():
    assert security.allowed_host("", set())


def test_tailscale_name_comes_from_the_hosts_job(store):
    assert "other-nas" not in security.hub_names({}, store)
    store.put_cache("hosts", {"tailscale": {"dns_name": "other-nas.tail9.ts.net.", "ip": None}})
    assert {"other-nas.tail9.ts.net", "other-nas"} <= security.hub_names({}, store)


def test_a_short_name_only_for_tailscale_names():
    # MagicDNS answers "dev-box"; a plain name's first label is not the hub.
    assert "hub" not in security.hub_names(CFG, None)


@pytest.fixture
def client(store, monkeypatch):
    monkeypatch.setattr(main.app.state, "config", CFG, raising=False)
    monkeypatch.setattr(main.app.state, "store", store, raising=False)
    # A fresh middleware stack, so no names are kept from another test.
    monkeypatch.setattr(main.app, "middleware_stack", None)
    return TestClient(main.app)


def test_a_rebinding_page_is_refused(client, caplog):
    # The browser sends the attacker's name as both Origin and Host.
    headers = {"host": "evil.example:8083", "origin": "http://evil.example:8083"}
    for method, path in [("GET", "/api/health"), ("POST", "/api/reminders"), ("POST", "/mcp")]:
        resp = client.request(method, path, headers=headers, json={})
        assert resp.status_code == 421, path
        assert resp.json() == {"detail": "Unknown host name."}
    assert "evil.example" in caplog.text


def test_the_hub_still_answers_its_own_names(client):
    for host in [TS, "192.168.1.10:8083", "host.docker.internal:8000"]:
        assert client.get("/api/health", headers={"host": host}).status_code == 200, host


def test_an_unreadable_store_keeps_the_last_names(monkeypatch):
    calls = iter([{TS}, RuntimeError("database is locked")])

    def names():
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value

    hosts = security.KnownHosts(app=None, names=names)
    assert hosts._known() == {TS}
    monkeypatch.setattr(security, "NAMES_SECONDS", -1)
    assert hosts._known() == {TS}
