from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.alerts import core, rules
from app.alerts.telegram import Telegram
from app.models import Service
from app.sources import docker

CFG = {
    "timezone": "Europe/Amsterdam",
    "nas": {"docker_socket": "/nonexistent.sock"},
    "telegram": {
        "token": "t",
        "chats": {"nas": {"id": "-1", "label": "NAS"}, "portfolio": {"id": "-2", "label": "P"}},
    },
}
NOW = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)  # noon in Amsterdam: no quiet hours


class Sent:
    def __init__(self):
        self.texts = []

    def client(self):
        def handler(request):
            self.texts.append(json.loads(request.content)["text"])
            return httpx.Response(200, json={"ok": True, "result": {}})

        return Telegram("t", transport=httpx.MockTransport(handler))


def pool(name, used_pct):
    return {
        "name": name,
        "used_pct": used_pct,
        "free_bytes": 0.5e12,
        "total_bytes": 6e12,
        "used_bytes": 5.5e12,
    }


def nas_payload(pools=(), disks=(), backup=None, at=NOW):
    return {
        "as_of": at.isoformat(),
        "stale": False,
        "storage": {"pools": list(pools)},
        "disks": list(disks),
        "backup": backup or {"status": "ok", "at": (at - timedelta(hours=2)).isoformat()},
    }


@pytest.fixture
def rule_store(store):
    core.ensure_tables(store)
    rules.ensure_tables(store)
    return store


def run_check(store, now=NOW, dies=None):
    sent = Sent()
    asyncio.run(rules.check(CFG, store, now=now, telegram=sent.client(), dies=dies or {}))
    return sent.texts


# --- the rules on their own -----------------------------------------------------------


def test_disk_space_flags_pools_over_the_threshold():
    nas = nas_payload([pool("volume2", 92.4), pool("volume1", 16.8)])

    (problem,) = rules.disk_space(nas, {"threshold_pct": 90})

    assert (problem.key, problem.title, problem.body) == (
        "disk_space:volume2",
        "volume2 is 92% full",
        "500,0 GB left of 6,0 TB",
    )
    assert rules.disk_space(None, {"threshold_pct": 90}) is None


def test_smart_warnings_and_failures():
    nas = nas_payload(
        disks=[
            {"name": "sda", "smart": "ok"},
            {"name": "sdb", "smart": "warn"},
            {"name": "sdc", "smart": "fail"},
        ]
    )

    found = {(p.key, p.severity) for p in rules.smart(nas, {})}

    assert found == {("smart:sdb", "warning"), ("smart:sdc", "error")}


def test_container_health_waits_out_short_blips():
    containers = {
        "containers": [{"name": "immich_server", "state": "running", "health": "unhealthy"}]
    }
    pending: dict[str, str] = {}
    settings = rules.DEFAULT_RULES["container_health"]

    assert rules.container_health(containers, [], {}, pending, settings, NOW) == []
    later = rules.container_health(
        containers, [], {}, pending, settings, NOW + timedelta(minutes=6)
    )
    assert [(p.title, p.body) for p in later] == [("immich_server is unhealthy", "for 6 min")]

    healthy = {"containers": [{"name": "immich_server", "state": "running", "health": "healthy"}]}
    rules.container_health(healthy, [], {}, pending, settings, NOW + timedelta(minutes=7))
    assert pending == {}


def test_container_health_flags_catalog_services_that_are_down_and_restart_loops():
    containers = {"containers": [{"name": "sonarr", "state": "exited", "health": None}]}
    catalog = [
        Service(id="sonarr", name="Sonarr", group="Arr", port=8989, container="sonarr"),
        Service(id="gone", name="Gone", group="Arr", port=1, container="gone"),
        Service(id="docs", name="Docs", group="Links", url="https://e.com"),
    ]
    pending = {
        "down:sonarr": (NOW - timedelta(minutes=10)).isoformat(),
        "down:gone": (NOW - timedelta(minutes=10)).isoformat(),
    }

    problems = rules.container_health(
        containers,
        catalog,
        {"tracearr": 4, "jellyfin": 1},
        pending,
        rules.DEFAULT_RULES["container_health"],
        NOW,
    )

    assert {(p.key, p.severity, p.body) for p in problems} == {
        ("down:sonarr", "error", "container sonarr: exited"),
        ("down:gone", "error", "container gone: no container"),
        ("restarting:tracearr", "warning", "4 restarts in 10 min"),
    }


def test_backup_missing_per_volume_or_from_the_marker():
    settings = {"hours": 26}
    backups = {
        "volumes": [
            {"name": "volume1", "last_success": (NOW - timedelta(hours=3)).isoformat()},
            {"name": "volume3", "last_success": (NOW - timedelta(hours=30)).isoformat()},
        ]
    }
    (late,) = rules.backup_missing(backups, None, settings, NOW)
    assert late.key == "backup_missing:volume3"

    failed_marker = nas_payload(backup={"status": "fail", "at": NOW.isoformat()})
    assert [p.body for p in rules.backup_missing(None, failed_marker, settings, NOW)] == [
        "Last success: none recorded"
    ]
    assert rules.backup_missing(None, nas_payload(), settings, NOW) == []
    assert rules.backup_missing(None, None, settings, NOW) is None


def test_a_failed_or_old_dump_is_a_problem_until_a_recent_good_one():
    settings = {"hours": 26}

    def db(name, ok, hours_ago, error=None):
        last = (NOW - timedelta(hours=hours_ago)).isoformat() if hours_ago is not None else None
        return {"name": name, "label": name.capitalize(), "ok": ok, "last_success": last,
                "error": error}

    dumps = {"databases": [
        db("ghostfolio", True, 8),
        db("tandoor", False, 32, "pg_dump: connection refused"),
        db("tracearr", True, 30),
        db("hub", None, None),  # never attempted yet: no opinion
    ]}

    failed, old = rules.backup_missing(None, nas_payload(), settings, NOW, dumps=dumps)
    assert (failed.key, failed.title, failed.body) == (
        "backup_missing:db:tandoor", "No good dump of the Tandoor database",
        "Last success: Wed 30 Sep 02:00\npg_dump: connection refused")
    # No error text: that line is left out.
    assert (old.key, old.body) == ("backup_missing:db:tracearr", "Last success: Wed 30 Sep 04:00")


def test_portfolio_move_beyond_the_threshold():
    portfolio = {"total_value": 9119.0, "change": {"day_pct": -3.4}}

    (p,) = rules.portfolio_move(portfolio, {"threshold_pct": 3}, "2026-10-01")
    assert (p.key, p.title, p.body) == (
        "portfolio_move:2026-10-01",
        "Portfolio moved −3,4% today",
        "Now € 9.119",
    )
    assert (
        rules.portfolio_move(
            {"total_value": 1, "change": {"day_pct": 1.0}}, {"threshold_pct": 3}, "d"
        )
        == []
    )


# --- start and resolve -------------------------------------------------------------------


def test_one_message_when_a_problem_starts_and_one_when_it_is_resolved(rule_store):
    rule_store.put_cache("nas", nas_payload([pool("volume2", 92.4)]))

    assert run_check(rule_store) == [
        "<b>WARNING</b> · <b>volume2 is 92% full</b>\n500,0 GB left of 6,0 TB"]
    # Still full a minute later: nothing new.
    rule_store.put_cache("nas", nas_payload([pool("volume2", 92.6)], at=NOW + timedelta(minutes=1)))
    assert run_check(rule_store, NOW + timedelta(minutes=1)) == []

    later = NOW + timedelta(hours=3, minutes=12)
    rule_store.put_cache("nas", nas_payload([pool("volume2", 80.0)], at=later))
    assert run_check(rule_store, later) == [
        "<b>OK</b> · <b>Resolved: volume2 is 92% full</b>\nafter 3 h 12 min"
    ]
    assert rules.incidents(rule_store)[0]["resolved_at"] == later.isoformat()


def test_missing_or_stale_input_never_resolves_a_problem(rule_store):
    rule_store.put_cache("nas", nas_payload([pool("volume2", 92.4)]))
    run_check(rule_store)

    stale_time = NOW + timedelta(hours=1)  # the cached payload is now an hour old
    assert run_check(rule_store, stale_time) == []
    assert rules.open_incidents(rule_store).keys() == {"disk_space:volume2"}


def test_disabling_a_rule_resolves_its_incidents_quietly(rule_store):
    rule_store.put_cache("nas", nas_payload([pool("volume2", 92.4)]))
    run_check(rule_store)
    core.put_setting(rule_store, "rules", {"disk_space": {"enabled": False}})

    assert run_check(rule_store) == []
    assert rules.open_incidents(rule_store) == {}


def test_portfolio_moves_go_to_the_portfolio_chat_without_a_resolved_message(rule_store):
    core.put_setting(rule_store, "rules", {"portfolio_move": {"enabled": True}})
    rule_store.put_cache(
        "portfolio",
        {
            "as_of": NOW.isoformat(),
            "stale": False,
            "total_value": 9119.0,
            "change": {"day_pct": 3.4},
        },
    )
    run_check(rule_store)
    assert core.messages(rule_store)[0].chat == "portfolio"

    rule_store.put_cache(
        "portfolio",
        {
            "as_of": NOW.isoformat(),
            "stale": False,
            "total_value": 9000.0,
            "change": {"day_pct": 0.5},
        },
    )
    assert run_check(rule_store) == []


# --- docker events ---------------------------------------------------------------------


def test_die_counts_reads_the_event_log():
    seen = []

    def handler(request):
        seen.append(request)
        lines = [
            {"Type": "container", "Action": "die", "Actor": {"Attributes": {"name": n}}}
            for n in ["tracearr", "tracearr", "tracearr", "sonarr"]
        ]
        return httpx.Response(200, text="\n".join(json.dumps(x) for x in lines) + "\n")

    counts = asyncio.run(
        docker.die_counts(
            "/x", NOW - timedelta(minutes=10), NOW, transport=httpx.MockTransport(handler)
        )
    )

    assert counts == {"tracearr": 3, "sonarr": 1}
    params = seen[0].url.params
    assert json.loads(params["filters"]) == {"type": ["container"], "event": ["die"]}
    assert int(params["until"]) - int(params["since"]) == 600


# --- endpoints ---------------------------------------------------------------------------


def test_rules_endpoints(rule_store):
    main.app.state.store = rule_store
    client = TestClient(main.app, headers={"origin": "http://testserver"})

    assert client.get("/api/alerts/rules").json()["rules"]["disk_space"] == {
        "enabled": True,
        "threshold_pct": 90,
    }
    saved = client.put(
        "/api/alerts/rules", json={"disk_space": {"enabled": True, "threshold_pct": 85, "hours": 5}}
    )
    # Fields a rule does not have are dropped.
    assert saved.json()["rules"]["disk_space"] == {"enabled": True, "threshold_pct": 85}
    assert client.put("/api/alerts/rules", json={"nope": {"enabled": True}}).status_code == 422
    assert (
        client.put(
            "/api/alerts/rules", json={"disk_space": {"enabled": True, "threshold_pct": 0}}
        ).status_code
        == 422
    )
    assert client.get("/api/alerts/incidents").json() == []
