"""Ask (plan.md M35): a short chat with the house on the hub's Ask page.

The browser keeps the conversation and sends it with every question; nothing of it is
stored here. Claude (Haiku) answers with the hub's own MCP tools, called in-process: the
house tools to read, and the write tools only as proposals. A write tool call is never run
here: it comes back to the page as a card, and only the owner's Confirm runs it
(`confirm`). Every call counts against the monthly AI cap (ai.py), as feature "ask".
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

import anthropic
from mcp.client import Client
from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from . import ai
from . import reminders as reminders_store
from .sources import hue
from .sources import music as music_source
from .store import Store

log = logging.getLogger(__name__)

FEATURE = "ask"
MODEL = "claude-haiku-5-5"
MAX_TOKENS = 1500
MAX_ROUNDS = 8  # tool rounds per question
HISTORY = 20  # messages of the conversation sent along
MESSAGE_CHARS = 4000
RESULT_CHARS = 16000  # a tool's answer, as Claude sees it

# What Claude may ask to change; each needs the owner's Confirm. The test message is for
# checking alerts from Claude Code, not for the chat.
PROPOSED = ("lights_room", "lights_change", "music_control", "music_volume",
            "music_play_favourite", "add_reminder", "tick_reminder")
# The developer tools are for Claude Code; the chat keeps to the house.
LEFT_OUT = {"source_sample", "job_status", "hub_logs", "container_logs", "deployed_version",
            "panel_state"}

SYSTEM = (
    "You are the Home hub of one household in the Netherlands, answering its owner on the "
    "hub's Ask page. Answer from the hub's tools, never from guesses: call the tools that "
    "fit, then answer briefly in plain sentences, in the owner's language. Bold a key fact "
    "with **double asterisks** and use a short list with '- ' when it helps; no tables, no "
    "headings, no emoji. Times are local (24-hour clock). When a tool says it has no data "
    "or fails, say so plainly. To change something (lights, music, reminders), call its "
    "tool: the hub shows the change to the owner with Confirm and Cancel, and nothing "
    "happens before they confirm. So say what you proposed, never that it is done. "
    "Now: {now}."
)


class Message(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=20000)


class Question(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=200)


class Proposal(BaseModel):
    id: str
    tool: str
    args: dict[str, Any]
    title: str
    detail: str | None = None


class Answer(BaseModel):
    text: str
    used: list[str]
    proposals: list[Proposal]
    spent: float
    cap: float


class AskError(Exception):
    """A refusal fit for the page: `status` is the HTTP status to answer with."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


# --- what a proposed change looks like on its card ------------------------------------------


def _day(value: Any) -> str:
    try:
        return date.fromisoformat(str(value)).strftime("%A %-d %B")
    except ValueError:
        return str(value)


def describe(tool: str, args: dict[str, Any], store: Store) -> tuple[str, str | None]:
    """The card's title and line under it, in the hub's words."""
    if tool == "lights_room":
        return (f"Switch the living room lights {'on' if args.get('on') else 'off'}", None)
    if tool == "lights_change":
        groups = {g.get("id"): g for g in (store.get_cache(hue.CACHE_KEY) or {}).get("groups")
                  or []}
        group = groups.get(args.get("group")) or {}
        name = group.get("name") or str(args.get("group"))
        parts = []
        if args.get("on") is False:
            parts.append("off")
        elif args.get("on") and args.get("brightness") is None:
            parts.append("on")
        if args.get("brightness") is not None:
            parts.append(f"to {args['brightness']}%")
        if args.get("kelvin") is not None:
            parts.append(f"{args['kelvin']} K white")
        now = (f"now at {group['brightness']}%" if group.get("on") else "now off") \
            if group else None
        verb = "Dim" if args.get("brightness") is not None else "Switch"
        return f"{verb} the {name} {' '.join(parts)}".strip(), now
    if tool == "music_control":
        action = args.get("action")
        words = {"play": "Play the music", "pause": "Pause the music",
                 "next": "Skip to the next track", "previous": "Go back a track"}
        return words.get(action, f"Music: {action}"), None
    if tool == "music_volume":
        return f"Set the music's volume to {args.get('percent')}%", None
    if tool == "music_play_favourite":
        favs = {f["position"]: f["name"] for f in music_source.favourites(store)}
        return f"Play {favs.get(args.get('position'), 'favourite ' + str(args.get('position')))}", \
            None
    if tool == "add_reminder":
        when = _day(args.get("on")) + (f" at {args['at']}" if args.get("at") else "")
        notify = {"none": "no message", "at": "message at its time" if args.get("at")
                  else "message at 08:00", "hour": "message an hour before",
                  "evening": "message the evening before"}.get(args.get("notify") or "at")
        return f"Add a reminder: {args.get('title')}", f"{when}, {notify}"
    if tool == "tick_reminder":
        verb = "Tick off" if args.get("done", True) else "Untick"
        when = _day(args["on"]) if args.get("on") else "today"
        found = reminders_store.get(store, int(args.get("reminder_id") or 0))
        name = found.title if found else f"reminder {args.get('reminder_id')}"
        return f"{verb}: {name}", when
    return tool, json.dumps(args)


# --- the conversation -------------------------------------------------------------------------


def _schema(tool: Any) -> dict[str, Any]:
    return {"name": tool.name, "description": tool.description or "",
            "input_schema": tool.input_schema or {"type": "object", "properties": {}}}


def _result_text(result: Any) -> str:
    if result.is_error:
        text = "".join(getattr(c, "text", "") for c in result.content)
        return f"The tool failed: {text}"
    if result.structured_content is not None:
        return json.dumps(result.structured_content, ensure_ascii=False)[:RESULT_CHARS]
    return "".join(getattr(c, "text", "") for c in result.content)[:RESULT_CHARS]


def _history(messages: list[Message]) -> list[dict[str, Any]]:
    """The last messages, alternating and starting with the owner, each cut to size."""
    kept = [m for m in messages if m.text.strip()][-HISTORY:]
    while kept and kept[0].role != "user":
        kept.pop(0)
    out: list[dict[str, Any]] = []
    for m in kept:
        text = m.text.strip()[:MESSAGE_CHARS]
        if out and out[-1]["role"] == m.role:
            out[-1]["content"] += "\n\n" + text
        else:
            out.append({"role": m.role, "content": text})
    if not out or out[-1]["role"] != "user":
        raise AskError(422, "The conversation has to end with a question.")
    return out


def _client(api_key: str) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=api_key, timeout=ai.TIMEOUT_SECONDS, max_retries=2)


async def answer(cfg: dict[str, Any], store: Store, question: Question, read: MCPServer,
                 write: MCPServer, now: datetime | None = None,
                 client: Callable[[str], Any] | None = None) -> Answer:
    """Claude's answer to the conversation's last question, with any changes it proposes."""
    now = now or datetime.now(UTC)
    s = ai.settings(cfg)
    if not s["enabled"]:
        raise AskError(503, "Claude is not set up (ANTHROPIC_API_KEY).")
    if not ai.switches(store).get(FEATURE):
        raise AskError(409, "Ask is switched off: switch it on in Settings, AI.")
    spent, _ = ai.month_spend(store, cfg, now)
    if spent >= s["cap_eur"]:
        raise AskError(429, "The AI cap is reached for this month. Ask works again on the "
                            "1st, or raise the cap in the hub's config.")
    messages = _history(question.messages)
    zone = ZoneInfo(cfg.get("timezone", "UTC"))
    system = SYSTEM.format(now=now.astimezone(zone).strftime("%A %-d %B %Y, %H:%M"))
    api = (client or _client)(s["api_key"])
    used: list[str] = []
    proposals: list[Proposal] = []

    async with Client(read) as reader, Client(write) as writer:
        tools = [_schema(t) for t in (await reader.list_tools()).tools
                 if t.name not in LEFT_OUT]
        tools += [_schema(t) for t in (await writer.list_tools()).tools if t.name in PROPOSED]
        text = ""
        for _ in range(MAX_ROUNDS):
            try:
                response = await api.messages.create(
                    model=MODEL, max_tokens=MAX_TOKENS, system=system, tools=tools,
                    messages=messages, output_config={"effort": "low"})
            except anthropic.RateLimitError:
                raise AskError(503, "Claude is busy; try again in a minute.") from None
            except anthropic.APIStatusError as exc:
                log.warning("ask failed: HTTP %s", exc.status_code)
                raise AskError(502, "Claude did not answer; try again.") from None
            except anthropic.APIConnectionError:
                raise AskError(502, "Claude could not be reached; try again.") from None
            ai._record(store, now, FEATURE, MODEL, response.usage)
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            calls = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not calls:
                break
            messages.append({"role": "assistant", "content": list(response.content)})
            results = []
            for call in calls:
                args = dict(call.input or {})
                if call.name in PROPOSED:
                    title, detail = describe(call.name, args, store)
                    proposals.append(Proposal(id=call.id, tool=call.name, args=args,
                                              title=title, detail=detail))
                    content = ("Shown to the owner as a card with Confirm and Cancel; not done "
                               "yet. Say what you proposed.")
                else:
                    if call.name not in used:
                        used.append(call.name)
                    content = _result_text(await reader.call_tool(call.name, args))
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                "content": content})
            messages.append({"role": "user", "content": results})
        else:
            text = text or "That took too many steps; ask a narrower question."

    spent, _ = ai.month_spend(store, cfg, now)
    await ai._warn_once(store, cfg, now, spent, s["cap_eur"], None)
    if response.stop_reason == "refusal":
        text = "Claude declined to answer that."
    return Answer(text=text or "No answer came back; try again.", used=used,
                  proposals=proposals, spent=round(spent, 4), cap=s["cap_eur"])


async def confirm(write: MCPServer, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """Runs a change the owner confirmed on its card, with the write tool Claude proposed."""
    if tool not in PROPOSED:
        raise AskError(422, f"{tool!r} is not a change Ask can make.")
    async with Client(write) as writer:
        result = await writer.call_tool(tool, args)
    if result.is_error:
        raise AskError(422, "".join(getattr(c, "text", "") for c in result.content)
                       or "The change failed.")
    return {"ok": True, "tool": tool, "result": result.structured_content}
