"""Explain the open warnings (plan.md M29 step 6), from a button under the briefing.

When the morning briefing lists open warnings or errors, it gets one button,
"Explain warnings". A tap reaches the bot (bot.py), which asks Sonnet here for
each open alert's likely cause and what to try first, and replies to the
briefing. Part of the "Alert explainer" switch, which it widens past container
alerts: without the switch there is no button.

Data sent: each alert's own title and text (redacted like the container logs),
how long it has been open, and the NAS's storage and memory; the same input is
answered from the cache, so a second tap costs nothing.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from . import ai, explainer
from .alerts import core, rules, templates
from .store import Store

log = logging.getLogger(__name__)

CALLBACK = "explain_open"  # the button's callback_data
BUTTON = {"text": "Explain warnings", "callback_data": CALLBACK}
MAX_ALERTS = 8

SYSTEM = (
    "You help the owner of a home server understand the alerts that are open on it. For "
    "each numbered alert give `cause`: what it means and its likely cause in one or two "
    "plain sentences, and `todo`: the first thing to try or check, as the owner would do it, "
    "or that it needs nothing when it will pass by itself (an outage at a provider, a "
    "maintenance window). Use only what is given and say so when it does not show a cause. "
    "Never suggest deleting data, volumes or databases. Some values are redacted, shown as "
    "<ip>, <email>, <secret> or <token>. No markdown, no emoji."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "alerts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"n": {"type": "integer"}, "cause": {"type": "string"},
                               "todo": {"type": "string"}},
                "required": ["n", "cause", "todo"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["alerts"],
    "additionalProperties": False,
}


def open_alerts(store: Store) -> list[dict[str, Any]]:
    """Open alerts as the briefing's House lists them: errors first, then the
    oldest; train alerts stay out (the briefing has this morning's train)."""
    return sorted((i for i in rules.open_incidents(store).values() if i["rule"] != "train"),
                  key=lambda i: (i["severity"] != "error", i["opened_at"]))


def available(cfg: dict[str, Any], store: Store) -> bool:
    return ai.settings(cfg)["enabled"] and bool(ai.switches(store).get(explainer.FEATURE))


def buttons(cfg: dict[str, Any], store: Store) -> list[dict[str, str]] | None:
    """The briefing's button row: only with open alerts and the switch on."""
    return [BUTTON] if open_alerts(store) and available(cfg, store) else None


async def explain(cfg: dict[str, Any], store: Store, chat: str, reply_to: int,
                  now: datetime | None = None, claude: ai.ClientFactory | None = None,
                  telegram: Any = None) -> core.AlertMessage | None:
    """Explain what is open now and reply to `reply_to` in `chat`; None when
    Claude gave no answer (off, the cap, a failure)."""
    now = now or datetime.now(UTC)
    found = open_alerts(store)[:MAX_ALERTS]
    if not found:
        sent = templates.message(store, "explained_none", {})
    else:
        lines = []
        for n, alert in enumerate(found, 1):
            lines.append(f"{n}. [{core.LEVEL.get(alert['severity'], '')}, open "
                         f"{rules._duration(alert['opened_at'], now)}] "
                         f"{explainer.redact(alert['title'])}")
            if alert.get("body"):
                lines.append("   " + explainer.redact(alert["body"]).replace("\n", "\n   "))
        prompt = ("Open alerts:\n" + "\n".join(lines)
                  + f"\n\nThe server:\n{explainer.house(store) or 'unknown'}")
        answer = await ai.ask(cfg, store, feature=explainer.FEATURE, model=ai.EXPLAINER_MODEL,
                              system=SYSTEM, prompt=prompt, max_tokens=4096, effort="medium",
                              schema=SCHEMA, fallback=True, now=now, client=claude,
                              telegram=telegram)
        if answer is None:
            return None
        try:
            by_n = {int(a["n"]): a for a in json.loads(answer)["alerts"]}
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            log.warning("explain open: the answer is not the expected JSON")
            return None
        items = [{"title": alert["title"], "cause": str(by_n[n]["cause"]).strip(),
                  "todo": str(by_n[n]["todo"]).strip()}
                 for n, alert in enumerate(found, 1) if n in by_n]
        if not items:
            return None
        sent = templates.message(store, "explained", {"alerts": items})
    return await core.notify(store, cfg, source="explainer", category="rules", severity="info",
                             title=sent.title, body=sent.body, formatted=sent.html, chat=chat,
                             bypass_quiet=True, reply_to=reply_to, now=now, telegram=telegram)
