from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import desk_boards, desk_headlines, desk_keys, main
from app.sources import readeck

from .test_desk_headlines import LEAD_ID, put

MAC, OTHER = "e8:f6:0a:e4:42:b0", "e8:f6:0a:e4:42:c8"
BROWSER = {"origin": "http://testserver"}


@pytest.fixture
def client(store):
    main.app.state.store = store
    main.app.state.config = {"timezone": "Europe/Amsterdam"}
    desk_boards.ensure_tables(store)
    put(store)
    return TestClient(main.app, headers=BROWSER)


def key_state(client, mac=MAC):
    return {b["mac"]: b["key"] for b in client.get("/api/settings/desk-boards").json()}.get(mac)


def board_with_key(client, mac=MAC, panel="now") -> str:
    client.get(f"/api/desk/board/{mac}")
    client.put(f"/api/settings/desk-boards/{mac}", json={"panel": panel})
    return client.get(f"/api/desk/board/{mac}").json()["key"]


def test_a_board_gets_its_key_once_when_it_gets_a_panel(client):
    client.get(f"/api/desk/board/{MAC}")
    assert key_state(client) == "none"
    client.put(f"/api/settings/desk-boards/{MAC}", json={"panel": "now"})
    assert key_state(client) == "pending"

    key = client.get(f"/api/desk/board/{MAC}").json()["key"]

    assert len(key) >= 40 and key_state(client) == "active"
    assert "key" not in client.get(f"/api/desk/board/{MAC}").json()
    assert desk_keys.board_for(client.app.state.store, key) == MAC


def test_taking_the_panel_away_or_moving_it_revokes_the_key(client):
    key = board_with_key(client)
    board_with_key(client, OTHER, "now")  # the Now panel moves to the other board
    assert key_state(client) == "none"
    assert desk_keys.board_for(client.app.state.store, key) is None
    client.put(f"/api/settings/desk-boards/{OTHER}", json={"panel": None})
    assert key_state(client, OTHER) == "none"


def test_settings_revokes_and_issues_a_new_key(client):
    key = board_with_key(client)
    assert client.delete(f"/api/settings/desk-boards/{MAC}/key").status_code == 200
    assert key_state(client) == "none" and desk_keys.board_for(client.app.state.store, key) is None

    assert client.post(f"/api/settings/desk-boards/{MAC}/key", json={}).status_code == 200
    new = client.get(f"/api/desk/board/{MAC}").json()["key"]
    assert new != key and key_state(client) == "active"

    client.get(f"/api/desk/board/{OTHER}")
    assert client.post(f"/api/settings/desk-boards/{OTHER}/key", json={}).status_code == 409
    other_site = TestClient(main.app, headers={"origin": "https://example.com"})
    assert other_site.delete(f"/api/settings/desk-boards/{MAC}/key").status_code == 403


def test_boards_with_a_panel_from_before_keys_get_one(store):
    desk_boards.ensure_tables(store)
    desk_boards.check_in(store, MAC, "v1")
    with store.connect() as conn:
        conn.execute("UPDATE desk_board SET panel = 'now'")
        conn.execute("DELETE FROM desk_key")
    desk_boards.ensure_tables(store)
    assert desk_keys.states(store) == {MAC: "pending"}


def test_a_tap_saves_the_story_once_with_the_boards_key(client, monkeypatch):
    calls = []

    async def fake_save(cfg, url, title=None):
        calls.append((url, title))
        return "bm1"

    monkeypatch.setattr(readeck, "save", fake_save)
    key = board_with_key(client)
    panel = TestClient(main.app, headers={"authorization": f"Bearer {key}"})

    assert panel.post("/api/desk/save", json={"article_id": LEAD_ID}).json() == {"saved": True}
    assert panel.post("/api/desk/save", json={"article_id": LEAD_ID}).status_code == 200
    assert len(calls) == 1
    stories = client.get(f"/api/desk/board/{MAC}").json()["screens"][4]["stories"]
    assert [s["saved"] for s in stories] == [True, False, False]

    assert panel.post("/api/desk/save", json={"article_id": "ffffffffffffffff"}).status_code == 404


def test_saving_needs_a_valid_key(client, monkeypatch):
    monkeypatch.setattr(readeck, "save", lambda *a, **k: pytest.fail("must not save"))
    board_with_key(client)
    no_key = TestClient(main.app)
    assert no_key.post("/api/desk/save", json={"article_id": LEAD_ID}).status_code == 401
    wrong = TestClient(main.app, headers={"authorization": "Bearer nope"})
    assert wrong.post("/api/desk/save", json={"article_id": LEAD_ID}).status_code == 401


def test_readeck_trouble_is_a_short_reason(client, monkeypatch):
    async def refused(cfg, url, title=None):
        raise readeck.SaveError("Readeck unreachable")

    monkeypatch.setattr(readeck, "save", refused)
    key = board_with_key(client)
    panel = TestClient(main.app, headers={"authorization": f"Bearer {key}"})
    answer = panel.post("/api/desk/save", json={"article_id": LEAD_ID})
    assert answer.status_code == 502 and answer.json() == {"detail": "Readeck unreachable"}
    assert desk_headlines.headlines_screen(client.app.state.store,
                                           desk_headlines.datetime.now(desk_headlines.UTC)
                                           )["stories"][0]["saved"] is False
