from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.alerts import bot, core, rules
from app.alerts.telegram import Telegram

CFG = {
    "timezone": "Europe/Amsterdam",
    "telegram": {
        "token": "t",
        "chats": {
            "nas": {"id": "-1001", "label": "NAS alerts"},
            "portfolio": {"id": "-1002", "label": "Portfolio"},
        },
    },
}

NAS = {
    "as_of": "2026-10-01T10:00:00+00:00",
    "stale": False,
    "host": "dev-minotaur",
    "cpu_pct": 12.3,
    "ram_pct": 77.2,
    "cpu_temp_c": 61.6,
    "containers": {"running": 36, "total": 36},
    "storage": {
        "pools": [{"name": "volume2", "used_pct": 86.9}, {"name": "volume3", "used_pct": 34.7}]
    },
    "backup": {"status": "ok", "at": "2026-09-30T18:33:51+00:00"},
}

PORTFOLIO = {
    "as_of": "2026-10-01T10:00:00+00:00",
    "stale": False,
    "total_value": 9119.4,
    "change": {"day_abs": 69.2, "day_pct": 0.76},
    "holdings": [
        {"symbol": "NVDA", "day_pct": 1.51},
        {"symbol": "ASML.AS", "day_pct": -0.27},
        {"symbol": "XDWT.DE", "day_pct": 0.63},
        {"symbol": "AAPL", "day_pct": 0.1},
    ],
}


class FakeApi:
    """Telegram stand-in: hands out queued updates and records sendMessage."""

    def __init__(self, updates=()):
        self.updates = list(updates)
        self.sent: list[dict] = []
        self.calls: list[str] = []

    def client(self):
        async def handler(request):
            method = request.url.path.rsplit("/", 1)[-1]
            self.calls.append(method)
            body = json.loads(request.content)
            if method == "getMe":
                return httpx.Response(200, json={"ok": True, "result": {"username": "HubBot"}})
            if method == "getUpdates":
                # The real call waits for news (long polling); waiting a moment
                # here keeps the loop from starving the test's own tasks.
                await asyncio.sleep(0.01)
                pending = [u for u in self.updates if u["update_id"] >= body.get("offset", 0)]
                return httpx.Response(200, json={"ok": True, "result": pending})
            if method == "sendMessage":
                self.sent.append(body)
            return httpx.Response(200, json={"ok": True, "result": True})

        return Telegram("t", transport=httpx.MockTransport(handler))


def update(update_id, text, chat="-1001", name="Pim"):
    return {
        "update_id": update_id,
        "message": {"text": text, "chat": {"id": int(chat)}, "from": {"first_name": name}},
    }


@pytest.fixture
def bot_store(store):
    core.ensure_tables(store)
    rules.ensure_tables(store)
    return store


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/status", "status"),
        ("/Status extra words", "status"),
        ("/status@HubBot", "status"),
        ("/status@OtherBot", None),
        ("status", None),
        ("", None),
        ("/whatever", "whatever"),
    ],
)
def test_parse_command(text, expected):
    assert bot.parse_command(text, "HubBot") == expected


def test_status_lists_figures_and_open_incidents(bot_store):
    bot_store.put_cache("nas", NAS)
    assert bot.status_text(bot_store, CFG) == (
        "<b>dev-minotaur</b>\nCPU 12% · memory 77% · 62 °C\nContainers 36 of 36 running\n"
        "Fullest: volume2 87%, volume3 35%\n\nNothing needs a look"
    )

    with bot_store.connect() as conn:
        conn.execute(
            "INSERT INTO alert_incident (key, rule, severity, title, opened_at, "
            "last_seen_at) VALUES ('k', 'disk_space', 'warning', 'volume2 is 92% full', "
            "'2026-10-01T10:00:00+00:00', '2026-10-01T10:00:00+00:00')"
        )
    assert bot.status_text(bot_store, CFG).endswith("<b>1 open</b>\n• volume2 is 92% full")


def test_backup_from_run_history_or_the_marker(bot_store):
    bot_store.put_cache("nas", NAS)
    assert (
        bot.backup_text(bot_store, CFG) == "<b>Last backup: Succeeded</b>\nWed 30 Sep 20:33"
    )

    bot_store.put_cache(
        "backups",
        {
            "runs": [
                {
                    "started": "2026-10-02T01:00:00+00:00",
                    "finished": "2026-10-02T01:23:00+00:00",
                    "ok": False,
                    "volumes": [
                        {"name": "volume1", "ok": True, "seconds": 241, "bytes": 2_468_000_000},
                        {
                            "name": "volume3",
                            "ok": False,
                            "seconds": 900,
                            "bytes": 10,
                            "last_error": "quota exceeded",
                        },
                    ],
                }
            ],
            "next_due": "2026-10-03T01:00:00+00:00",
        },
    )
    assert bot.backup_text(bot_store, CFG) == (
        "<b>Last backup: Failed</b>\nFri 02 Oct 03:23\nvolume1: OK · 4 min · 2,5 GB\n"
        "volume3: failed (quota exceeded)\nNext run Sat 03 Oct 03:00"
    )


def test_portfolio_move_is_the_sum_of_the_holdings(bot_store):
    with_euros = {**PORTFOLIO, "holdings": [
        {"symbol": "NVDA", "day_pct": 1.5, "day_abs": 30.0},
        {"symbol": "ASML.AS", "day_pct": -0.5, "day_abs": -10.0},
    ]}
    bot_store.put_cache("portfolio", with_euros)
    # 20 on 9099,40 before the move, not Ghostfolio's own +69.
    assert "Today +€ 20 (+0,22%)" in bot.portfolio_text(bot_store, CFG)


def test_portfolio_shows_value_change_and_biggest_movers(bot_store):
    bot_store.put_cache("portfolio", PORTFOLIO)

    assert bot.portfolio_text(bot_store, CFG) == (
        "<b>€ 9.119</b>\nToday +€ 69 (+0,76%)\nNVDA +1,5%\nXDWT.DE +0,6%\nASML.AS −0,3%"
    )


def test_missing_data_gets_a_plain_answer(bot_store):
    assert "No NAS data yet" in bot.status_text(bot_store, CFG)
    assert "No backup recorded yet" in bot.backup_text(bot_store, CFG)
    assert "No portfolio data yet" in bot.portfolio_text(bot_store, CFG)


def test_only_commands_from_the_two_chats_are_answered(bot_store):
    bot_store.put_cache("nas", NAS)
    api = FakeApi()
    tg = api.client()

    def handle(u):
        return asyncio.run(bot.handle_update(bot_store, CFG, u, tg, "HubBot"))

    assert handle(update(1, "/status")) is True
    assert handle(update(2, "/status", chat="-999")) is False  # a stranger's chat
    assert handle(update(3, "hello")) is False  # not a command
    assert handle(update(4, "/help", chat="-1002")) is True

    assert [m["chat_id"] for m in api.sent] == ["-1001", "-1002"]
    assert api.sent[1]["text"].startswith("<b>Home hub</b>\n/status")
    log = core.messages(bot_store, category="bot")
    assert [(m.title, m.chat, m.status) for m in log] == [
        ("/help from Pim", "portfolio", "sent"),
        ("/status from Pim", "nas", "sent"),
    ]


def test_the_poller_registers_commands_answers_and_saves_its_offset(bot_store):
    bot_store.put_cache("portfolio", PORTFOLIO)
    api = FakeApi([update(41, "/portfolio"), update(42, "/portfolio@OtherBot")])

    async def run_once():
        task = asyncio.create_task(bot.run(bot_store, CFG, api.client()))
        for _ in range(200):
            await asyncio.sleep(0.01)
            if core.get_setting(bot_store, bot.OFFSET_KEY, 0) == 43:
                break
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run_once())

    assert api.calls[:2] == ["getMe", "setMyCommands"]
    assert len(api.sent) == 1  # the command for another bot was skipped
    assert api.sent[0]["text"].startswith("<b>€")
    # The saved offset means a restart does not answer these again.
    assert core.get_setting(bot_store, bot.OFFSET_KEY, 0) == 43


def test_no_token_means_no_bot(bot_store):
    asyncio.run(bot.run(bot_store, {"telegram": {"token": ""}}))
