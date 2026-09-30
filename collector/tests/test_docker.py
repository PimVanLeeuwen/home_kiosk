from __future__ import annotations

import asyncio

import pytest

from app.sources import docker

RAW = [
    {"Names": ["/sonarr"], "State": "running", "Status": "Up 3 hours"},
    {"Names": ["/jellyfin"], "State": "running", "Status": "Up 2 days (healthy)"},
    {"Names": ["/tracearr"], "State": "running", "Status": "Up 5 seconds (health: starting)"},
    {"Names": ["/immich_server"], "State": "running", "Status": "Up 1 hour (unhealthy)"},
    {"Names": ["/old"], "State": "exited", "Status": "Exited (0) 3 days ago"},
    {"Names": [], "State": "running", "Status": "Up"},  # nameless: skipped
]


def test_parse_reads_name_state_and_health_sorted_by_name():
    containers = docker.parse(RAW)

    assert [(c.name, c.state, c.health) for c in containers] == [
        ("immich_server", "running", "unhealthy"),
        ("jellyfin", "running", "healthy"),
        ("old", "exited", None),
        ("sonarr", "running", None),
        ("tracearr", "running", "starting"),
    ]


def test_list_containers_is_none_without_a_socket(tmp_path):
    assert asyncio.run(docker.list_containers(str(tmp_path / "docker.sock"))) is None


def test_collect_raises_without_a_socket_so_the_last_list_goes_stale(tmp_path):
    cfg = {"nas": {"docker_socket": str(tmp_path / "docker.sock")}}

    with pytest.raises(RuntimeError):
        asyncio.run(docker.collect(cfg))
