from __future__ import annotations

from datetime import UTC, datetime, timedelta


def test_cache_round_trip_and_overwrite(store):
    assert store.get_cache("nas") is None

    store.put_cache("nas", {"v": 1})
    store.put_cache("nas", {"v": 2})

    assert store.get_cache("nas") == {"v": 2}


def test_recent_snapshots_are_oldest_first_and_limited(store):
    for day in range(1, 6):
        store.put_snapshot(f"2026-09-0{day}", day * 100.0, "EUR")

    rows = store.recent_snapshots(limit=3)

    assert [r["date"] for r in rows] == ["2026-09-03", "2026-09-04", "2026-09-05"]


def test_snapshot_same_day_overwrites(store):
    store.put_snapshot("2026-09-01", 100.0, "EUR")
    store.put_snapshot("2026-09-01", 150.0, "EUR")

    assert [r["total_value"] for r in store.recent_snapshots()] == [150.0]


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
