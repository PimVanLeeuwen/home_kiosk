"""The desk panels' side of the hub (plan.md M16). A panel only knows its
name and asks /api/desk/<name> for what to show. For now a stub that answers
the bring-up firmware, so a panel can prove it reaches the hub; the layouts
and screens come with the rest of M16.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter

router = APIRouter(prefix="/api/desk")

# The three panels, and "test" for a board on the bench.
PanelName = Literal["now", "home", "house", "test"]


@router.get("/{name}")
def desk(name: PanelName) -> dict[str, Any]:
    return {"name": name, "as_of": datetime.now(UTC).isoformat(), "stale": False, "screens": []}
