from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import Service
from app.sources import services
from app.store import Store

OLD_SCHEMA = """
CREATE TABLE service (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, grp TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '', port INTEGER NOT NULL,
    path TEXT NOT NULL DEFAULT '/', container TEXT, widget TEXT, sort INTEGER NOT NULL
);
INSERT INTO service VALUES ('jellyfin', 'Jellyfin', 'Media', 'Media server', 8096, '/',
                            'jellyfin', 'jellyfin', 0);
INSERT INTO service VALUES ('couchdb', 'CouchDB', 'Apps', '', 5984, '/_utils', 'couchdb',
                            NULL, 1);
"""

CFG = {
    "services": [
        {"group": "Media", "items": [
            {"id": "jellyfin", "name": "Jellyfin", "port": 8096, "container": "jellyfin"},
        ]},
        {"group": "Links", "items": [
            {"id": "trash-guides", "name": "TRaSH Guides", "url": "https://trash-guides.info"},
            {"id": "hetzner-robot", "name": "Hetzner Robot", "url": "https://robot.hetzner.com"},
        ]},
    ]
}


@pytest.fixture
def old_db(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(OLD_SCHEMA)
    return path


def test_an_old_catalog_is_upgraded_in_place(old_db):
    store = Store(old_db)

    assert store.catalog_upgraded is True
    catalog = store.list_services()
    assert [(s.id, s.port, s.path, s.url, s.container) for s in catalog] == [
        ("jellyfin", 8096, "/", None, "jellyfin"),
        ("couchdb", 5984, "/_utils", None, "couchdb"),
    ]
    # Links can be stored now: port is no longer NOT NULL.
    store.add_service(Service(id="x", name="X", group="Links", url="https://e.com"))
    assert store.list_services()[-1].port is None

    assert Store(old_db).catalog_upgraded is False  # only once


def test_prepare_adds_default_links_to_an_upgraded_catalog_once(old_db):
    store = Store(old_db)

    message = services.prepare(store, CFG)

    assert message == "service catalog upgraded for links; added trash-guides, hetzner-robot"
    assert [(s.id, s.group) for s in store.list_services()] == [
        ("jellyfin", "Media"), ("couchdb", "Apps"),
        ("trash-guides", "Links"), ("hetzner-robot", "Links"),
    ]
    # A deleted link does not come back on the next start.
    store.delete_service("trash-guides")
    assert services.prepare(Store(old_db), CFG) == "service catalog unchanged"
    assert "trash-guides" not in {s.id for s in Store(old_db).list_services()}


def test_prepare_seeds_a_new_catalog_with_links(tmp_path):
    store = Store(tmp_path / "new.db")

    assert store.catalog_upgraded is False
    assert services.prepare(store, CFG) == "service catalog seeded from config.yaml"
    assert [s.id for s in store.list_services()] == ["jellyfin", "trash-guides", "hetzner-robot"]


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = {}
    store.seed_services([Service(id="jellyfin", name="Jellyfin", group="Media", port=8096)])
    return TestClient(main.app, headers={"origin": "http://testserver"})


def test_settings_accepts_a_link(client):
    body = client.post(
        "/api/settings/services",
        json={"name": "TRaSH Guides", "group": "Links", "url": " https://trash-guides.info "},
    ).json()

    link = body["services"][-1]
    assert (link["id"], link["url"], link["port"], link["container"]) == (
        "trash-guides", "https://trash-guides.info", None, None,
    )


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"port": 80, "url": "https://e.com"}, "not both"),
        ({}, "either a port"),
        ({"url": "javascript:alert(1)"}, "http:// or https://"),
        ({"url": "ftp://files.example"}, "http:// or https://"),
        ({"url": "https://"}, "http:// or https://"),
        ({"url": "https://e.com", "container": "x"}, "no container or widget"),
        ({"url": "https://e.com", "widget": "jellyfin"}, "no container or widget"),
    ],
)
def test_settings_rejects_bad_links(client, fields, reason):
    resp = client.post("/api/settings/services", json={"name": "X", "group": "Links", **fields})

    assert resp.status_code == 422
    assert reason in str(resp.json()["detail"])


def test_a_service_can_become_a_link(client):
    body = client.put(
        "/api/settings/services/jellyfin",
        json={"name": "Jellyfin docs", "group": "Media", "url": "https://jellyfin.org/docs"},
    ).json()

    entry = body["services"][0]
    assert (entry["port"], entry["url"]) == (None, "https://jellyfin.org/docs")


def test_links_have_unknown_status_and_no_widget(store):
    store.seed_services([Service(id="t", name="T", group="Links", url="https://t.example")])

    result = services.build(store.list_services(), None, None)

    link = result.groups[0].services[0]
    assert (link.status, link.stats, link.url) == ("unknown", None, "https://t.example")
