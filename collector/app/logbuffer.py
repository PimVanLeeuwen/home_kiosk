"""The collector's last log records in memory, for the MCP `hub_logs` tool (plan.md M34).

The log is written to be free of personal data (names, titles, addresses are never logged),
but an exception can carry a URL with a key in it, so what is read back goes through the
alert explainer's redaction. Kept in memory only: lost on a restart, which Dozzle covers.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any

KEEP = 1000
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class RingHandler(logging.Handler):
    def __init__(self, keep: int = KEEP) -> None:
        super().__init__(level=logging.INFO)
        self.records: deque[dict[str, Any]] = deque(maxlen=keep)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = record.getMessage()
            if record.exc_info:
                text += "\n" + logging.Formatter().formatException(record.exc_info)
        except Exception:  # a log call with the wrong arguments must not break logging
            text = str(record.msg)
        self.records.append({"at": datetime.fromtimestamp(record.created, UTC),
                             "level": record.levelname, "logger": record.name, "text": text})


HANDLER = RingHandler()


def install() -> None:
    """Once, at start-up: the root logger keeps a copy of everything from INFO up."""
    root = logging.getLogger()
    if HANDLER not in root.handlers:
        root.addHandler(HANDLER)


def recent(minutes: int = 60, level: str = "INFO", limit: int = 100,
           handler: RingHandler = HANDLER, now: datetime | None = None) -> list[dict[str, Any]]:
    """The newest records of at least `level` from the last `minutes`, oldest first, redacted."""
    from .explainer import redact  # the explainer pulls in the AI client; only when asked

    level = level.upper() if level.upper() in LEVELS else "INFO"
    floor = LEVELS.index(level)
    since = (now or datetime.now(UTC)) - timedelta(minutes=max(minutes, 1))
    found = [r for r in handler.records
             if r["level"] in LEVELS and LEVELS.index(r["level"]) >= floor
             and r["at"] >= since]
    return [{"at": r["at"].isoformat(timespec="seconds"), "level": r["level"],
             "logger": r["logger"], "text": redact(r["text"])[:4000]}
            for r in found[-max(min(limit, 500), 1):]]
