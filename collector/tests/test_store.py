from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Service


def test_cache_round_trip_and_overwrite(store):
    assert store.get_cache("nas") is None

    store.put_cache("nas", {"v": 1})
    store.put_cache("nas", {"v": 2})

    assert store.get_cache("nas") == {"v": 2}


def test_prune_drops_samples_older_than_retention(store):
    now = datetime.now(UTC)
    store.put_nas_sample(now - timedelta(hours=30), 1, 1, 1.0, 1.0, 40.0)
    store.put_nas_sample(now - timedelta(hours=1), 2, 2, 2.0, 2.0, 41.0)

    assert store.prune_nas_samples() == 1
    remaining = store.recent_nas_samples(now - timedelta(days=7))
    assert [r["rx_bytes"] for r in remaining] == [2]


def test_storage_history_keeps_one_row_per_day(store):
    store.put_storage_sample("2026-09-01", "/volume1", 10)
    store.put_storage_sample("2026-09-01", "/volume1", 12)
    store.put_storage_sample("2026-09-02", "/volume1", 15)
    store.put_storage_sample("2026-09-02", "/volume2", 99)

    rows = store.storage_history("/volume1")

    assert [(r["date"], r["used_bytes"]) for r in rows] == [
        ("2026-09-01", 12),
        ("2026-09-02", 15),
    ]


def _svc(id_: str, group: str = "Media") -> Service:
    return Service(id=id_, name=id_.title(), group=group, port=8000)


def test_seed_services_keeps_order_and_only_fills_an_empty_table(store):
    assert store.seed_services([_svc("b"), _svc("a", "Apps"), _svc("c")]) is True

    assert [s.id for s in store.list_services()] == ["b", "a", "c"]
    assert store.list_services()[1].group == "Apps"

    # A second seed (next restart, or a changed config.yaml) must not touch
    # a catalog that exists, since the app may have edited it.
    assert store.seed_services([_svc("x")]) is False
    assert [s.id for s in store.list_services()] == ["b", "a", "c"]
