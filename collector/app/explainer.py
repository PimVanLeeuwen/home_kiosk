"""Alert explainer (plan.md M26, step 5): a likely cause and what to try first.

When a container alert opens (a container down, or one stuck restarting) and its
message went out, the hub waits a minute (the logs fill in), reads the container's
last log lines and state over the Docker socket (read-only) and the NAS's storage
and memory, removes what could identify a person or a secret, and asks Sonnet. The
answer goes out as a reply to the alert's own Telegram message and is logged with
the other messages, so the Alerts page shows it too. It suggests; it never acts.

Redacted before anything leaves the hub: email addresses, IPv4 and IPv6 addresses
(and MACs), passwords in URLs, bearer tokens and JWTs, `key=value` secrets, and
long tokens. The plan's choice (M26): Sonnet, with its server-side fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from . import ai
from .alerts import core, templates
from .alerts.core import AlertMessage
from .store import Store

log = logging.getLogger(__name__)

FEATURE = "explainer"
DELAY_SECONDS = 60
LOG_LINES = 200
LOG_CHARS = 12000  # the end of the log, where the failure is
TEMPLATES = ("container_down", "container_restarting")
_pending: set[asyncio.Task[None]] = set()  # kept so a waiting task is not collected

SYSTEM = (
    "You help the owner of a home server understand an alert about one of its Docker "
    "containers. From the alert, the container's state and its last log lines, give "
    "`cause`: the likely cause in one or two plain sentences, quoting the telling log line "
    "briefly when there is one; when the logs do not show a cause, say so plainly. Then "
    "`steps`: one to three short things to try first, most likely first, as the owner would "
    "do them (a setting, a command, freeing space). Never suggest deleting data, volumes or "
    "databases. Some values are redacted, shown as <ip>, <email>, <secret> or <token>. No "
    "markdown, no emoji."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "cause": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["cause", "steps"],
    "additionalProperties": False,
}

_REDACT = [
    (re.compile(r"(://)[^/\s:@]+:[^/\s@]+@"), r"\1<secret>@"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "<email>"),
    (re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"), "<token>"),
    (re.compile(r"(?i)\b(bearer|basic)\s+[\w.~+/=-]+"), r"\1 <token>"),
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key"
                r"|auth|session|cookie)([\"'\s]*[:=]\s*[\"']?)([^\s\"'&,;]+)"), r"\1\2<secret>"),
    # IPv6 with "::" (fe80::1, ::1), then full IPv6 and MACs; not clock times (12:30:45).
    (re.compile(r"(?<![\w:])(?:[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{1,4})*)?::"
                r"(?:[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{1,4})*)?(?![\w:])"), "<ip>"),
    (re.compile(r"(?<![\w:])(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{1,4}(?![\w:])"), "<ip>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<ip>"),
    (re.compile(r"\b[A-Za-z0-9+/_-]{32,}={0,2}"), "<token>"),
]


def redact(text: str) -> str:
    for pattern, replacement in _REDACT:
        text = pattern.sub(replacement, text)
    return text


def demux(raw: bytes) -> str:
    """Docker's log stream: without a TTY each chunk has an 8-byte header."""
    if len(raw) >= 8 and raw[0] in (0, 1, 2) and raw[1:4] == b"\x00\x00\x00":
        out, i = bytearray(), 0
        while i + 8 <= len(raw):
            size = int.from_bytes(raw[i + 4:i + 8], "big")
            out += raw[i + 8:i + 8 + size]
            i += 8 + size
        raw = bytes(out)
    return raw.decode("utf-8", "replace")


def container_of(problem: Any) -> str | None:
    return problem.values.get("container") or problem.values.get("name")


async def gather(socket: str, name: str,
                 transport: httpx.AsyncBaseTransport | None = None) -> tuple[str, str]:
    """(the container's state as short lines, its last log lines), both redacted."""
    if transport is None and not Path(socket).exists():
        raise RuntimeError("docker socket unavailable")
    transport = transport or httpx.AsyncHTTPTransport(uds=socket)
    async with httpx.AsyncClient(transport=transport, base_url="http://docker",
                                 timeout=10) as client:
        info = await client.get(f"/containers/{name}/json")
        info.raise_for_status()
        logs = await client.get(f"/containers/{name}/logs", params={
            "stdout": "1", "stderr": "1", "tail": str(LOG_LINES), "timestamps": "1"})
        logs.raise_for_status()
    data = info.json()
    state = data.get("State") or {}
    health = ((state.get("Health") or {}).get("Log") or [{}])[-1].get("Output")
    lines = [f"Status: {state.get('Status')}, exit code {state.get('ExitCode')}",
             f"Restarts: {data.get('RestartCount', 0)}",
             f"Killed for memory: {'yes' if state.get('OOMKilled') else 'no'}"]
    if state.get("Error"):
        lines.append(f"Docker's error: {state['Error']}")
    if health:
        lines.append(f"Last health check: {' '.join(health.split())[:300]}")
    lines.append(f"Image: {data.get('Config', {}).get('Image', '')}")
    return redact("\n".join(lines)), redact(demux(logs.content)[-LOG_CHARS:])


def house(store: Store) -> str:
    nas = store.get_cache("nas") or {}
    storage = nas.get("storage") or {}
    pools = ", ".join(f"{p['name']} {round(p['used_pct'])}% full"
                      for p in storage.get("pools") or [])
    lines = [f"Storage: {pools}"] if pools else []
    if nas.get("ram_pct") is not None:
        lines.append(f"Memory in use: {round(nas['ram_pct'])}%")
    return "\n".join(lines)


async def explain(cfg: dict[str, Any], store: Store, title: str, container: str,
                  alert: AlertMessage, now: datetime | None = None,
                  docker_transport: httpx.AsyncBaseTransport | None = None,
                  claude: ai.ClientFactory | None = None, telegram: Any = None) -> str | None:
    """Ask and reply to the alert; the reply's text, or None. Transports, `claude` and
    `telegram` are for tests."""
    now = now or datetime.now(UTC)
    if alert.status != "sent" or alert.telegram_id is None:
        return None  # held or failed: nothing to reply to
    if not ai.settings(cfg)["enabled"] or not ai.switches(store).get(FEATURE):
        return None
    try:
        state, logs = await gather(cfg["nas"]["docker_socket"], container, docker_transport)
    except Exception as exc:
        log.warning("explainer: no logs for %s: %s", container, type(exc).__name__)
        return None
    prompt = (f"Alert: {title}\nContainer: {container}\n\nState:\n{state}\n\n"
              f"The server:\n{house(store) or 'unknown'}\n\nLast log lines:\n{logs or '(none)'}")
    answer = await ai.ask(cfg, store, feature=FEATURE, model=ai.EXPLAINER_MODEL, system=SYSTEM,
                          prompt=prompt, max_tokens=4096, effort="medium", schema=SCHEMA,
                          fallback=True, now=now, client=claude, telegram=telegram)
    if answer is None:
        return None
    try:
        data = json.loads(answer)
        steps = [str(s).strip() for s in data["steps"] if str(s).strip()][:3]
        cause = str(data["cause"]).strip()
    except (json.JSONDecodeError, KeyError, TypeError):
        log.warning("explainer: the answer is not the expected JSON")
        return None
    sent = templates.message(store, "explainer", {
        "container": container, "cause": cause,
        "steps": [{"n": n, "step": step} for n, step in enumerate(steps, 1)]})
    await core.notify(store, cfg, source="explainer", category=alert.category,
                      severity="info", title=sent.title, body=sent.body, formatted=sent.html,
                      chat=alert.chat, bypass_quiet=True, reply_to=alert.telegram_id, now=now,
                      telegram=telegram)
    return sent.html


def later(cfg: dict[str, Any], store: Store, problem: Any, alert: AlertMessage,
          telegram: Any = None) -> None:
    """For a container alert that went out: explain it a minute from now."""
    container = container_of(problem)
    if problem.template not in TEMPLATES or not container or alert.telegram_id is None:
        return
    if not ai.settings(cfg)["enabled"] or not ai.switches(store).get(FEATURE):
        return

    async def wait_and_explain() -> None:
        await asyncio.sleep(DELAY_SECONDS)
        try:
            await explain(cfg, store, alert.title, container, alert, telegram=telegram)
        except Exception:
            log.exception("explaining an alert failed")

    task = asyncio.get_running_loop().create_task(wait_and_explain())
    _pending.add(task)
    task.add_done_callback(_pending.discard)
