from __future__ import annotations

import asyncio

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
