"""FastAPI app — JSON API + HTMX web UI (dashboard, composer)."""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from adapters import ADAPTERS
from ai import AdaptError, adapt_caption_async
from api.queue import get_queue
from api.schema import ContentUnit, parse_target, validate
from media import PLATFORM_IMAGE_SPECS, TranscodeError, transcode_image_bytes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("open-dispatch.api")

VERSION = "0.2.0"

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "web" / "templates"
STATIC_DIR = REPO_ROOT / "web" / "static"

app = FastAPI(
    title="Open-Dispatch",
    version=VERSION,
    description="One API to dispatch content anywhere — open-source.",
    docs_url="/docs",
    redoc_url=None,
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ─── Helpers ──────────────────────────────────────────────────────────────

def _platforms_configured() -> set[str]:
    """Which platforms have at least the canonical credential env var set?"""
    checks = {
        "telegram":  ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"),
        "twitter":   ("TWITTER_API_KEY", "TWITTER_ACCESS_TOKEN"),
        "instagram": ("IG_USER_ID", "IG_TOKEN"),
        "bluesky":   ("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"),
        "linkedin":  ("LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR_URN"),
        "threads":   ("THREADS_USER_ID", "THREADS_ACCESS_TOKEN"),
        "youtube":   ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"),
    }
    return {
        platform for platform, envs in checks.items()
        if all(os.getenv(e) for e in envs)
    }


def _build_formats(text: str, formats_json: str | None) -> dict[str, Any]:
    """Build per-platform formats dict from either raw JSON or a single text field."""
    if formats_json and formats_json.strip():
        try:
            parsed = json.loads(formats_json)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as e:
            raise ValueError(f"formats_json: {e}") from e
    # Default: use the text across the common format keys for every selected platform
    return {
        "telegram_message":  {"text": text},
        "twitter_thread":    {"tweets": [text]},
        "bluesky_post":      {"text": text},
        "instagram_post":    {"caption": text},
        "linkedin_post":     {"text": text},
        "threads_post":      {"text": text},
        # youtube_short omitted on purpose — needs a video_path the form
        # composer can't supply yet. Use AI adapter + Advanced JSON for now.
    }


def _wants_html(request: Request) -> bool:
    """Heuristic — does this request expect HTML (browser) vs JSON (API)?"""
    accept = request.headers.get("accept", "")
    return "text/html" in accept or "hx-request" in {k.lower() for k in request.headers}


# ─── JSON API (unchanged) ─────────────────────────────────────────────────

@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"status": "ok", "version": VERSION}


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


@app.get("/queue/{row_id}/json")
def get_row_json(row_id: str) -> dict[str, Any]:
    row = get_queue().get(row_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return row


@app.post("/queue/{row_id}/retry")
async def retry_row(request: Request, row_id: str) -> Any:
    q = get_queue()
    row = q.get(row_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    q._update(row_id, {"status": "queued", "last_error": None})  # noqa: SLF001
    if _wants_html(request):
        # HTMX caller: re-render the queue fragment
        return await _render_queue_fragment(request, status=None)
    return {"id": row_id, "status": "queued"}


# ─── Web UI ────────────────────────────────────────────────────────────────

def _row_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = Counter(r.get("status", "") for r in rows)
    counts["all"] = len(rows)
    return counts


async def _render_queue_fragment(request: Request, status: str | None) -> HTMLResponse:
    rows = get_queue().list_all(status=status)
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return templates.TemplateResponse(
        request, "_queue_table.html",
        {"rows": rows, "filter_status": status},
    )


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, status: str | None = None) -> HTMLResponse:
    all_rows = get_queue().list_all()
    rows = [r for r in all_rows if not status or r.get("status") == status]
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return templates.TemplateResponse(
        request, "dashboard.html",
        {
            "rows": rows,
            "counts": _row_counts(all_rows),
            "filter_status": status,
            "active": "dashboard",
            "version": VERSION,
            "now": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        },
    )


@app.get("/_queue-fragment", response_class=HTMLResponse)
async def queue_fragment(request: Request, status: str | None = None) -> HTMLResponse:
    return await _render_queue_fragment(request, status)


@app.get("/compose", response_class=HTMLResponse)
async def compose_page(request: Request) -> HTMLResponse:
    platforms = sorted(ADAPTERS.keys())
    configured = _platforms_configured()
    return templates.TemplateResponse(
        request, "compose.html",
        {
            "platforms": platforms,
            "configured": configured,
            "active": "compose",
            "version": VERSION,
            "now": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        },
    )


@app.post("/_compose", response_class=HTMLResponse)
async def compose_submit(
    request: Request,
    text: str = Form(""),
    platforms: list[str] = Form(default=[]),
    targets_override: str = Form(""),
    scheduled_for: str = Form(""),
    webhook_url: str = Form(""),
    formats_json: str = Form(""),
) -> HTMLResponse:
    errors: list[str] = []
    targets: list[str] = []
    if targets_override.strip():
        targets = [t.strip() for t in targets_override.split(",") if t.strip()]
    else:
        targets = [p for p in platforms if p]
    if not targets:
        errors.append("pick at least one platform or enter override targets")
    if not text and not formats_json:
        errors.append("text or formats_json is required")

    try:
        formats = _build_formats(text, formats_json or None)
    except ValueError as e:
        errors.append(str(e))
        formats = {}

    if errors:
        return templates.TemplateResponse(
            request, "_compose_result.html",
            {"ok": False, "errors": errors},
        )

    unit = ContentUnit.from_dict({
        "category": "web",
        "targets": targets,
        "scheduled_for": scheduled_for.strip() or None,
        "formats": formats,
        "webhook_url": webhook_url.strip() or None,
    })
    errs = validate(unit)
    if errs:
        return templates.TemplateResponse(
            request, "_compose_result.html",
            {"ok": False, "errors": errs},
        )

    q = get_queue()
    sf = unit.scheduled_for or datetime.now(tz=timezone.utc).isoformat()
    enqueued = []
    for target in unit.targets:
        platform, account = parse_target(target)
        key = f"{platform}:{account or 'default'}"
        row_id = q.enqueue(unit.to_dict(), key, sf)
        enqueued.append({"id": row_id, "target": target, "scheduled_for": sf})

    return templates.TemplateResponse(
        request, "_compose_result.html",
        {"ok": True, "unit_id": unit.id, "enqueued": enqueued},
    )


@app.get("/queue/{row_id}")
async def row_detail(request: Request, row_id: str) -> Any:
    """Content-negotiated: HTML for browsers, JSON for API consumers.

    Browsers send `Accept: text/html,...`, curl/SDKs send `*/*` or
    `application/json`. We return HTML only when the client clearly
    prefers it so we don't break existing API consumers.
    """
    row = get_queue().get(row_id)
    wants_html = _wants_html(request)
    if not row:
        if wants_html:
            return HTMLResponse(
                "<h1>404 — row not found</h1>"
                f"<p>No queue row with id <code>{row_id}</code>.</p>"
                "<p><a href='/'>Back to dashboard</a></p>",
                status_code=404,
            )
        raise HTTPException(status_code=404, detail="not found")
    if wants_html:
        return templates.TemplateResponse(
            request, "row_detail.html",
            {
                "row": row,
                "unit_json": json.dumps(row.get("unit", {}), indent=2, ensure_ascii=False),
                "active": "dashboard",
                "version": VERSION,
                "now": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            },
        )
    # Default to JSON for API consumers (back-compat with the documented contract)
    return row


# Redirect bare /queue (GET) to dashboard when called from a browser
@app.get("/queue/", response_class=HTMLResponse, include_in_schema=False)
async def queue_redirect() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=307)


# ─── AI caption adaptation ────────────────────────────────────────────────

@app.post("/ai/adapt")
async def ai_adapt(request: Request) -> dict[str, Any]:
    """Adapt a source caption into per-platform formats.

    Request body:
      { "text": "...", "platforms": ["twitter","bluesky",...], "provider": "openrouter"|"ollama"|"heuristic" }

    Response:
      { "ok": true, "formats": {...}, "provider": "openrouter" }

    Provider defaults: ollama if OLLAMA_HOST set, else openrouter if
    OPENROUTER_API_KEY set, else heuristic (no LLM).
    """
    body = await request.json()
    text = (body.get("text") or "").strip()
    platforms = body.get("platforms") or []
    provider = body.get("provider")
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if not isinstance(platforms, list) or not platforms:
        raise HTTPException(status_code=400, detail="platforms must be a non-empty list")

    try:
        formats = await adapt_caption_async(text, platforms, provider=provider)
    except AdaptError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {"ok": True, "formats": formats}


@app.post("/_compose-adapt", response_class=HTMLResponse)
async def compose_adapt_htmx(
    request: Request,
    text: str = Form(""),
    platforms: list[str] = Form(default=[]),
) -> HTMLResponse:
    """HTMX endpoint: takes the in-progress composer text + selected platforms,
    returns a JSON formats blob to drop into the Advanced textarea.
    """
    if not text.strip() or not platforms:
        return HTMLResponse(
            '<div class="alert alert-error">'
            "<strong>Need text and at least one platform.</strong>"
            "</div>",
        )
    try:
        formats = await adapt_caption_async(text, platforms)
    except AdaptError as e:
        return HTMLResponse(
            f'<div class="alert alert-error"><strong>Adapt failed:</strong> {e}</div>',
        )
    pretty = json.dumps(formats, indent=2, ensure_ascii=False)
    return HTMLResponse(
        '<div class="alert alert-success">'
        "<strong>Adapted.</strong> Paste this into the Advanced JSON box "
        "(or just submit — the adapter ran on the server side):"
        f'<pre class="mono small" style="margin-top:8px;max-height:300px;overflow:auto">{pretty}</pre>'
        "</div>",
    )


# ─── Media transcoding ────────────────────────────────────────────────────

@app.get("/media/specs")
def media_specs() -> dict[str, Any]:
    """Return the per-platform image-spec table so clients can introspect
    what we'll do to their images before they upload."""
    return {
        name: {
            "max_width": spec.max_width,
            "max_height": spec.max_height,
            "aspect_min": spec.aspect_min,
            "aspect_max": spec.aspect_max,
            "format": spec.format,
            "quality": spec.quality,
            "description": spec.description,
        }
        for name, spec in PLATFORM_IMAGE_SPECS.items()
    }


@app.post("/media/transcode")
async def media_transcode(request: Request) -> Any:
    """Transcode raw image bytes for one platform spec.

    Two ways to call:
    1. Raw body: `Content-Type: image/<anything>`, body = image bytes,
       query param `?platform=instagram` — returns the transcoded JPEG bytes
       directly with Content-Type: image/jpeg.
    2. multipart/form-data with fields `image` (file) and `platform` — same response.
    """
    from fastapi.responses import Response
    platform = request.query_params.get("platform", "")
    blob: bytes | None = None

    content_type = (request.headers.get("content-type") or "").lower()
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        platform = platform or str(form.get("platform", ""))
        upload = form.get("image")
        if upload is None:
            raise HTTPException(status_code=400, detail="multipart: missing 'image' field")
        blob = await upload.read()  # type: ignore[union-attr]
    else:
        blob = await request.body()

    if not platform:
        raise HTTPException(status_code=400, detail="platform query param required")
    if not blob:
        raise HTTPException(status_code=400, detail="empty image body")

    try:
        out = transcode_image_bytes(blob, platform)
    except TranscodeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    spec = PLATFORM_IMAGE_SPECS[platform]
    mime = "image/jpeg" if spec.format == "JPEG" else "image/png"
    return Response(content=out, media_type=mime)
