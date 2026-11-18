from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app import main
from app.sources import incoming

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)  # 10:00 in Amsterdam


def touch(path, when):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(b"x" * 10)
    stamp = when.timestamp()
    os.utime(path, (stamp, stamp))


def source(path, **extra):
    return {"name": "family", "label": "Family NAS", "path": str(path), "max_days": 3, **extra}


def test_a_night_runs_from_noon_to_noon():
    assert incoming.night_of(datetime(2026, 11, 17, 21, 30, tzinfo=UTC), ZONE) == date(2026, 11, 17)
    # 00:40 local the next morning still belongs to the evening before.
    assert incoming.night_of(datetime(2026, 11, 17, 23, 40, tzinfo=UTC), ZONE) == date(2026, 11, 17)
    assert incoming.night_of(datetime(2026, 11, 18, 11, 0, tzinfo=UTC), ZONE) == date(2026, 11, 18)


def test_the_newest_change_size_and_nights_come_from_the_files(tmp_path):
    root = tmp_path / "family"
    first = datetime(2026, 11, 14, 21, 40, tzinfo=UTC)  # the night of the 14th
    touch(root / "Server.hbk" / "Pool" / "0" / "a.bucket", first)
    second = datetime(2026, 11, 15, 22, 0, tzinfo=UTC)
    touch(root / "Server.hbk" / "Pool" / "0" / "b.bucket", second)
    last = datetime(2026, 11, 17, 23, 10, tzinfo=UTC)  # after midnight: the night of the 17th
    touch(root / "Server.hbk" / "Control" / "version", last)
    for folder in [root / "Server.hbk" / "Pool" / "0", root / "Server.hbk" / "Pool",
                   root / "Server.hbk" / "Control", root / "Server.hbk", root]:
        os.utime(folder, (first.timestamp(), first.timestamp()))

    backup = incoming.read(source(root, at="22:30"), NOW, ZONE)

    assert backup.present and backup.error is None
    assert backup.last_change == last
    assert (backup.files, backup.bytes) == (3, 30)
    assert backup.at == "22:30"
    # The 16th sent nothing. Tonight (the 18th) has not started yet, and nothing
    # before the first night the folder existed is shown.
    assert [(n.night.day, n.ok) for n in backup.nights] == [
        (17, True), (16, False), (15, True), (14, True)]


def test_tonight_shows_once_something_arrived(tmp_path):
    root = tmp_path / "family"
    touch(root / "a", NOW - timedelta(days=2))
    later = datetime(2026, 11, 18, 21, 50, tzinfo=UTC)
    touch(root / "b", later)
    os.utime(root, ((NOW - timedelta(days=2)).timestamp(),) * 2)

    backup = incoming.read(source(root), later + timedelta(minutes=5), ZONE)

    assert (backup.nights[0].night, backup.nights[0].ok) == (date(2026, 11, 18), True)


def test_a_missing_folder_is_reported_without_its_path(tmp_path):
    backup = incoming.read(source(tmp_path / "nowhere"), NOW, ZONE)

    assert not backup.present
    assert backup.error == "FileNotFoundError 2"
    assert backup.last_change is None and backup.nights == []


def test_collect_reads_every_configured_source_and_none_without_config(tmp_path):
    touch(tmp_path / "family" / "a", NOW)
    cfg = {"timezone": "Europe/Amsterdam", "incoming_backups": [source(tmp_path / "family")]}

    result = asyncio.run(incoming.collect(cfg))

    assert [s.name for s in result.sources] == ["family"]
    assert asyncio.run(incoming.collect({})).sources == []


def test_the_api_serves_the_cached_payload(store):
    main.app.state.store = store
    main.app.state.config = {}
    client = TestClient(main.app)
    assert client.get("/api/incoming-backups").status_code == 503

    store.put_cache(incoming.CACHE_KEY, {"as_of": NOW.isoformat(), "stale": False, "sources": []})

    assert client.get("/api/incoming-backups").json()["sources"] == []
