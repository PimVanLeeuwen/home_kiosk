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
