"""Market notes (plan.md M29 step 4): why the big movers moved, from the feeds.

The two holdings that moved most in the last session, each by more than 1%,
go to Haiku with their ticker, Ghostfolio's name for them and their move in %
(never amounts or values), with the indices' moves and the last 24 hours of
headlines from every feed (title and first line). Claude answers one short
sentence per mover from those alone, or says the feeds do not explain it.
Used by the morning briefing's Markets section and the Portfolio reports.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from .. import ai
from ..store import Store

log = logging.getLogger(__name__)

FEATURE = "market_notes"
THRESHOLD_PCT = 1.0  # a mover moved more than this, either way
MOVERS = 2
WINDOW = timedelta(hours=24)
MAX_ARTICLES = 120
LINE_CHARS = 160
NOTE_MAX = 160
UNEXPLAINED = "No news in your feeds explains it."

SYSTEM = (
    "You explain, in one short sentence each, why a stock or fund in someone's portfolio "
    "moved in the last trading session. You get each mover's ticker, name and move, the "
    "indices' moves, and numbered headlines from the owner's news feeds (title, then the "
    "feed's first line). Use only those: give the reason, not the percentage (the owner "
    "sees it). A fund or stock that moved with its market may say so, naming the index. "
    f"When nothing given explains a move, the note is exactly \"{UNEXPLAINED}\" Never "
    f"guess. English, at most {NOTE_MAX} characters, no markdown, no emoji."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}, "note": {"type": "string"}},
                "required": ["symbol", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["notes"],
    "additionalProperties": False,
}


def movers(portfolio: dict[str, Any]) -> list[dict[str, Any]]:
    """The two holdings that moved most, each by more than the threshold."""
    big = [h for h in portfolio.get("holdings") or []
           if abs(h.get("day_pct") or 0.0) > THRESHOLD_PCT]
    return sorted(big, key=lambda h: abs(h["day_pct"]), reverse=True)[:MOVERS]


def _headlines(store: Store, now: datetime) -> list[str]:
    with store.connect() as conn:
        rows = conn.execute(
            "SELECT source, title, summary FROM article WHERE published >= ? "
            "ORDER BY published DESC, id LIMIT ?",
            ((now - WINDOW).isoformat(), MAX_ARTICLES)).fetchall()
    out = []
    for i, row in enumerate(rows, 1):
        first = " ".join((row["summary"] or "").split())[:LINE_CHARS]
        out.append(f"{i}. [{row['source']}] {row['title']}" + (f" | {first}" if first else ""))
    return out


async def notes(cfg: dict[str, Any], store: Store, portfolio: dict[str, Any],
                indices: dict[str, Any] | None, now: datetime | None = None,
                claude: ai.ClientFactory | None = None) -> dict[str, str]:
    """A note per big mover, by ticker; empty without movers or an answer."""
    now = now or datetime.now(UTC)
    big = movers(portfolio)
    if not big or not ai.switches(store).get(FEATURE):
        return {}
    lines = ["Movers in the last session:"]
    lines += [f"- {h['symbol']} ({h.get('name') or h['symbol']}): {h['day_pct']:+.2f}%"
              for h in big]
    index_moves = [f"{q['label']} {q['day_pct']:+.2f}%"
                   for q in (indices or {}).get("indices") or []]
    if index_moves:
        lines.append("Indices: " + ", ".join(index_moves))
    lines += ["", "Headlines from the last 24 hours:", *(_headlines(store, now) or ["(none)"])]
    answer = await ai.ask(cfg, store, feature=FEATURE, model=ai.SCHEDULED_MODEL, system=SYSTEM,
                          prompt="\n".join(lines), max_tokens=1024, schema=SCHEMA, now=now,
                          client=claude)
    if answer is None:
        return {}
    try:
        data = json.loads(answer)
    except json.JSONDecodeError:
        log.warning("market notes: the answer is not JSON")
        return {}
    found = {str(n.get("symbol")): " ".join(str(n.get("note") or "").split())[:NOTE_MAX]
             for n in data.get("notes") or []}
    # In the movers' order, only theirs, and only real notes.
    return {h["symbol"]: found[h["symbol"]] for h in big if found.get(h["symbol"])}
