from __future__ import annotations

from app.models import ContainerState, Service
from app.sources import services

CONTAINERS = {
    "jellyfin": ContainerState(name="jellyfin", state="running", health="healthy"),
    "sonarr": ContainerState(name="sonarr", state="running"),
    "radarr": ContainerState(name="radarr", state="exited"),
    "immich_server": ContainerState(name="immich_server", state="running", health="unhealthy"),
    "tracearr": ContainerState(name="tracearr", state="running", health="starting"),
}


def test_status_for_each_container_state():
    assert services.status_for("jellyfin", CONTAINERS) == "up"
    assert services.status_for("sonarr", CONTAINERS) == "up"
    assert services.status_for("radarr", CONTAINERS) == "down"
    assert services.status_for("immich_server", CONTAINERS) == "unhealthy"
    assert services.status_for("tracearr", CONTAINERS) == "starting"
    assert services.status_for("gone", CONTAINERS) == "missing"


def test_status_unknown_without_container_or_list():
    assert services.status_for(None, CONTAINERS) == "unknown"
    assert services.status_for("jellyfin", None) == "unknown"


def _svc(id_: str, group: str, container: str | None = None) -> Service:
    return Service(id=id_, name=id_.title(), group=group, port=1, container=container)


def test_build_groups_in_catalog_order_with_status():
    catalog = [
        _svc("jellyfin", "Media", "jellyfin"),
        _svc("sonarr", "Arr", "sonarr"),
        _svc("immich", "Media", "immich_server"),
    ]
    cache = {
        "as_of": "2026-09-30T12:00:00+00:00",
        "stale": False,
        "containers": [c.model_dump() for c in CONTAINERS.values()],
    }

    result = services.build(catalog, cache)

    assert [g.name for g in result.groups] == ["Media", "Arr"]
    assert [(s.id, s.status) for s in result.groups[0].services] == [
        ("jellyfin", "up"),
        ("immich", "unhealthy"),
    ]
    assert result.stale is False
    assert result.as_of.isoformat() == "2026-09-30T12:00:00+00:00"


def test_build_without_container_list_is_stale_and_unknown():
    result = services.build([_svc("jellyfin", "Media", "jellyfin")], None)

    assert result.as_of is None
    assert result.stale is True
    assert result.groups[0].services[0].status == "unknown"


def test_seed_reads_groups_and_defaults():
    cfg = {
        "services": [
            {
                "group": "Apps",
                "items": [
                    {"id": "couchdb", "name": "CouchDB", "port": 5984, "path": "/_utils"},
                    {"id": "tandoor", "name": "Tandoor", "port": 8090, "container": "tandoor"},
                ],
            }
        ]
    }

    seeded = services.seed(cfg)

    assert [(s.id, s.group, s.path, s.container) for s in seeded] == [
        ("couchdb", "Apps", "/_utils", None),
        ("tandoor", "Apps", "/", "tandoor"),
    ]


def test_the_shipped_config_seeds_a_valid_catalog():
    from app import config

    seeded = services.seed(config.load())

    ids = [s.id for s in seeded]
    assert len(ids) == len(set(ids))
    assert all(1 <= s.port <= 65535 for s in seeded)
