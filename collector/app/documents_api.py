"""Paperless documents for the command palette (plan.md M25): a read-only search.

The browser never sees the Paperless token: the hub asks Paperless's full-text
search (`/api/documents/?query=`, title and content) with the widget's address
and key, and answers with titles, correspondents and dates only. The query is
never logged; it can be a name or an account number. Paperless not answering is
an answer too (`available: false`), so the palette can say so.

Checked against Paperless-ngx v3.3.4 (2026-10): correspondents filter on
`id__in`, and `fields` trims each document to what the palette shows.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Query, Request

from .models import DocumentHit, DocumentSearch
from .sources.widgets import describe

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents")

RESULTS = 8
TIMEOUT_SECONDS = 6


def _paperless(request: Request) -> tuple[str, str] | None:
    """The Paperless base URL and token, as the service tile's widget has them."""
    cfg = request.app.state.config
    widgets = cfg.get("widgets") or {}
    key = str((widgets.get("keys") or {}).get("paperless") or "").strip()
    service = next((s for s in request.app.state.store.list_services()
                    if s.widget == "paperless" and s.port), None)
    if not key or service is None:
        return None
    return f"http://{widgets.get('host', 'localhost')}:{service.port}", key


async def search(base: str, key: str, q: str,
                 transport: httpx.AsyncBaseTransport | None = None) -> list[DocumentHit]:
    headers = {"Authorization": f"Token {key}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as client:
        found = await client.get(f"{base}/api/documents/", headers=headers, params={
            "query": q, "page_size": RESULTS, "fields": "id,title,correspondent,created"})
        found.raise_for_status()
        docs = (found.json().get("results") or [])[:RESULTS]
        ids = sorted({d["correspondent"] for d in docs if d.get("correspondent")})
        names: dict[int, str] = {}
        if ids:
            who = await client.get(f"{base}/api/correspondents/", headers=headers, params={
                "id__in": ",".join(map(str, ids)), "page_size": len(ids), "fields": "id,name"})
            who.raise_for_status()
            names = {c["id"]: c["name"] for c in who.json().get("results") or []}
    return [DocumentHit(id=d["id"], title=d.get("title") or "Untitled",
                        correspondent=names.get(d.get("correspondent") or 0),
                        created=str(d.get("created") or "")[:10] or None)
            for d in docs]


@router.get("/search")
async def search_documents(
    request: Request, q: Annotated[str, Query(min_length=2, max_length=100)]
) -> Any:
    now = datetime.now(UTC)
    paperless = _paperless(request)
    if paperless is None:
        return DocumentSearch(as_of=now, available=False,
                              reason="Not set up in the hub").model_dump(mode="json")
    transport = getattr(request.app.state, "documents_transport", None)  # tests
    try:
        results = await search(*paperless, q.strip(), transport)
    except Exception as exc:
        # The class only: the request carries the token and the query.
        log.warning("paperless search failed: %s", type(exc).__name__)
        return DocumentSearch(as_of=now, available=False,
                              reason=describe(exc)).model_dump(mode="json")
    return DocumentSearch(as_of=now, results=results).model_dump(mode="json")
