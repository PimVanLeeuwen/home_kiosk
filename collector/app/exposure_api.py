"""The outside port scan's side of the hub (M14 step 2).

The exposure-scan GitHub workflow joins the tailnet as a tagged, temporary
node that the ACL only lets reach the hub's API. It asks for the current home
IP (the house has no static IP), scans it over the normal internet, and posts
the result back. Both ends prove themselves with the NOTIFY_KEY, like every
other sender. The IP is only handed out on that key; it is not kept here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .alerts.api import notify_key
from .models import PortScan, PortScanRun
from .security import same_origin_json
from .sources import exposure

router = APIRouter(prefix="/api/exposure")

SCAN_KEY = "port_scan"
MAX_RUNS = 30

Port = Annotated[int, Field(ge=1, le=65535)]


class ScanIn(BaseModel):
    started: datetime
    finished: datetime
    ports_checked: Annotated[int, Field(ge=0, le=65535)]
    open: Annotated[list[Port], Field(max_length=1024)]
    error: Annotated[str | None, Field(max_length=300)] = None


@router.get("/target", dependencies=[Depends(notify_key)])
async def target() -> dict[str, str]:
    """The home IP right now, for the scan to aim at."""
    async with httpx.AsyncClient(timeout=exposure.TIMEOUT_SECONDS) as client:
        ip = await exposure.home_ip(client)
    if not ip:
        raise HTTPException(503, "The home IP could not be found.")
    return {"ip": ip}


@router.post("/scan", dependencies=[Depends(notify_key), Depends(same_origin_json)])
def receive(body: ScanIn, request: Request) -> PortScan:
    store = request.app.state.store
    previous = (store.get_cache(SCAN_KEY) or {}).get("runs", [])
    run = PortScanRun(**body.model_dump() | {"open": sorted(set(body.open))})
    runs = [run, *(PortScanRun.model_validate(r) for r in previous)][:MAX_RUNS]
    scan = PortScan(as_of=datetime.now(UTC), runs=runs)
    store.put_cache(SCAN_KEY, scan.model_dump(mode="json"))
    return scan


@router.get("/scan")
def latest(request: Request) -> Any:
    payload = request.app.state.store.get_cache(SCAN_KEY)
    if payload is None:
        return JSONResponse(status_code=503, content={"detail": "no port scan received yet"})
    return payload
