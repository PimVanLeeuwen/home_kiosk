from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.sources import laundry

FIXTURES = Path(__file__).parent / "fixtures"
DRYER = json.loads((FIXTURES / "connectlife_dryer.json").read_text())
WASHER = json.loads((FIXTURES / "connectlife_washer.json").read_text())
NOW = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)
CFG = {"connectlife": {"username": "hub@example.com", "password": "secret"}}

# A throwaway 1024-bit key: the private exponent lets a test check a signature.
TEST_N = int(
    "d74d0e0cc0857571e32843a5f46535a347a6ca77f75b37e29f29c3a3fd949f446f515605806d5b70e9a35feb"
    "615dd8d961ad0dfeb09ee93e9129a22e927fa27422a0a9d8d3fee5653162c82c41eaca45d86e56b2e02ab7bc"
    "8eb0720e780ebe499faade8013f8891ce36cd994c1938c4f48cd7214cd6d3a10cc1b102e6d57f647", 16)
TEST_D = int(
    "16d6adaedc9d4ba01120ac4c666876102401a568a46ca0b9017944af98aeb356671891af73b826030c45b05f"
    "1facfcdbd268b11b5b51001d0af907a3391720fc4ef0f3e5131e0a39f79236875e5e2a32cc76a5ebf2f2611f"
    "d2563696449912efb6016debe56877660921284c6407bb4968c700588af2210638cd6e377cbf47c1", 16)


@pytest.fixture(autouse=True)
def tables(store):
    laundry.ensure_tables(store)


def unpad(cipher: bytes) -> bytes:
    block = pow(int.from_bytes(cipher, "big"), TEST_D, TEST_N).to_bytes(128, "big")
    assert block[:2] == b"\x00\x02" and 0 not in block[2:10]
    return block[block.index(b"\x00", 2) + 1:]


# --- signing -------------------------------------------------------------------------


def test_reads_connectlifes_public_key():
    n, e = laundry.rsa_key(laundry.PUBLIC_KEY)
    assert (n.bit_length(), e) == (2048, 65537)


def test_the_signature_is_the_sorted_parameters_hashed_and_encrypted():
    params = {"timeStamp": "1", "appId": "a", "accessToken": "t", "list": [1, 2]}

    out = laundry.signed(params, (TEST_N, 65537))

    assert laundry.sign_text(params) == "accessToken=t&appId=a&list=[1, 2]&timeStamp=1"
    expected = hashlib.sha256(("accessToken=t&appId=a&list=[1, 2]&timeStamp=1"
                               + laundry.SIGN_SALT).encode()).digest()
    assert unpad(base64.b64decode(out["sign"])) == expected
    # Random padding: the same input never gives the same signature twice.
    assert laundry.signed(params, (TEST_N, 65537))["sign"] != out["sign"]


# --- what a machine's numbers mean ----------------------------------------------------


def dryer(**props) -> dict:
    device = copy.deepcopy(DRYER["response"]["deviceList"][0])
    device["statusList"].update({k: str(v) for k, v in props.items()})
    return device


def washer(**props) -> dict:
    base = {"machine_status": 0, "Door_status": 3, "error_code": 0, "Selected_program_ID": 6,
            "Selected_program_remaining_time_in_minutes": 0,
            "Selected_program_total_time_in_minutes": 0}
    return {"puid": "test-washer-puid", "deviceTypeCode": "025",
            "deviceNickName": "Washing machine", "offlineState": 1,
            "statusList": {k: str(v) for k, v in (base | props).items()}}


def test_the_real_dryer_now_is_off_with_its_door_open():
    machine = laundry.read_machine(DRYER["response"]["deviceList"][0], None, NOW)

    assert (machine.name, machine.kind, machine.state, machine.online, machine.door_open) == (
        "Tumble dryer", "dryer", "idle", True, True)
    assert machine.id != "test-dryer-puid" and len(machine.id) == 10


def test_the_real_washer_after_a_cotton_wash_is_off_with_its_door_open():
    device = WASHER["response"]["deviceList"][0]

    machine = laundry.read_machine(device, None, NOW)
    running = laundry.read_machine(
        device | {"statusList": device["statusList"] | {"machine_status": "2", "Door_status": "3",
                  "Selected_program_remaining_time_in_minutes": "100"}}, None, NOW)

    assert (machine.name, machine.kind, machine.state, machine.door_open) == (
        "Washing Machine", "washer", "idle", True)
    assert (running.state, running.program, running.total_minutes) == ("running", "Cotton", 239)
    assert laundry.read_machine(washer(machine_status=2, Selected_program_ID=6), None,
                                NOW).program == "Program 6"


def test_a_running_dryer_with_its_program_and_ready_time():
    machine = laundry.read_machine(dryer(machine_status=2, Current_program_phase=2, Door_status=1,
                                         Selected_program_ID=8,
                                         Selected_program_remaining_time_in_minutes=94), None, NOW)

    assert (machine.state, machine.program, machine.remaining_minutes) == ("running", "Cotton", 94)
    assert machine.total_minutes == 163
    assert machine.ready_at == NOW + timedelta(minutes=94)


def test_a_machine_that_stops_running_is_done_until_its_door_opens():
    running = laundry.read_machine(
        washer(machine_status=2, Selected_program_remaining_time_in_minutes=3), None, NOW,
    ).model_dump(mode="json")

    stopped = laundry.read_machine(washer(machine_status=1), running, NOW + timedelta(minutes=4))
    later = laundry.read_machine(washer(machine_status=1), stopped.model_dump(mode="json"),
                                 NOW + timedelta(minutes=30))
    opened = laundry.read_machine(washer(machine_status=1, Door_status=1),
                                  later.model_dump(mode="json"), NOW + timedelta(minutes=31))

    assert (stopped.state, stopped.done_at) == ("done", NOW + timedelta(minutes=4))
    assert (later.state, later.done_at) == ("done", NOW + timedelta(minutes=4))
    assert (opened.state, opened.done_at) == ("idle", None)


def test_done_lasts_two_hours_at_most():
    done = {"state": "done", "done_at": NOW.isoformat()}

    machine = laundry.read_machine(washer(machine_status=1), done,
                                   NOW + timedelta(hours=2, minutes=1))

    assert machine.state == "idle"


def test_a_dryer_left_finished_in_standby_does_not_come_back_after_emptying():
    finished = dryer(machine_status=1, Current_program_phase=5, Door_status=1)

    after_restart = laundry.read_machine(finished, None, NOW)
    emptied = laundry.read_machine(
        dryer(machine_status=1, Current_program_phase=5, Door_status=2),
        after_restart.model_dump(mode="json"), NOW + timedelta(minutes=5))
    closed_again = laundry.read_machine(finished, emptied.model_dump(mode="json"),
                                        NOW + timedelta(minutes=6))

    assert after_restart.state == "done"
    assert emptied.state == "idle"
    assert closed_again.state == "idle"


def test_paused_and_errors():
    paused = laundry.read_machine(
        washer(machine_status=3, Selected_program_remaining_time_in_minutes=20), None, NOW)
    unbalanced = laundry.read_machine(washer(machine_status=4, error_code=100), None, NOW)
    numbered = laundry.read_machine(washer(machine_status=2, error_code=5), None, NOW)

    assert (paused.state, paused.remaining_minutes, paused.ready_at) == ("paused", 20, None)
    assert (unbalanced.state, unbalanced.error) == ("error", "Unbalanced load")
    assert (numbered.state, numbered.error) == ("error", "F05")


# --- the whole conversation -----------------------------------------------------------


class ConnectLife:
    """Fake Gigya, OAuth and gateway, answering like the real ones."""

    def __init__(self, devices: list[dict], gateway_refuses_once: bool = False):
        self.devices, self.refuse, self.seen = devices, gateway_refuses_once, []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            host, path = request.url.host, request.url.path
            self.seen.append(f"{host}{path}")
            if path == "/accounts.login":
                return httpx.Response(200, json={"sessionInfo": {"cookieValue": "c"}, "UID": "u"})
            if path == "/accounts.getJWT":
                return httpx.Response(200, json={"id_token": "j"})
            if path == "/oauth/authorize":
                assert json.loads(request.content)["idToken"] == "j"
                return httpx.Response(200, json={"code": "k"})
            if path == "/oauth/token":
                return httpx.Response(200, json={"access_token": f"token-{len(self.seen)}"})
            if path == "/clife-svc/pu/get_device_status_list":
                params = request.url.params
                assert "sign" in params and params["accessToken"].startswith("token")
                if self.refuse:
                    self.refuse = False
                    return httpx.Response(200, json={"response": {"resultCode": 1003}})
                return httpx.Response(200, json={"response": {"resultCode": 0,
                                                              "deviceList": self.devices}})
            return httpx.Response(404)

        return httpx.MockTransport(handler)


def collect(store, cloud: ConnectLife, client: laundry.Client | None = None,
            now: datetime = NOW) -> laundry.Laundry:
    client = client or laundry.Client(transport=cloud.transport())
    return asyncio.run(laundry.collect(CFG, store, now=now, client=client))


def test_logs_in_once_and_reuses_the_token(store):
    cloud = ConnectLife([DRYER["response"]["deviceList"][0], washer()])
    client = laundry.Client(transport=cloud.transport())

    first = collect(store, cloud, client)
    collect(store, cloud, client, NOW + timedelta(minutes=1))

    assert [m.kind for m in first.machines] == ["washer", "dryer"]
    assert first.showing is False
    assert sum(1 for s in cloud.seen if s.endswith("/accounts.login")) == 1
    assert sum(1 for s in cloud.seen if s.endswith("get_device_status_list")) == 2


def test_the_login_sends_no_shared_gmid(store):
    sent = []

    class Recording(ConnectLife):
        def transport(self):
            inner = super().transport()

            def handler(request):
                if request.url.host == "accounts.eu1.gigya.com":
                    sent.append(request.content.decode())
                return inner.handle_request(request)

            return httpx.MockTransport(handler)

    collect(store, Recording([washer()]))

    assert len(sent) == 2 and not any("gmid" in body for body in sent)


def test_a_restart_reuses_the_stored_token(store):
    cloud = ConnectLife([washer()])
    collect(store, cloud)

    restarted = laundry.Client(transport=cloud.transport())
    collect(store, cloud, restarted, NOW + timedelta(hours=1))

    assert sum(1 for s in cloud.seen if s.endswith("/accounts.login")) == 1
    assert restarted.token_until == NOW + laundry.TOKEN_FOR


def test_a_restart_logs_in_again_once_the_stored_token_has_expired(store):
    cloud = ConnectLife([washer()])
    collect(store, cloud)

    collect(store, cloud, now=NOW + laundry.TOKEN_FOR + timedelta(minutes=1))

    assert sum(1 for s in cloud.seen if s.endswith("/accounts.login")) == 2


def test_a_refused_status_logs_in_again_once(store):
    cloud = ConnectLife([washer(machine_status=2, Selected_program_remaining_time_in_minutes=40)])
    client = laundry.Client(transport=cloud.transport())
    collect(store, cloud, client)
    cloud.refuse = True

    result = collect(store, cloud, client, NOW + timedelta(minutes=1))

    assert result.showing is True and result.machines[0].state == "running"
    assert sum(1 for s in cloud.seen if s.endswith("/accounts.login")) == 2


def test_done_is_remembered_between_runs_through_the_cache(store):
    cloud = ConnectLife([washer(machine_status=2, Selected_program_remaining_time_in_minutes=1)])
    client = laundry.Client(transport=cloud.transport())
    store.put_cache(laundry.CACHE_KEY, collect(store, cloud, client).model_dump(mode="json"))
    cloud.devices = [washer(machine_status=1)]

    after = collect(store, cloud, client, NOW + timedelta(minutes=2))

    assert after.machines[0].state == "done" and after.showing is True


def test_a_refused_login_raises_so_the_last_answer_goes_stale(store):
    class Refusing(ConnectLife):
        def transport(self):
            return httpx.MockTransport(lambda r: httpx.Response(200, json={"errorCode": 403042}))

    with pytest.raises(laundry.ConnectLifeError, match="login refused"):
        collect(store, Refusing([]))


def test_after_a_refused_login_it_waits_longer_each_time_before_trying_again(store):
    class RateLimited(ConnectLife):
        refusing = True

        def transport(self):
            inner = super().transport()

            def handler(request):
                if request.url.path == "/accounts.login" and self.refusing:
                    self.seen.append("refused")
                    return httpx.Response(200, json={"errorCode": 403048})
                return inner.handle_request(request)

            return httpx.MockTransport(handler)

    cloud = RateLimited([washer()])
    client = laundry.Client(transport=cloud.transport())

    def attempt(minutes: int) -> str:
        try:
            collect(store, cloud, client, NOW + timedelta(minutes=minutes))
        except laundry.ConnectLifeError as exc:
            return str(exc)
        return "ok"

    assert attempt(0) == "login refused (Gigya 403048)"
    assert attempt(1) == "login paused until 08:15 UTC after a refusal"
    assert attempt(15) == "login refused (Gigya 403048)"
    assert attempt(30) == "login paused until 08:45 UTC after a refusal"
    assert cloud.seen.count("refused") == 2
    cloud.refusing = False
    assert attempt(45) == "ok"
    assert client.pause == laundry.LOGIN_PAUSE and client.paused_until is None


def test_a_login_pause_survives_a_restart(store):
    class Refusing(ConnectLife):
        def transport(self):
            def handler(request):
                self.seen.append(request.url.path)
                return httpx.Response(200, json={"errorCode": 403048})

            return httpx.MockTransport(handler)

    cloud = Refusing([])
    with pytest.raises(laundry.ConnectLifeError, match="login refused"):
        collect(store, cloud)

    restarted = laundry.Client(transport=cloud.transport())
    with pytest.raises(laundry.ConnectLifeError, match="paused until 08:15 UTC"):
        collect(store, cloud, restarted, NOW + timedelta(minutes=1))

    assert cloud.seen == ["/accounts.login"]
    assert restarted.pause == laundry.LOGIN_PAUSE * 2


def test_switched_off_without_an_account():
    assert laundry.settings(CFG)["enabled"] is True
    assert laundry.settings({"connectlife": {"username": "x"}})["enabled"] is False


def test_the_route_serves_the_answer(store):
    # No `with`: the lifespan would start the scheduler and hit real sources.
    main.app.state.store = store
    main.app.state.config = CFG
    client = TestClient(main.app)
    assert client.get("/api/laundry").status_code == 503

    store.put_cache(laundry.CACHE_KEY,
                    collect(store, ConnectLife([washer()])).model_dump(mode="json"))

    answer = client.get("/api/laundry").json()
    assert answer["machines"][0]["name"] == "Washing machine"
    assert "test-washer-puid" not in json.dumps(answer)


def test_a_failing_status_call_never_puts_the_token_in_the_error(store):
    class Failing(ConnectLife):
        def transport(self):
            inner = super().transport()

            def handler(request):
                if request.url.path.endswith("get_device_status_list"):
                    return httpx.Response(502)
                return inner.handle_request(request)

            return httpx.MockTransport(handler)

    with pytest.raises(laundry.ConnectLifeError) as caught:
        collect(store, Failing([]))

    assert str(caught.value) == "get_device_status_list: HTTP 502"
    assert "token" not in str(caught.value) and caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
