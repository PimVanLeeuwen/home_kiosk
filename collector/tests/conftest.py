from __future__ import annotations

import pytest

from app.alerts import rules
from app.store import Store


@pytest.fixture
def store(tmp_path) -> Store:
    store = Store(tmp_path / "test.db")
    rules.ensure_tables(store)  # as the app does at start-up: every panel answer reads alerts
    return store
