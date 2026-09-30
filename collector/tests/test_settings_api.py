from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import Service

SEED = [
    Service(id="jellyfin", name="Jellyfin", group="Media", port=8096, container="jellyfin"),
    Service(id="immich", name="Immich", group="Media", port=2283),
    Service(id="sonarr", name="Sonarr", group="Arr", port=8989),
    Service(id="tandoor", name="Tandoor", group="Apps", port=8090),
]

# TestClient's host is "testserver"; a same-origin browser would send this.
SAME_ORIGIN = {"origin": "http://testserver"}


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = {}
    store.seed_services(SEED)
    return TestClient(main.app, headers=SAME_ORIGIN)


def ids(body):
    return [s["id"] for s in body["services"]]


def groups(body):
    return [(s["id"], s["group"]) for s in body["services"]]


VALID = {"name": "Uptime Kuma", "group": "Monitoring", "port": 3001}


def test_lists_catalog_and_widget_choices(client):
    body = client.get("/api/settings/services").json()

    assert ids(body) == ["jellyfin", "immich", "sonarr", "tandoor"]
    assert "jellyfin" in body["widgets"]


def test_add_derives_a_unique_id_and_appends_to_the_group(client):
    body = client.post("/api/settings/services", json={**VALID, "group": "Media"}).json()
    assert ids(body) == ["jellyfin", "immich", "uptime-kuma", "sonarr", "tandoor"]

    body = client.post("/api/settings/services", json=VALID).json()
    assert ids(body)[-1] == "uptime-kuma-2"
    assert body["services"][-1]["group"] == "Monitoring"


def test_add_with_explicit_id(client):
    resp = client.post("/api/settings/services", json={**VALID, "id": "kuma"})
    assert resp.status_code == 201
    assert "kuma" in ids(resp.json())

    assert client.post("/api/settings/services", json={**VALID, "id": "kuma"}).status_code == 409
    assert client.post("/api/settings/services", json={**VALID, "id": "Bad Id"}).status_code == 422


@pytest.mark.parametrize(
    "change",
    [
        {"port": 0},
        {"port": 70000},
        {"name": "   "},
        {"name": "x" * 61},
        {"group": ""},
        {"container": "bad name!"},
        {"widget": "grafana"},
        {"path": "/has space"},
    ],
)
def test_rejects_invalid_input(client, change):
    resp = client.post("/api/settings/services", json={**VALID, **change})

    assert resp.status_code == 422


def test_normalises_path_whitespace_and_empty_optionals(client):
    body = client.post(
        "/api/settings/services",
        json={
            **VALID,
            "name": "  Uptime   Kuma ",
            "path": "status",
            "container": " ",
            "widget": "",
        },
    ).json()

    added = body["services"][-1]
    assert added["name"] == "Uptime Kuma"
    assert added["path"] == "/status"
    assert added["container"] is None
    assert added["widget"] is None


def test_update_changes_fields(client):
    body = client.put(
        "/api/settings/services/immich",
        json={"name": "Immich", "group": "Media", "port": 2283, "description": "Photos",
              "container": "immich_server", "widget": "immich"},
    ).json()

    immich = next(s for s in body["services"] if s["id"] == "immich")
    assert (immich["description"], immich["container"], immich["widget"]) == (
        "Photos", "immich_server", "immich",
    )


def test_moving_to_another_group_lands_at_its_end(client):
    body = client.put(
        "/api/settings/services/jellyfin", json={"name": "Jellyfin", "group": "Arr", "port": 8096}
    ).json()

    assert groups(body) == [
        ("immich", "Media"), ("sonarr", "Arr"), ("jellyfin", "Arr"), ("tandoor", "Apps"),
    ]


def test_update_and_delete_unknown_service_is_404(client):
    assert client.put("/api/settings/services/nope", json=VALID).status_code == 404
    assert client.delete("/api/settings/services/nope").status_code == 404


def test_delete(client):
    body = client.delete("/api/settings/services/sonarr").json()

    assert ids(body) == ["jellyfin", "immich", "tandoor"]


def test_reorder_applies_a_complete_order_and_keeps_groups_together(client):
    body = client.put(
        "/api/settings/services-order", json={"ids": ["tandoor", "immich", "sonarr", "jellyfin"]}
    ).json()

    # jellyfin joins its group-mate immich instead of splitting Media in two.
    assert ids(body) == ["tandoor", "immich", "jellyfin", "sonarr"]


@pytest.mark.parametrize(
    "order",
    [["jellyfin", "immich", "sonarr"], ["jellyfin", "immich", "sonarr", "sonarr"],
     ["jellyfin", "immich", "sonarr", "tandoor", "extra"]],
)
def test_reorder_must_list_every_service_once(client, order):
    assert client.put("/api/settings/services-order", json={"ids": order}).status_code == 409


def test_rename_group_and_merge_into_an_existing_one(client):
    body = client.put("/api/settings/groups", json={"old": "Arr", "new": "Arr stack"}).json()
    assert ("sonarr", "Arr stack") in groups(body)

    body = client.put("/api/settings/groups", json={"old": "Apps", "new": "Media"}).json()
    assert groups(body) == [
        ("jellyfin", "Media"), ("immich", "Media"), ("tandoor", "Media"), ("sonarr", "Arr stack"),
    ]

    assert client.put("/api/settings/groups", json={"old": "Nope", "new": "X"}).status_code == 404


# --- write protection ---------------------------------------------------------


def test_cross_site_writes_are_refused(client):
    evil = {"origin": "https://evil.example"}

    assert client.post("/api/settings/services", json=VALID, headers=evil).status_code == 403
    assert client.delete("/api/settings/services/sonarr", headers=evil).status_code == 403
    assert client.post("/api/save", json={"url": "https://e.com"}, headers=evil).status_code == 403
    # Nothing changed.
    assert len(client.get("/api/settings/services").json()["services"]) == 4


def test_form_posts_are_refused(client):
    resp = client.post(
        "/api/settings/services",
        content="name=x&group=y&port=1",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert resp.status_code == 415


def test_requests_without_origin_are_allowed(store):
    # curl and server-side callers send no Origin header.
    main.app.state.store = store
    store.seed_services(SEED)
    plain = TestClient(main.app)

    assert plain.post("/api/settings/services", json=VALID).status_code == 201


def test_proxy_forwarded_host_counts_as_same_origin(client):
    resp = client.post(
        "/api/settings/services",
        json=VALID,
        headers={"origin": "http://localhost:5273", "x-forwarded-host": "localhost:5273"},
    )

    assert resp.status_code == 201


def test_no_cors_headers_for_other_origins(client):
    resp = client.get("/api/services", headers={"origin": "https://evil.example"})

    assert "access-control-allow-origin" not in resp.headers


def test_containers_endpoint_serves_the_cached_list(client, store):
    assert client.get("/api/containers").status_code == 503
    store.put_cache("containers", {"as_of": "2026-09-30T12:00:00+00:00", "stale": False,
                                   "containers": [{"name": "sonarr", "state": "running",
                                                   "health": None}]})

    assert client.get("/api/containers").json()["containers"][0]["name"] == "sonarr"
