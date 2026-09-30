from __future__ import annotations

import pytest

from app.store import Store


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(tmp_path / "test.db")
