from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import desk_boards, main
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
    desk_boards.ensure_tables(store)
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


def test_a_failed_or_old_restore_check_is_a_problem():
    settings = {"hours": 26, "restore_days": 45}

    def checks(ok, days_ago, last_days_ago):
        last = (NOW - timedelta(days=last_days_ago)).isoformat()
        return {"restore_checks": [{
            "finished": (NOW - timedelta(days=days_ago)).isoformat(), "ok": ok,
            "checks": [{"name": "download:databases", "ok": True, "detail": "identical"},
                       {"name": "ghostfolio", "ok": ok,
                        "detail": "ok" if ok else "pg_restore failed"}],
        }], "last_verified": last}

    def judge(dumps):
        return rules.backup_missing(None, nas_payload(), settings, NOW, dumps=dumps)

    assert judge(checks(True, 9, 9)) == []
    assert judge({"restore_checks": [], "last_verified": None}) == []  # never run: no opinion

    (failed,) = judge(checks(False, 1, 32))
    assert (failed.key, failed.title, failed.body) == (
        "backup_missing:restore-check", "Restore check failed, or none passed in 45 days",
        "Last good check: Sun 30 Aug 10:00\nghostfolio: pg_restore failed")
    (old,) = judge(checks(True, 50, 50))
    assert old.key == "backup_missing:restore-check"


def test_a_token_warns_at_14_days_and_again_at_3():
    settings = {"days": 14}

    def judge(days_left, owners=("Mine", "GEWIS")):
        token = {"owners": list(owners), "checked": True,
                 "expires_at": (NOW + timedelta(days=days_left)).isoformat()}
        repos = {"tokens": [token, {"owners": ["Hubble"], "expires_at": None}]}
        return rules.token_expiry(repos, settings, NOW)

    assert judge(20) == []
    (warn,) = judge(13.5)
    assert (warn.key, warn.severity, warn.title) == (
        "token_expiry:Mine and GEWIS:14", "warning",
        "GitHub token for Mine and GEWIS expires in 13 days")
    assert warn.body.startswith("Valid until Wed 14 Oct 2026.")
    (final,) = judge(2.5, owners=("Hubble",))
    assert (final.key, final.severity) == ("token_expiry:Hubble:3", "error")
    (gone,) = judge(-1)
    assert gone.title == "GitHub token for Mine and GEWIS expired on Wed 30 Sep"
    assert rules.token_expiry(None, settings, NOW) is None


def test_the_storage_box_above_the_threshold():
    box = {"storage_box": {"used_pct": 86.4, "free": 150_000_000_000, "total": 1_099_511_627_776}}

    (p,) = rules.storage_box(box, {"threshold_pct": 85})
    assert (p.key, p.severity, p.title, p.body) == (
        "storage_box", "warning", "The storage box is 86% full", "150,0 GB left of 1,1 TB")
    assert rules.storage_box(box, {"threshold_pct": 90}) == []
    assert rules.storage_box({"storage_box": None}, {"threshold_pct": 85}) == []
    assert rules.storage_box(None, {"threshold_pct": 85}) is None


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


def outside(state="ok", stale=False, incidents=(), key="cloudflare"):
    return {"key": key, "name": "Cloudflare", "url": "https://www.cloudflarestatus.com",
            "state": state, "stale": stale, "incidents": list(incidents),
            "as_of": NOW.isoformat()}


TUNNEL = {"title": "Tunnel errors", "impact": "degraded", "url": "https://stspg.io/x"}
MAINTENANCE = {"title": "AMS maintenance", "impact": "maintenance", "url": "https://m"}


def test_an_outside_problem_is_a_warning_with_its_incident():
    (p,) = rules.outside_services(
        {"services": [outside("degraded", incidents=[MAINTENANCE, TUNNEL]), outside(key="gh")]},
        set())

    assert (p.key, p.severity) == ("outside_services:cloudflare", "warning")
    assert (p.title, p.body) == ("Cloudflare: Tunnel errors",
                                 "Degraded on their status page.\nhttps://stspg.io/x")


def test_outside_maintenance_and_unread_pages_open_nothing():
    status = {"services": [outside("maintenance", incidents=[MAINTENANCE]),
                           outside("unknown", stale=True, key="hz")]}

    assert rules.outside_services(status, set()) == []
    assert rules.outside_services(None, set()) is None


def test_an_unread_page_keeps_its_open_outside_incident():
    status = {"services": [outside("ok", stale=True)]}

    (p,) = rules.outside_services(status, {"outside_services:cloudflare"})
    assert p.key == "outside_services:cloudflare"


def test_an_outside_incident_starts_and_resolves_once(rule_store):
    def put(state, incidents=(), at=NOW):
        rule_store.put_cache("outside_services", {
            "as_of": at.isoformat(), "stale": False,
            "services": [outside(state, incidents=incidents)]})

    put("outage", [TUNNEL | {"impact": "outage"}])
    assert run_check(rule_store) == [
        "<b>WARNING</b> · <b>Cloudflare: Tunnel errors</b>\n"
        "Outage on their status page.\nhttps://stspg.io/x"]

    later = NOW + timedelta(minutes=50)
    put("ok", at=later)
    assert run_check(rule_store, later) == [
        "<b>OK</b> · <b>Resolved: Cloudflare: Tunnel errors</b>\nafter 50 min"]


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


# --- Apple devices -----------------------------------------------------------------------


def apple_payload(offline_since=None, at=NOW, stale=False):
    bath = {"id": "badkamer", "name": "Badkamer", "kind": "homepod_mini",
            "online": offline_since is None, "offline_since": offline_since, "thread": True}
    return {"as_of": at.isoformat(), "stale": stale, "rooms": [
        {"id": "bathroom", "name": "Bathroom", "devices": [bath], "playing": None}]}


def test_an_apple_device_offline_for_ten_minutes_is_a_warning():
    settings = rules.DEFAULT_RULES["apple_offline"]
    since = (NOW - timedelta(minutes=12)).isoformat()

    (p,) = rules.apple_offline(apple_payload(since), settings, NOW)

    assert (p.key, p.severity) == ("apple_offline:badkamer", "warning")
    assert p.title == "Badkamer is offline"
    assert rules.apple_offline(apple_payload((NOW - timedelta(minutes=9)).isoformat()),
                               settings, NOW) == []
    assert rules.apple_offline(apple_payload(), settings, NOW) == []
    assert rules.apple_offline(None, settings, NOW) is None


def test_an_apple_device_warns_once_and_resolves_when_back(rule_store):
    rule_store.put_cache("apple", apple_payload((NOW - timedelta(minutes=10)).isoformat()))
    assert run_check(rule_store) == [
        "<b>WARNING</b> · <b>Badkamer is offline</b>\nNot answering in the Bathroom for 10 min."]
    later = NOW + timedelta(minutes=5)
    rule_store.put_cache("apple", apple_payload((NOW - timedelta(minutes=10)).isoformat(), later))
    assert run_check(rule_store, later) == []

    back = NOW + timedelta(minutes=20)
    rule_store.put_cache("apple", apple_payload(at=back))
    assert run_check(rule_store, back) == [
        "<b>OK</b> · <b>Resolved: Badkamer is offline</b>\nafter 20 min"]


def test_a_stale_apple_answer_never_resolves_the_warning(rule_store):
    rule_store.put_cache("apple", apple_payload((NOW - timedelta(minutes=10)).isoformat()))
    run_check(rule_store)

    later = NOW + timedelta(minutes=5)
    rule_store.put_cache("apple", apple_payload(at=later, stale=True))

    assert run_check(rule_store, later) == []
    assert "apple_offline:badkamer" in rules.open_incidents(rule_store)


def test_the_apple_minutes_can_be_changed_in_settings(rule_store):
    main.app.state.store = rule_store
    client = TestClient(main.app, headers={"origin": "http://testserver"})

    saved = client.put("/api/alerts/rules",
                       json={"apple_offline": {"enabled": True, "offline_minutes": 30}})

    assert saved.json()["rules"]["apple_offline"] == {"enabled": True, "offline_minutes": 30}
    assert saved.json()["labels"]["apple_offline"] == "Apple devices"


def test_the_train_minutes_can_be_changed_in_settings(rule_store):
    main.app.state.store = rule_store
    client = TestClient(main.app, headers={"origin": "http://testserver"})

    saved = client.put("/api/alerts/rules", json={"train": {"enabled": True, "late_minutes": 5}})

    assert saved.json()["rules"]["train"] == {"enabled": True, "late_minutes": 5}
    assert rules.rule_settings(rule_store)["train"]["late_minutes"] == 5
    too_late = {"train": {"enabled": True, "late_minutes": 61}}
    assert client.put("/api/alerts/rules", json=too_late).status_code == 422


# --- desk panels ----------------------------------------------------------------------

BOARD = "e8:f6:0a:e4:42:b0"


def board(panel="now", quiet_minutes=0, mac=BOARD):
    seen = NOW - timedelta(minutes=quiet_minutes)
    return desk_boards.Board(mac=mac, panel=panel, first_seen=seen, last_seen=seen,
                             firmware="f4da96d")


def test_a_desk_panel_quiet_for_ten_minutes_is_a_warning():
    settings = rules.DEFAULT_RULES["desk_panels"]
    (p,) = rules.desk_panels([board(quiet_minutes=12)], settings, NOW)
    assert (p.key, p.severity) == (f"desk_panels:{BOARD}", "warning")
    assert p.title == "The Now panel is quiet"
    assert rules.desk_panels([board(quiet_minutes=9)], settings, NOW) == []
    # A board on the bench, without a panel, is nobody's concern.
    assert rules.desk_panels([board(panel=None, quiet_minutes=60)], settings, NOW) == []


def test_a_quiet_desk_panel_warns_once_and_resolves_when_it_asks_again(rule_store):
    desk_boards.check_in(rule_store, BOARD, "f4da96d", NOW - timedelta(minutes=10))
    desk_boards.assign(rule_store, BOARD, "home")
    assert run_check(rule_store) == [
        "<b>WARNING</b> · <b>The Home panel is quiet</b>\nBoard e8:f6:0a:e4:42:b0 has not asked "
        "the hub for 10 min: off, out of Wi-Fi reach, or stuck."]
    assert run_check(rule_store, NOW + timedelta(minutes=5)) == []

    back = NOW + timedelta(minutes=15)
    desk_boards.check_in(rule_store, BOARD, "f4da96d", back)
    assert run_check(rule_store, back) == [
        "<b>OK</b> · <b>Resolved: The Home panel is quiet</b>\nafter 15 min"]
