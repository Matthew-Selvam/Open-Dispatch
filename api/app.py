"""FastAPI app — POST /dispatch + status endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from api.queue import get_queue
from api.schema import ContentUnit, parse_target, validate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("open-dispatch.api")

app = FastAPI(
    title="Open-Dispatch",
    version="0.1.0",
    description="One API to dispatch content anywhere — open-source.",
)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"status": "ok", "version": app.version}


@app.post("/dispatch", status_code=202)
async def dispatch(request: Request) -> JSONResponse:
    body = await request.json()
    unit = ContentUnit.from_dict(body)
    errs = validate(unit)
    if errs:
        raise HTTPException(status_code=400, detail={"errors": errs})

    q = get_queue()
    sf = unit.scheduled_for or datetime.now(tz=timezone.utc).isoformat()
    enqueued = []
    for target in unit.targets:
        platform, account = parse_target(target)
        key = f"{platform}:{account or 'default'}"
        row_id = q.enqueue(unit.to_dict(), key, sf)
        enqueued.append({"id": row_id, "target": target, "scheduled_for": sf})

    return JSONResponse(
        status_code=202,
        content={"unit_id": unit.id, "enqueued": enqueued},
    )


@app.get("/queue")
def list_queue(status: str | None = None) -> dict[str, Any]:
    rows = get_queue().list_all(status=status)
    return {"count": len(rows), "rows": rows}


@app.get("/queue/{row_id}")
def get_row(row_id: str) -> dict[str, Any]:
    row = get_queue().get(row_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return row


@app.post("/queue/{row_id}/retry")
def retry_row(row_id: str) -> dict[str, Any]:
    q = get_queue()
    row = q.get(row_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    q._update(row_id, {"status": "queued", "last_error": None})  # noqa: SLF001
    return {"id": row_id, "status": "queued"}
