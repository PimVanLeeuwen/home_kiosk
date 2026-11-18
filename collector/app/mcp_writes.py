"""The MCP tools that change something in the house (plan.md M33, step 3).

Only on the server that answers a request carrying the write token (mcp_server.py), so a
Claude without the token never sees them. The same writes the hub's own pages make, through
the same functions: the living room's lights, Spotify, reminders, todos and a test message.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import ValidationError

from . import mcp_house as house
from . import reminders as reminders_store
from . import todos as todos_store
from .alerts import core as alerts_core
from .lights_api import Change
from .sources import hue, music, spotify
from .store import Store

# Changes the house, but nothing that cannot be changed back.
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
# Ticking a todo off removes it (plan.md M37): the hub's Undo is on its pages only.
REMOVES = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)
TEST_TITLE = "Test from Claude"


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    where = ".".join(str(p) for p in err.get("loc") or ()) or "input"
    return f"{where}: {err.get('msg')}"


def _hue(cfg: dict[str, Any]) -> dict[str, Any]:
    if not hue.settings(cfg)["enabled"]:
        raise ToolError("The Hue Bridge is not set up (HUE_APPLICATION_KEY).")
    return cfg


def _spotify(cfg: dict[str, Any]) -> dict[str, Any]:
    if not spotify.settings(cfg)["enabled"]:
        raise ToolError("Spotify is not set up (SPOTIFY_CLIENT_ID).")
    return cfg


def _spotify_failed(exc: Exception) -> ToolError:
    if isinstance(exc, spotify.SpotifyError):
        return ToolError(str(exc))
    return ToolError("Spotify could not be reached.")


def register(server: MCPServer, store: Callable[[], Store],
             config: Callable[[], dict[str, Any]], day: Callable[[str | None], date]) -> None:
    """Adds the write tools to `server`. `day` reads a tool's YYYY-MM-DD argument."""
    tool = server.tool(annotations=WRITE)

    def _todo(t: todos_store.Todo) -> dict[str, Any]:
        return house.todo(t.model_dump(mode="json") | {"state": todos_store.state(t, day(None))})

    @tool
    async def lights_room(on: bool) -> dict[str, Any]:
        """Switch all the living room's lights on or off at once. Answers with the lights as
        the bridge has them afterwards."""
        cfg = _hue(config())
        try:
            result = await hue.switch_room(cfg, store(), on)
        except Exception as exc:
            raise ToolError(hue.reason(exc)) from None
        return house.lights(result.model_dump(mode="json"))

    @tool
    async def lights_change(group: str, on: bool | None = None, brightness: int | None = None,
                            kelvin: int | None = None) -> dict[str, Any]:
        """Change one group of the living room's lights (its id from the `lights` tool):
        switch it, dim it (brightness 1 to 100) or set its white (kelvin, one of the
        `kelvins` the lights tool lists). Dimming or a white also switches it on."""
        cfg = _hue(config())
        try:
            change = Change(on=on, brightness=brightness, kelvin=kelvin)
        except ValidationError as exc:
            raise ToolError(_first_error(exc)) from None
        try:
            result = await hue.change(cfg, store(), group, on=change.on,
                                      brightness=change.brightness, kelvin=change.kelvin)
        except KeyError:
            raise ToolError(f"No group of lights called {group!r}; see the lights tool.") \
                from None
        except ValueError as exc:
            raise ToolError(str(exc)) from None
        except Exception as exc:
            raise ToolError(hue.reason(exc)) from None
        return house.lights(result.model_dump(mode="json"))

    @tool
    async def music_control(action: Literal["play", "pause", "next", "previous"]) -> dict:
        """Play, pause, or skip to the next or previous track on Spotify, where it plays."""
        cfg = _spotify(config())
        try:
            await music.control(cfg, store(), action)
        except Exception as exc:
            raise _spotify_failed(exc) from None
        return {"ok": True, "action": action}

    @tool
    async def music_volume(percent: int) -> dict[str, Any]:
        """Set Spotify's volume on the device that plays, 0 to 100."""
        if not 0 <= percent <= 100:
            raise ToolError("The volume goes from 0 to 100.")
        cfg = _spotify(config())
        try:
            await music.volume(cfg, store(), percent)
        except Exception as exc:
            raise _spotify_failed(exc) from None
        return {"ok": True, "volume": percent}

    @tool
    async def music_play_favourite(position: int) -> dict[str, Any]:
        """Start one of the favourite playlists (its position from the `music` tool), on the
        device that plays or else the default one (the living room Apple TV, woken up)."""
        cfg = _spotify(config())
        try:
            device = await music.play_favourite(cfg, store(), position)
        except Exception as exc:
            raise _spotify_failed(exc) from None
        return {"ok": True, "device_id": device}

    @tool
    def add_reminder(title: str, on: str, at: str | None = None,
                     notify: Literal["none", "at", "hour", "evening"] = "at") -> dict[str, Any]:
        """Add a one-off reminder on the day `on` (YYYY-MM-DD), optionally at a time `at`
        (HH:MM). `notify`: none, at its time (08:00 without one), an hour before (needs a
        time) or the evening before at 20:00. It shows on the Reminders page, Home and the
        Door panel. Repeating reminders are made in the hub."""
        try:
            draft = reminders_store.Draft.model_validate(
                {"title": title, "start": day(on).isoformat(), "at": at, "notify": notify})
        except ValidationError as exc:
            raise ToolError(_first_error(exc)) from None
        made = reminders_store.add(store(), draft)
        return {"ok": True, "id": made.id, "title": made.title, "on": made.start.isoformat(),
                "at": made.at, "notify": made.notify}

    @tool
    def tick_reminder(reminder_id: int, on: str | None = None,
                      done: bool = True) -> dict[str, Any]:
        """Tick a reminder off (or `done=false` to untick it) for one day: `on` (YYYY-MM-DD,
        default today). Its id comes from the `reminders` tool. A repeating reminder is
        ticked off for that day only."""
        s = store()
        found = reminders_store.get(s, reminder_id)
        if found is None:
            raise ToolError(f"No reminder with id {reminder_id}; see the reminders tool.")
        when = day(on)
        if not reminders_store.occurs(found, when):
            raise ToolError(f"{found.title!r} does not fall on {when.isoformat()}.")
        reminders_store.set_done(s, reminder_id, when, done)
        return {"ok": True, "title": found.title, "on": when.isoformat(), "done": done}

    @tool
    def add_todo(title: str, note: str | None = None, due: str | None = None,
                 high: bool = False) -> dict[str, Any]:
        """Add a todo: a title, optionally a short `note`, a `due` date (YYYY-MM-DD) and
        `high` for something that matters most. It stays until ticked off, on the Todos page,
        Home, the Now panel and the daily todo message."""
        s = store()
        try:
            draft = todos_store.Draft.model_validate(
                {"title": title, "note": note, "due": day(due).isoformat() if due else None,
                 "high": high})
        except ValidationError as exc:
            raise ToolError(_first_error(exc)) from None
        if todos_store.count(s) >= todos_store.MAX_OPEN:
            raise ToolError(f"At most {todos_store.MAX_OPEN} open todos.")
        made = todos_store.add(s, draft)
        return {"ok": True, **_todo(made)}

    @server.tool(annotations=REMOVES)
    def tick_todo(todo_id: int) -> dict[str, Any]:
        """Tick a todo off, which removes it from the list (there is no done list). Its id
        comes from the `todos` tool. Answers with the todo as it was, so it can be added
        again if this was a mistake."""
        removed = todos_store.remove(store(), todo_id)
        if removed is None:
            raise ToolError(f"No open todo with id {todo_id}; see the todos tool.")
        return {"ok": True, "removed": _todo(removed)}

    @tool
    async def send_test_message(text: str = "Claude can reach the hub.") -> dict[str, Any]:
        """Send a test message to the owner's phone through the hub (ntfy, Telegram as the
        fallback), also in quiet hours. For checking that alerts arrive; not for chatting."""
        body = text.strip()[:500] or "Claude can reach the hub."
        sent = await alerts_core.notify(store(), config(), source="hub.mcp", category="manual",
                                        severity="info", title=TEST_TITLE, body=body,
                                        bypass_quiet=True, now=datetime.now(UTC))
        return {"ok": sent.status == "sent", "status": sent.status, "channel": sent.channel}
