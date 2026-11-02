"""Which rule alerts get a picture (plan.md M31 step 4), and its figures.

Disk space (the pool's last 30 days), the storage box (a gauge) and the portfolio's
move (the biggest movers). Each returns a painter for `core.notify`, which paints it
once, sends it with the message and keeps it for the message's page.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from PIL import Image

from .. import paint_notify
from ..portfolio.moves import day_move
from ..store import Store
from . import core

Painter = Callable[[], Image.Image | None]
HISTORY_DAYS = 30


def disk(store: Store, pool: str, free: str, limit_pct: float) -> Image.Image | None:
    found = next((p for p in ((store.get_cache("nas") or {}).get("storage") or {}).get("pools")
                  or [] if p.get("name") == pool), None)
    if not found or not found.get("total_bytes"):
        return None
    total = found["total_bytes"]
    history = [row["used_bytes"] / total * 100
               for row in store.storage_history(f"/{pool}", HISTORY_DAYS)]
    return paint_notify.disk(pool, found["used_pct"], free, limit_pct, history)


def move(cfg: dict[str, Any], store: Store, now: datetime) -> Image.Image | None:
    portfolio = store.get_cache("portfolio")
    if not portfolio or not portfolio.get("holdings"):
        return None
    _, pct = day_move(portfolio)
    movers = [(h["symbol"], h.get("day_pct") or 0.0) for h in portfolio["holdings"]]
    return paint_notify.move(pct, movers, f"{core.local(now, cfg):%a %-d %b}")


def for_problem(cfg: dict[str, Any], store: Store, problem: Any, settings: dict[str, Any],
                now: datetime) -> Painter | None:
    """The painter for a rule alert's opening message, or None for a rule without one."""
    values = problem.values
    if problem.rule == "disk_space":
        return lambda: disk(store, values["pool"], values["free"], settings["threshold_pct"])
    if problem.rule == "storage_box":
        return lambda: paint_notify.gauge("Storage box", values["used_pct"], values["free"],
                                          values["total"], settings["threshold_pct"])
    if problem.rule == "portfolio_move":
        return lambda: move(cfg, store, now)
    return None
