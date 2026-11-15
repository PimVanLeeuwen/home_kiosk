from __future__ import annotations

import pytest

from app.alerts import core, rules
from app.store import Store


@pytest.fixture
def store(tmp_path) -> Store:
    store = Store(tmp_path / "test.db")
    # As the app does at start-up: every panel answer reads alerts and their settings.
    core.ensure_tables(store)
    rules.ensure_tables(store)
    return store


@pytest.fixture(autouse=True)
def _testserver_is_a_hub_name(monkeypatch):
    # FastAPI's TestClient sends "Host: testserver"; the app only answers to its own
    # names (security.KnownHosts).
    from app import security

    monkeypatch.setattr(security, "BUILT_IN_HOSTS", {*security.BUILT_IN_HOSTS, "testserver"})
