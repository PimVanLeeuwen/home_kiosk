from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from app.sources import tailscale

STATUS = {
    "BackendState": "Running",
    "Self": {
        "HostName": "dev-minotaur",
        "DNSName": "dev-minotaur.tail1234.ts.net.",
        "TailscaleIPs": ["100.70.0.10", "fd7a:115c:a1e0::1"],
    },
}


def test_parse_status_strips_the_trailing_dot_and_picks_ipv4():
    host = tailscale.parse_status(STATUS)

    assert host.dns_name == "dev-minotaur.tail1234.ts.net"
    assert host.ip == "100.70.0.10"


def test_parse_status_without_ipv4():
    status = {"Self": {"DNSName": "nas.tail1234.ts.net.", "TailscaleIPs": ["fd7a::1"]}}

    assert tailscale.parse_status(status).ip is None


def test_parse_status_without_a_name_is_an_error():
    with pytest.raises(ValueError):
        tailscale.parse_status({"Self": {"DNSName": ""}})
    with pytest.raises(ValueError):
        tailscale.parse_status({})


def test_collect_raises_without_the_socket_so_last_hosts_go_stale(tmp_path):
    cfg = {"hosts": {"lan": "192.168.1.10"}, "tailscale": {"socket": str(tmp_path / "ts.sock")}}

    with pytest.raises(FileNotFoundError):
        asyncio.run(tailscale.collect(cfg))


def test_status_asks_tailscaled_over_its_socket_with_the_required_host():
    import json
    import shutil
    import tempfile
    from pathlib import Path

    # Short path: Unix socket paths are capped at ~104 bytes on macOS.
    folder = tempfile.mkdtemp(dir="/tmp")
    sock = str(Path(folder) / "ts.sock")
    seen: list[bytes] = []

    async def handle(reader, writer):
        head = await reader.readuntil(b"\r\n\r\n")
        seen.append(head)
        payload = SERVE_CONFIG if b"/serve-config" in head else STATUS
        body = json.dumps(payload).encode()
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        await writer.drain()
        writer.close()

    async def run():
        server = await asyncio.start_unix_server(handle, path=sock)
        async with server:
            return await tailscale.status(sock)

    try:
        host = asyncio.run(run())
    finally:
        shutil.rmtree(folder)

    assert host.dns_name == "dev-minotaur.tail1234.ts.net"
    assert host.https_ports == {"8083": 443, "8096": 18096, "5984": 15984}
    requests = [r.decode().lower() for r in seen]
    assert [r.split(" ")[1] for r in requests] == [
        "/localapi/v0/status",
        "/localapi/v0/serve-config",
    ]
    assert all("host: local-tailscaled.sock" in r for r in requests)


SERVE_CONFIG = {
    "TCP": {"443": {"HTTPS": True}, "18096": {"HTTPS": True}, "15984": {"HTTPS": True}},
    "Web": {
        "dev-minotaur.tail1234.ts.net:443": {
            "Handlers": {"/": {"Proxy": "http://127.0.0.1:8083"}}
        },
        "dev-minotaur.tail1234.ts.net:18096": {
            "Handlers": {"/": {"Proxy": "http://localhost:8096/"}}
        },
        "dev-minotaur.tail1234.ts.net:15984": {
            "Handlers": {"/": {"Proxy": "https+insecure://127.0.0.1:5984"}}
        },
        # Not a service link: a path handler, a static text reply, a remote proxy.
        "dev-minotaur.tail1234.ts.net:10001": {"Handlers": {"/api": {"Proxy": "http://127.0.0.1:1"}}},
        "dev-minotaur.tail1234.ts.net:10002": {"Handlers": {"/": {"Text": "hello"}}},
        "dev-minotaur.tail1234.ts.net:10003": {"Handlers": {"/": {"Proxy": "http://10.0.0.5:80"}}},
    },
}


def test_parse_serve_config_maps_local_ports_to_https_ports():
    assert tailscale.parse_serve_config(SERVE_CONFIG) == {
        "8083": 443,
        "8096": 18096,
        "5984": 15984,
    }


def test_parse_serve_config_empty():
    assert tailscale.parse_serve_config({}) == {}
    assert tailscale.parse_serve_config({"Web": None}) == {}


NOW = datetime(2026, 10, 12, 20, 0, tzinfo=UTC)

TAILNET_STATUS = {
    "BackendState": "Running",
    "MagicDNSSuffix": "tail1234.ts.net",
    "CurrentTailnet": {"Name": "owner@example.com", "MagicDNSSuffix": "tail1234.ts.net"},
    "Health": ["Tailscale can't reach the configured DNS servers."],
    "Self": {
        "HostName": "dev-minotaur",
        "DNSName": "dev-minotaur.tail1234.ts.net.",
        "OS": "linux",
        "TailscaleIPs": ["100.70.0.10", "fd7a:115c:a1e0::1"],
        "Relay": "ams",
        "Online": True,
    },
    "Peer": {
        "k1": {
            "HostName": "pim-macbook", "DNSName": "pim-macbook.tail1234.ts.net.", "OS": "macOS",
            "TailscaleIPs": ["100.71.12.4", "fd7a:115c:a1e0::2"], "Online": True, "Active": True,
            "CurAddr": "192.168.1.23:41641", "Relay": "ams", "RxBytes": 1800, "TxBytes": 412,
            "LastSeen": "0001-01-01T00:00:00Z",
        },
        "k2": {
            "HostName": "pim-iphone", "DNSName": "pim-iphone.tail1234.ts.net.", "OS": "iOS",
            "TailscaleIPs": ["100.88.3.51"], "Online": True, "Active": True,
            "CurAddr": "", "Relay": "ams",
        },
        "k3": {
            "HostName": "appletv", "DNSName": "appletv.tail1234.ts.net.", "OS": "tvOS",
            "TailscaleIPs": ["100.64.9.17"], "Online": True, "Active": False, "Relay": "ams",
            "ExitNodeOption": True,
        },
        "k4": {
            "HostName": "desk-pc", "DNSName": "desk-pc.tail1234.ts.net.", "OS": "windows",
            "TailscaleIPs": ["100.102.7.88"], "Online": False, "LastSeen": "2026-10-12T15:00:00Z",
        },
        "k5": {
            "HostName": "Amsterdam 12", "DNSName": "nl-ams-wg-012.mullvad.ts.net.", "OS": "linux",
            "TailscaleIPs": ["100.120.1.1"], "Online": True, "ExitNodeOption": True,
            "Location": {"Country": "Netherlands", "City": "Amsterdam"},
        },
    },
}


def test_parse_tailnet_names_the_tailnet_by_its_suffix_never_the_login():
    net = tailscale.parse_tailnet(TAILNET_STATUS, NOW)

    assert net.name == "tail1234"
    assert "owner@example.com" not in net.model_dump_json()
    assert net.as_of == NOW and not net.stale


def test_parse_tailnet_describes_the_nas_itself():
    me = tailscale.parse_tailnet(TAILNET_STATUS, NOW).self

    assert me.name == "dev-minotaur"
    assert me.dns_name == "dev-minotaur.tail1234.ts.net"
    assert (me.ipv4, me.ipv6) == ("100.70.0.10", "fd7a:115c:a1e0::1")
    assert me.online and me.connection is None
    assert me.relay == "ams"  # the home relay


def test_parse_tailnet_tells_direct_relay_and_idle_apart():
    peers = {p.name: p for p in tailscale.parse_tailnet(TAILNET_STATUS, NOW).peers}

    mac, phone, tv = peers["pim-macbook"], peers["pim-iphone"], peers["appletv"]
    assert (mac.connection, mac.endpoint, mac.relay) == ("direct", "192.168.1.23:41641", None)
    assert (mac.rx_bytes, mac.tx_bytes) == (1800, 412)
    assert (phone.connection, phone.relay, phone.endpoint) == ("relay", "ams", None)
    assert (tv.connection, tv.relay) == ("idle", None)
    assert tv.exit_node and not mac.exit_node


def test_parse_tailnet_keeps_last_seen_for_offline_devices_only():
    peers = {p.name: p for p in tailscale.parse_tailnet(TAILNET_STATUS, NOW).peers}

    assert peers["desk-pc"].last_seen == datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
    assert peers["desk-pc"].connection is None and not peers["desk-pc"].online
    assert peers["pim-macbook"].last_seen is None


def test_parse_tailnet_lists_online_first_and_skips_mullvad_nodes():
    net = tailscale.parse_tailnet(TAILNET_STATUS, NOW)

    assert [p.name for p in net.peers] == ["appletv", "pim-iphone", "pim-macbook", "desk-pc"]


def test_parse_tailnet_passes_health_warnings_through():
    assert tailscale.parse_tailnet(TAILNET_STATUS, NOW).health == [
        "Tailscale can't reach the configured DNS servers."
    ]
    healthy = {**TAILNET_STATUS, "Health": None}
    assert tailscale.parse_tailnet(healthy, NOW).health == []


def test_parse_tailnet_without_peers_or_a_name():
    alone = {
        "Self": {"DNSName": "nas.tail1234.ts.net.", "HostName": "nas"},
        "MagicDNSSuffix": "tail1234.ts.net",
    }
    assert tailscale.parse_tailnet(alone, NOW).peers == []
    with pytest.raises(ValueError):
        tailscale.parse_tailnet({}, NOW)


def test_collect_tailnet_raises_without_the_socket_so_the_last_one_goes_stale(tmp_path):
    cfg = {"tailscale": {"socket": str(tmp_path / "ts.sock")}}

    with pytest.raises(FileNotFoundError):
        asyncio.run(tailscale.collect_tailnet(cfg))
