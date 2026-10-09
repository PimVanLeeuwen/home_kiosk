from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.alerts import core
from app.alerts.telegram import Telegram
from app.sources import ups

CFG = {
    "timezone": "Europe/Amsterdam",
    "telegram": {"token": "t", "chats": {"nas": {"id": "-1", "label": "NAS"}}},
    "ups": {"host": "127.0.0.1", "port": 3493, "name": "ups0"},
}
NOW = datetime(2026, 10, 6, 8, 2, tzinfo=UTC)  # 10:02 in Amsterdam
ONLINE = {"ups.status": "OL", "battery.charge": "100", "battery.charge.low": "15",
          "ups.load": "1", "device.mfr": "UGREEN", "device.model": "US3000"}


def on_battery(charge, flags="OB"):
    return {**ONLINE, "ups.status": flags, "battery.charge": str(charge)}


@pytest.fixture
def ups_store(store):
    ups.ensure_tables(store)
    core.ensure_tables(store)
    return store


def read(store, values, at):
    return asyncio.run(ups.collect(CFG, store, now=at, values=values))


class FakeTelegram:
    """Sends through a mock transport; `up` says whether Telegram can be reached."""

    def __init__(self):
        self.texts, self.up = [], True

    def client(self):
        def handler(request):
            if not self.up:
                raise httpx.ConnectError("no route to host")
            self.texts.append(json.loads(request.content)["text"])
            return httpx.Response(200, json={"ok": True, "result": {}})

        return Telegram("t", transport=httpx.MockTransport(handler))


def test_reads_every_variable_from_a_nut_server():
    async def nut(reader, writer):
        line = await reader.readline()
        assert line == b"LIST VAR ups0\n"
        writer.write(b'BEGIN LIST VAR ups0\nVAR ups0 battery.charge "87"\n'
                     b'VAR ups0 ups.status "OB DISCHRG"\nEND LIST VAR ups0\n')
        await writer.drain()
        await reader.readline()  # LOGOUT
        writer.close()

    async def go():
        server = await asyncio.start_server(nut, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            return await ups.read_vars("127.0.0.1", port, "ups0")

    assert asyncio.run(go()) == {"battery.charge": "87", "ups.status": "OB DISCHRG"}


def test_an_unknown_ups_is_an_error():
    async def nut(reader, writer):
        await reader.readline()
        writer.write(b"ERR UNKNOWN-UPS\n")
        await writer.drain()
        writer.close()

    async def go():
        server = await asyncio.start_server(nut, "127.0.0.1", 0)
        async with server:
            await ups.read_vars("127.0.0.1", server.sockets[0].getsockname()[1], "ups9")

    with pytest.raises(ValueError, match="UNKNOWN-UPS"):
        asyncio.run(go())


def test_status_from_the_flags_and_the_charge():
    assert ups.status_of(ONLINE)[0] == "online"
    assert ups.status_of(on_battery(80))[0] == "on_battery"
    # ignorelb: the UPS's own LB flag is ignored, so the charge decides too.
    assert ups.status_of(on_battery(15))[0] == "low_battery"
    assert ups.status_of(on_battery(40, "OB LB"))[0] == "low_battery"
    assert ups.status_of({})[0] == "unknown"


def test_an_outage_is_kept_from_the_first_reading_on_battery_to_mains_again(ups_store):
    payload = read(ups_store, ONLINE, NOW - timedelta(minutes=1))
    assert (payload.status, payload.charge, payload.load, payload.model, payload.outages) == (
        "online", 100, 1, "UGREEN US3000", [])

    read(ups_store, on_battery(80), NOW)
    read(ups_store, on_battery(14), NOW + timedelta(minutes=30))
    during = read(ups_store, on_battery(60), NOW + timedelta(minutes=31))
    (current,) = during.outages
    assert (current.ended_at, current.lowest_charge, current.reached_low) == (None, 14, True)

    after = read(ups_store, ONLINE, NOW + timedelta(minutes=39))
    (done,) = after.outages
    assert done.started_at == NOW and done.ended_at == NOW + timedelta(minutes=39)


def test_one_report_per_power_cut_retried_until_telegram_is_back(ups_store):
    read(ups_store, on_battery(62), NOW)
    read(ups_store, ONLINE, NOW + timedelta(minutes=39))
    telegram = FakeTelegram()
    telegram.up = False

    later = NOW + timedelta(minutes=40)
    assert asyncio.run(ups.report_outages(ups_store, CFG, later, telegram.client())) == 0

    telegram.up = True
    assert asyncio.run(ups.report_outages(ups_store, CFG, later, telegram.client())) == 1
    assert telegram.texts == [
        "<b>WARNING</b> · <b>Power cut of 39 min</b>\n"
        "From Tue 06 Oct 10:02 to 10:41, the UPS went down to 62%."]
    # Sent once only.
    assert asyncio.run(ups.report_outages(ups_store, CFG, later, telegram.client())) == 0


def test_the_report_says_when_the_nas_stopped_its_services(ups_store):
    read(ups_store, on_battery(14), NOW)
    read(ups_store, ONLINE, NOW + timedelta(hours=2, minutes=5))
    telegram = FakeTelegram()

    asyncio.run(ups.report_outages(ups_store, CFG, NOW + timedelta(hours=3), telegram.client()))

    assert telegram.texts[0].startswith("<b>WARNING</b> · <b>Power cut of 2 h 5 min</b>")
    assert telegram.texts[0].endswith("so the NAS stopped its services.")


def test_a_report_that_cannot_go_out_for_two_days_is_dropped(ups_store):
    read(ups_store, on_battery(90), NOW)
    read(ups_store, ONLINE, NOW + timedelta(minutes=5))
    telegram = FakeTelegram()

    asyncio.run(ups.report_outages(ups_store, CFG, NOW + timedelta(days=3), telegram.client()))
    asyncio.run(ups.report_outages(ups_store, CFG, NOW + timedelta(days=3), telegram.client()))

    assert telegram.texts == []
