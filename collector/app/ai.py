"""Claude for a few written extras (plan.md M26), with a hard monthly cap.

Every feature asks through `ask()`, which:
- answers from `ai_answer` when the same feature already answered the same input
  (a hash of model, system and prompt), so a schedule never pays twice;
- refuses when the feature is switched off, the key is missing, or this month's
  spend has reached the cap; the caller then shows what it had, or nothing;
- records each call's token usage and its price in `ai_usage`, and sends one
  Telegram note per month when the spend passes 80% of the cap.

Prices are Anthropic's list prices in dollars per million tokens (2026-10). The
cap is in euros but counted in dollars: a dollar is worth less than a euro, so
the hub stops a little before EUR 5 is really spent. A spend limit on the key's
workspace in the Anthropic Console, a little above it, is the backstop.

Nothing here logs a prompt or an answer: they can hold the house's state.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import anthropic

from .alerts import core
from .store import Store

log = logging.getLogger(__name__)

# The plan's choice (M26): Haiku for the scheduled features, Sonnet for the alert explainer.
SCHEDULED_MODEL = "claude-haiku-5-5"
EXPLAINER_MODEL = "claude-sonnet-5-5"


@dataclass(frozen=True)
class Price:
    """Dollars per million tokens. Cache writes (5 minutes) cost 1.25 times input."""
    input: float
    output: float
    cache_read: float
    # Haiku 5.5 charges more for a prompt over 100K tokens.
    long_from: int | None = None
    long_input: float | None = None
    long_output: float | None = None


PRICES = {
    "claude-haiku-5-5": Price(0.10, 0.50, 0.01, long_from=100_000, long_input=0.50,
                              long_output=2.50),
    "claude-sonnet-5-5": Price(2.00, 10.00, 0.20),
}

# The features, with their switch in Settings. Each step of M26 adds its own.
FEATURES: dict[str, str] = {
    "update_notes": "Update notes",  # app/update_notes.py, app/pinned.py
    "briefing": "Morning digest",  # app/briefing.py
    "headlines": "Grouped headlines",  # app/news/stories.py
}

WARN_SHARE = 0.8
TIMEOUT_SECONDS = 60

TABLES = """
CREATE TABLE IF NOT EXISTS ai_usage (
    ts            TEXT NOT NULL,  -- UTC, ISO
    feature       TEXT NOT NULL,
    model         TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_read    INTEGER NOT NULL DEFAULT 0,
    cache_write   INTEGER NOT NULL DEFAULT 0,
    cost_usd      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ai_usage_ts ON ai_usage (ts);

CREATE TABLE IF NOT EXISTS ai_answer (
    key      TEXT PRIMARY KEY,  -- sha256 of feature, model, system and prompt
    feature  TEXT NOT NULL,
    ts       TEXT NOT NULL,
    text     TEXT NOT NULL
);
"""

SETTING = "ai_features"  # {feature: bool}; off until switched on in Settings
WARNED = "ai_warned_month"  # "2026-10" once this month's 80% note went out


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    a = cfg.get("ai") or {}
    key = str(a.get("api_key") or "").strip()
    return {"api_key": key, "cap_eur": float(a.get("cap_eur") or 5), "enabled": bool(key)}


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


def switches(store: Store) -> dict[str, bool]:
    saved = core.get_setting(store, SETTING, {})
    return {name: bool(saved.get(name, False)) for name in FEATURES}


def set_switches(store: Store, changes: dict[str, bool]) -> dict[str, bool]:
    unknown = set(changes) - set(FEATURES)
    if unknown:
        raise ValueError(f"unknown feature: {', '.join(sorted(unknown))}")
    core.put_setting(store, SETTING, switches(store) | changes)
    return switches(store)


def cost_usd(model: str, usage: Any) -> float:
    price = PRICES[model]
    read = getattr(usage, "cache_read_input_tokens", None) or 0
    write = getattr(usage, "cache_creation_input_tokens", None) or 0
    prompt = usage.input_tokens + read + write
    long = price.long_from is not None and prompt > price.long_from
    rate_in = price.long_input if long and price.long_input else price.input
    rate_out = price.long_output if long and price.long_output else price.output
    return (usage.input_tokens * rate_in + write * rate_in * 1.25 + read * price.cache_read
            + usage.output_tokens * rate_out) / 1_000_000


def month_key(now: datetime, cfg: dict[str, Any]) -> str:
    return core.local(now, cfg).strftime("%Y-%m")


def month_spend(store: Store, cfg: dict[str, Any], now: datetime) -> tuple[float, int]:
    """This month's spend in dollars and the number of calls, by the house's calendar."""
    start = core.local(now, cfg).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    with store.connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) AS spent, COUNT(*) AS calls FROM ai_usage "
            "WHERE ts >= ?", (start.astimezone(UTC).isoformat(),)).fetchone()
    return float(row["spent"]), int(row["calls"])


def answer_key(feature: str, model: str, system: str, prompt: str) -> str:
    return hashlib.sha256("\x00".join((feature, model, system, prompt)).encode()).hexdigest()


def cached(store: Store, key: str) -> str | None:
    with store.connect() as conn:
        row = conn.execute("SELECT text FROM ai_answer WHERE key = ?", (key,)).fetchone()
    return row["text"] if row else None


def _record(store: Store, now: datetime, feature: str, model: str, usage: Any) -> None:
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO ai_usage (ts, feature, model, input_tokens, output_tokens, cache_read, "
            "cache_write, cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (now.isoformat(), feature, model, usage.input_tokens, usage.output_tokens,
             getattr(usage, "cache_read_input_tokens", None) or 0,
             getattr(usage, "cache_creation_input_tokens", None) or 0,
             cost_usd(model, usage)))


async def _warn_once(store: Store, cfg: dict[str, Any], now: datetime, spent: float,
                     cap: float, telegram: Any) -> None:
    month = month_key(now, cfg)
    if spent < cap * WARN_SHARE or core.get_setting(store, WARNED, "") == month:
        return
    core.put_setting(store, WARNED, month)
    await core.notify(
        store, cfg, source="ai", category="ai", severity="warning",
        title=f"AI spend at {spent / cap:.0%} of the monthly cap",
        body=f"{spent:.2f} of {cap:.2f} spent this month. At the cap the hub stops asking "
             "Claude until the 1st.", now=now, telegram=telegram)


ClientFactory = Callable[[str], Any]


def _client(api_key: str) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=2)


async def ask(cfg: dict[str, Any], store: Store, *, feature: str, model: str, system: str,
              prompt: str, max_tokens: int = 1024, effort: str = "low",
              schema: dict[str, Any] | None = None,
              now: datetime | None = None, client: ClientFactory | None = None,
              telegram: Any = None) -> str | None:
    """Claude's answer for a feature, or None (off, no key, at the cap, or a failure).
    With a JSON `schema` the answer is JSON in that shape (structured output).
    `client`, `now` and `telegram` are for tests."""
    now = now or datetime.now(UTC)
    s = settings(cfg)
    if not s["enabled"] or not switches(store).get(feature):
        return None
    shape = json.dumps(schema, sort_keys=True) if schema else ""
    key = answer_key(feature, model, system + shape, prompt)
    if (text := cached(store, key)) is not None:
        return text
    spent, _ = month_spend(store, cfg, now)
    if spent >= s["cap_eur"]:
        log.info("AI %s skipped: this month's cap is reached", feature)
        return None
    try:
        response = await (client or _client)(s["api_key"]).messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": effort}
            | ({"format": {"type": "json_schema", "schema": schema}} if schema else {}))
    except anthropic.RateLimitError:
        log.warning("AI %s: rate limited", feature)
        return None
    except anthropic.APIStatusError as exc:
        log.warning("AI %s failed: HTTP %s", feature, exc.status_code)
        return None
    except anthropic.APIConnectionError:
        log.warning("AI %s failed: the API did not answer", feature)
        return None
    _record(store, now, feature, model, response.usage)
    await _warn_once(store, cfg, now, month_spend(store, cfg, now)[0], s["cap_eur"], telegram)
    if response.stop_reason == "refusal":
        log.warning("AI %s: the model declined", feature)
        return None
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text or response.stop_reason == "max_tokens":
        log.warning("AI %s: no usable answer (%s)", feature, response.stop_reason)
        return None
    with store.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO ai_answer (key, feature, ts, text) "
                     "VALUES (?, ?, ?, ?)", (key, feature, now.isoformat(), text))
    return text
