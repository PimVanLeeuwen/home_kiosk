from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.models import Service
from app.sources import services
from app.store import Store

ICON_DIR = Path(__file__).resolve().parents[2] / "web" / "src" / "assets" / "icons"

# The catalog as it was with links but before icons.
LINKS_SCHEMA = """
CREATE TABLE service (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, grp TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '', port INTEGER, path TEXT NOT NULL DEFAULT '/',
    url TEXT, container TEXT, widget TEXT, sort INTEGER NOT NULL
);
INSERT INTO service VALUES ('jellyfin', 'Jellyfin', 'Media', '', 8096, '/', NULL, 'jellyfin',
                            'jellyfin', 0);
INSERT INTO service VALUES ('mine', 'My app', 'Apps', '', 9000, '/', NULL, NULL, NULL, 1);
"""

CFG = {"services": [{"group": "Media", "items": [
    {"id": "jellyfin", "name": "Jellyfin", "port": 8096, "icon": "jellyfin"},
    {"id": "immich", "name": "Immich", "port": 2283, "icon": "immich"},
]}]}


def test_icons_are_added_to_an_existing_catalog_once(tmp_path):
    path = tmp_path / "links.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(LINKS_SCHEMA)

    store = Store(path)
    assert (store.catalog_upgraded, store.catalog_icons_added) == (False, True)
    assert services.prepare(store, CFG) == "service catalog icons added for 1 entries"

    icons = {s.id: s.icon for s in store.list_services()}
    # Known ids get their default; the owner's own entry keeps letters.
    assert icons == {"jellyfin": "jellyfin", "mine": None}

    # Removing an icon later sticks: the fill only runs on the upgrade.
    jellyfin = store.list_services()[0].model_copy(update={"icon": None})
    store.update_service(jellyfin)
    reopened = Store(path)
    assert reopened.catalog_icons_added is False
    assert services.prepare(reopened, CFG) == "service catalog unchanged"
    assert reopened.list_services()[0].icon is None


def test_a_catalog_from_before_links_gets_both_upgrades(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE service (id TEXT PRIMARY KEY, name TEXT NOT NULL, grp TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '', port INTEGER NOT NULL,
                path TEXT NOT NULL DEFAULT '/', container TEXT, widget TEXT,
                sort INTEGER NOT NULL);
            INSERT INTO service VALUES ('jellyfin', 'Jellyfin', 'Media', '', 8096, '/',
                                        NULL, NULL, 0);
        """)
    cfg = {"services": CFG["services"] + [{"group": "Links", "items": [
        {"id": "trash-guides", "name": "TRaSH", "url": "https://trash-guides.info",
         "icon": "trash-guides"},
    ]}]}

    store = Store(path)
    message = services.prepare(store, cfg)

    assert message == (
        "service catalog upgraded for links; added trash-guides; icons added for 1 entries"
    )
    assert {s.id: s.icon for s in store.list_services()} == {
        "jellyfin": "jellyfin", "trash-guides": "trash-guides",
    }


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = {}
    store.seed_services([Service(id="jellyfin", name="Jellyfin", group="Media", port=8096)])
    return TestClient(main.app, headers={"origin": "http://testserver"})


def test_settings_sets_and_clears_an_icon(client):
    body = {"name": "Jellyfin", "group": "Media", "port": 8096, "icon": "jellyfin"}
    assert client.put("/api/settings/services/jellyfin", json=body).json()["services"][0][
        "icon"] == "jellyfin"

    cleared = client.put("/api/settings/services/jellyfin", json={**body, "icon": ""}).json()
    assert cleared["services"][0]["icon"] is None


@pytest.mark.parametrize("icon", ["../etc/passwd", "Jellyfin", "a b", "x" * 41])
def test_settings_rejects_icon_names_that_are_not_slugs(client, icon):
    body = {"name": "Jellyfin", "group": "Media", "port": 8096, "icon": icon}

    assert client.put("/api/settings/services/jellyfin", json=body).status_code == 422


def test_every_icon_in_the_shipped_config_exists_in_the_web_app():
    files = {p.stem for p in ICON_DIR.iterdir() if p.suffix in (".svg", ".png")}
    named = {s.icon for s in services.seed(config.load(config.DEFAULT_PATH)) if s.icon}

    assert named, "the config names no icons"
    assert named <= files, f"missing icon files: {named - files}"
