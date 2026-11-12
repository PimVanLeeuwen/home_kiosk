"""The hub's MCP server at /mcp (plan.md M33): Claude asks the house over the tailnet.

Read-only tools over the collector's own cache, so a call never waits on a source and
never reaches one. Whatever a tool returns goes into a prompt at Anthropic, so each tool
returns the least that answers: the cached payload trimmed, never more than `/api` serves.

No login, like the rest of the hub (the LAN and Tailscale are the boundary). A browser
has no business here, so any request with an Origin header is refused: that keeps another
website, or a DNS rebinding trick, from asking on the owner's behalf.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from . import mcp_house as house
from . import reminders as reminders_store
from .alerts import core as alerts_core
from .alerts import rules as alert_rules
from .sources import agenda, media_status, my_sites, ns
from .sources import air as air_source
from .sources import forecast as forecast_source
from .sources import laundry as laundry_source
from .sources import outside_services as outside_services_source
from .sources import services as service_catalog
from .sources import weather as weather_source
from .store import Store

log = logging.getLogger(__name__)

PATH = "/mcp"

INSTRUCTIONS = (
    "The Home hub of one household in the Netherlands: the NAS and its apps, backups, Docker "
    "and media stack, the owner's weekday train, today's calendar and reminders, the weather, "
    "the living room's air, the washer and dryer, the owner's websites, the outside services "
    "the house depends on, and the alerts the hub sent. Every answer is the hub's last good "
    "reading; `stale: true` means a source failed and this is older than usual, `as_of` says "
    "from when."
)

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def _zone(cfg: dict[str, Any]) -> ZoneInfo:
    return ZoneInfo(cfg.get("timezone", "UTC"))


def _date(value: str | None, default: date) -> date:
    """A tool's YYYY-MM-DD argument; an empty one is `default`."""
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ToolError(f"Give the date as YYYY-MM-DD, not {value!r}.") from None


def _dumped(value: Any) -> Any:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def build(store: Callable[[], Store], config: Callable[[], dict[str, Any]]) -> MCPServer:
    """The server; `store` and `config` are asked on each call, so tests and the app can swap
    them. What each tool returns is in mcp_house.py."""
    server = MCPServer("home-hub", instructions=INSTRUCTIONS)
    tool = server.tool(annotations=READ_ONLY)

    def cached(key: str) -> Any:
        return store().get_cache(key)

    @tool
    def train() -> dict[str, Any]:
        """The owner's weekday morning train: on weekday mornings until it leaves, the evening
        before for tomorrow's. Status, delay, track, cancellation with the next direct train."""
        return house.train(cached(ns.CACHE_KEY))

    @tool
    def backups() -> dict[str, Any]:
        """The nightly backup to the Hetzner storage box: per volume the last run and last
        success, the box's free room and when it fills up, and the next run."""
        return house.backups(cached("backups"))

    @tool
    def nas() -> dict[str, Any]:
        """The NAS right now: CPU, memory, temperatures, storage, disks with SMART state,
        running containers, network speed and the last backup's state."""
        return house.nas(cached("nas"))

    @tool
    async def calendar(start: str | None = None, days: int = 1) -> dict[str, Any]:
        """The household's shown calendars: events with title and times only, from `start`
        (YYYY-MM-DD, default today) for `days` days (1 to 31). Today and tomorrow come from the
        hub's copy; any other range is read from the calendars on the spot."""
        zone = _zone(config())
        today = datetime.now(zone).date()
        first = _date(start, today)
        if first == today and days <= 2:
            return house.calendar(cached(agenda.CACHE_KEY), max(days, 1))
        try:
            answer = await agenda.days(config(), store(), first, days)
        except LookupError as exc:
            raise ToolError(str(exc)) from None
        except Exception as exc:
            # The class only: an error can carry a calendar's address, and that a token.
            log.warning("MCP calendar read failed: %s", type(exc).__name__)
            raise ToolError("The calendars could not be read just now; try again later.") \
                from None
        return house.calendar_days(answer)

    @tool
    def weather() -> dict[str, Any]:
        """The weather at home now (Buienradar) and the rain over the next two hours in
        5-minute steps. For later hours and days, use `forecast`."""
        return house.weather(cached(weather_source.CACHE_KEY))

    @tool
    def forecast(day: str | None = None) -> dict[str, Any]:
        """The forecast at home for the coming 7 days (Open-Meteo): per day the high, low,
        WMO sky code, highest chance of rain and expected rain in mm, and per hour the
        temperature, chance of rain and expected rain. `day` (YYYY-MM-DD) gives one day only;
        `known_days` lists the days there are."""
        return house.forecast(cached(forecast_source.CACHE_KEY), day)

    @tool
    def air() -> dict[str, Any]:
        """The living room's air: temperature, humidity, CO2, fine dust and how good it is."""
        return house.air(cached(air_source.CACHE_KEY))

    @tool
    def laundry() -> dict[str, Any]:
        """The washer and dryer: running, done, paused or with an error, and time left."""
        return house.laundry(cached(laundry_source.CACHE_KEY))

    @tool
    def reminders(start: str | None = None, days: int = 7) -> dict[str, Any]:
        """The hub's reminders: for each day from `start` (YYYY-MM-DD, default today) for
        `days` days (1 to 92) the reminders that fall then, ticked off or not; and every
        reminder with its next day and how it repeats."""
        zone = _zone(config())
        now = datetime.now(UTC)
        first = _date(start, now.astimezone(zone).date())
        s = store()
        wanted = [first + timedelta(days=i) for i in range(min(max(days, 1), 92))]
        found = [(day.isoformat(), reminders_store.today(s, day)) for day in wanted]
        return house.reminders(reminders_store.overview(s, now, zone), found)

    @tool
    def docker() -> dict[str, Any]:
        """Every container on the NAS: state, health, CPU and memory."""
        return house.docker(cached("docker"))

    @tool
    def media() -> dict[str, Any]:
        """The media stack: downloads and their progress, aired episodes that are missing,
        and what airs in the coming week (Sonarr and Radarr)."""
        return house.media(cached(media_status.CACHE_KEY))

    @tool
    def services() -> dict[str, Any]:
        """Every app on the NAS by group: up or not, and its live figures."""
        s = store()
        catalog = service_catalog.build(s.list_services(), s.get_cache("containers"),
                                        s.get_cache("widgets"))
        return house.services(_dumped(catalog))

    @tool
    def websites() -> dict[str, Any]:
        """The owner's own websites: up now, ping and 30-day uptime (Uptime Kuma)."""
        return house.sites(cached(my_sites.CACHE_KEY))

    @tool
    def outside_services() -> dict[str, Any]:
        """The outside services the house depends on (GitHub, Cloudflare, Docker Hub,
        Tailscale, Hetzner, TransIP, Proton): their state and any open incident."""
        return house.outside(cached(outside_services_source.CACHE_KEY))

    @tool
    def alerts(limit: int = 20, category: str | None = None) -> dict[str, Any]:
        """The newest messages the hub sent to the phone (newest first, at most 50), optionally
        one category (e.g. backup, updates, uptime, nas, reminders), and the open incidents
        of the hub's own alert rules."""
        s = store()
        messages = alerts_core.messages(s, min(max(limit, 1), 50), category)
        return house.alerts(messages, alert_rules.incidents(s))

    return server


class _RefuseBrowsers:
    """403 for any request carrying an Origin header (see the module docstring)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and any(k == b"origin" for k, _ in scope["headers"]):
            response = JSONResponse({"detail": "Not for browsers."}, status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def http_endpoint(server: MCPServer) -> ASGIApp:
    """The ASGI endpoint to route at PATH.

    Stateless and plain JSON (no event stream): every tool answers at once from the
    cache, and Caddy passes it on like any API call. The SDK's own Host check is off:
    the hub answers on several names (LAN, Tailscale), and the Origin check covers it.
    It answers only while `server.session_manager.run()` runs (the app's lifespan).
    """
    # Builds the server's session manager; the SDK's own Starlette app is not used.
    server.streamable_http_app(
        streamable_http_path=PATH,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return _RefuseBrowsers(StreamableHTTPASGIApp(server.session_manager))
