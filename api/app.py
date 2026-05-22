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
from profiles import (
    CRED_LABELS,
    PASSWORD_FIELDS,
    PLATFORM_CRED_MAP,
    PLATFORM_EMOJI,
    PRESET_COLORS,
    Profile,
    ProfileStore,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("open-dispatch.api")

try:
    from importlib.metadata import version as _pkg_version

    VERSION = _pkg_version("open-dispatch")
except Exception:  # not installed as a package (dev checkout) — keep in sync w/ pyproject
    VERSION = "0.4.0"

# Captured once at import — used to compute server uptime on /healthz.
_START_TIME = datetime.now(tz=timezone.utc)

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


def _fmt_uptime(seconds: float) -> str:
    """Human-friendly uptime, e.g. '3d 14h 22m' or '47s'."""
    secs = int(seconds)
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins, sec = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    if not parts:  # < 1 min
        parts.append(f"{sec}s")
    return " ".join(parts[:3])


def _rel_time(iso: str | None) -> str:
    """ISO timestamp → 'just now' / '14 min ago' / '2h ago' / '3d ago'."""
    if not iso:
        return "never"
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return iso
    delta = (datetime.now(tz=timezone.utc) - then).total_seconds()
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def _queue_backend_name() -> str:
    """Which queue backend is active (mirrors get_queue() selection logic)."""
    if os.getenv("DATABASE_URL"):
        return "Postgres"
    if os.getenv("REDIS_URL"):
        return "Redis"
    return "JSONL on disk"


def _healthz_context() -> dict[str, Any]:
    """Build the health-dashboard stats from the queue. Cheap — one list_all()."""
    rows = get_queue().list_all()
    counts = _row_counts(rows)

    published = [r for r in rows if r.get("status") == "published"]
    last_dispatch = max(
        published,
        key=lambda r: r.get("updated_at", ""),
        default=None,
    )

    # A row "errored" if it carries a last_error and hasn't since succeeded.
    # The worker re-queues transient failures (status="queued" + last_error),
    # and marks exhausted ones "dead" — surface both so retries are visible.
    errored_rows = [
        r for r in rows
        if r.get("last_error") and r.get("status") != "published"
    ]
    errored_rows.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
    recent_errors = [
        {
            "platform": r.get("platform", "?"),
            "error": (r.get("last_error") or "unknown error"),
            "when": _rel_time(r.get("updated_at")),
            "status": r.get("status", "?"),
            "attempts": r.get("attempts", 0),
        }
        for r in errored_rows[:5]
    ]

    top_platforms = Counter(r.get("platform", "?") for r in rows).most_common(5)

    uptime_secs = (datetime.now(tz=timezone.utc) - _START_TIME).total_seconds()

    return {
        "active": "health",
        "version": VERSION,
        "now": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "uptime": _fmt_uptime(uptime_secs),
        "backend": _queue_backend_name(),
        "counts": counts,
        "total": len(rows),
        "configured_platforms": sorted(_platforms_configured()),
        "last_dispatch": (
            {
                "platform": last_dispatch.get("platform", "?"),
                "when": _rel_time(last_dispatch.get("updated_at")),
                "post_id": last_dispatch.get("post_id"),
            }
            if last_dispatch
            else None
        ),
        "top_platforms": top_platforms,
        "recent_errors": recent_errors,
        "failed_count": len(errored_rows),
        "platform_emoji": PLATFORM_EMOJI,
    }


# ─── JSON API + health ─────────────────────────────────────────────────────

@app.get("/healthz")
def healthz(request: Request) -> Any:
    """JSON for monitors/curl; HTML status dashboard for browsers."""
    if _wants_html(request):
        return templates.TemplateResponse(request, "health.html", _healthz_context())
    return JSONResponse({"status": "ok", "version": VERSION})


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


@app.post("/_retry-all")
async def retry_all(request: Request) -> Any:
    """Re-queue every failed/dead row. Used by the health dashboard."""
    q = get_queue()
    requeued = 0
    for row in q.list_all():
        if row.get("last_error") and row.get("status") != "published":
            q._update(row["id"], {"status": "queued", "last_error": None})  # noqa: SLF001
            requeued += 1
    if _wants_html(request):
        # Browser form submit: bounce back to the refreshed health dashboard.
        return RedirectResponse(url="/healthz", status_code=303)
    return {"requeued": requeued}


@app.delete("/queue/{row_id}")
async def delete_row(request: Request, row_id: str) -> Any:
    """Delete a single queue row permanently."""
    q = get_queue()
    row = q.get(row_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    q.delete(row_id)
    if _wants_html(request):
        return RedirectResponse(url="/", status_code=303)
    return {"deleted": row_id}


@app.post("/queue/{row_id}/delete")
async def delete_row_post(request: Request, row_id: str) -> Any:
    """HTML-form-friendly alias for DELETE /queue/{id}.

    When called via HTMX from the queue table, returns the refreshed
    queue fragment instead of a redirect.
    """
    q = get_queue()
    row = q.get(row_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    q.delete(row_id)
    # HTMX inline call from dashboard table
    if "hx-request" in {k.lower() for k in request.headers}:
        return await _render_queue_fragment(request, status=None)
    if _wants_html(request):
        return RedirectResponse(url="/", status_code=303)
    return {"deleted": row_id}


@app.post("/_purge")
async def purge_queue(request: Request, status: str = "published") -> Any:
    """Delete all rows with a given status. Default: clear published rows."""
    allowed = {"published", "dead"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"can only purge: {', '.join(sorted(allowed))}")
    q = get_queue()
    deleted = 0
    for row in q.list_all(status=status):
        q.delete(row["id"])
        deleted += 1
    if _wants_html(request):
        return RedirectResponse(url="/", status_code=303)
    return {"purged": deleted, "status": status}


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
    profiles = ProfileStore().list()
    # Build per-profile configured-platforms map for client-side JS
    import json as _json
    profiles_js = _json.dumps([
        {"id": p.id, "name": p.name, "emoji": p.emoji,
         "configured": p.configured_platforms()}
        for p in profiles
    ])
    return templates.TemplateResponse(
        request, "compose.html",
        {
            "platforms": platforms,
            "configured": configured,
            "profiles": profiles,
            "profiles_js": profiles_js,
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
    profile_id: str = Form(""),
    scheduled_for: str = Form(""),
    webhook_url: str = Form(""),
    formats_json: str = Form(""),
) -> HTMLResponse:
    errors: list[str] = []
    targets: list[str] = [p for p in platforms if p]

    if not targets:
        errors.append("pick at least one platform")
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
        "profile_id": profile_id.strip() or None,
    })
    errs = validate(unit)
    if errs:
        return templates.TemplateResponse(
            request, "_compose_result.html",
            {"ok": False, "errors": errs},
        )

    # Resolve profile label for the result panel
    profile = ProfileStore().get(profile_id.strip()) if profile_id.strip() else None
    profile_label = f"{profile.emoji} {profile.name}" if profile else ".env defaults"

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
        {"ok": True, "unit_id": unit.id, "enqueued": enqueued,
         "profile_label": profile_label},
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


# ─── Profiles ─────────────────────────────────────────────────────────────────

def _profile_ctx(version: str, now: str, active: str = "profiles") -> dict:
    return {"active": active, "version": version, "now": now,
            "platform_cred_map": PLATFORM_CRED_MAP, "cred_labels": CRED_LABELS,
            "password_fields": PASSWORD_FIELDS, "platform_emoji": PLATFORM_EMOJI,
            "preset_colors": PRESET_COLORS}


@app.get("/profiles", response_class=HTMLResponse)
async def profiles_list(request: Request) -> HTMLResponse:
    profiles = ProfileStore().list()
    ctx = _profile_ctx(VERSION, datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    return templates.TemplateResponse(request, "profiles.html",
                                      {**ctx, "profiles": profiles})


@app.get("/profiles/new", response_class=HTMLResponse)
async def profile_new(request: Request) -> HTMLResponse:
    ctx = _profile_ctx(VERSION, datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    return templates.TemplateResponse(request, "profile_form.html",
                                      {**ctx, "profile": None, "title": "New Profile"})


@app.get("/profiles/{profile_id}/edit", response_class=HTMLResponse)
async def profile_edit(request: Request, profile_id: str) -> HTMLResponse:
    profile = ProfileStore().get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="profile not found")
    ctx = _profile_ctx(VERSION, datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    return templates.TemplateResponse(request, "profile_form.html",
                                      {**ctx, "profile": profile,
                                       "title": f"Edit — {profile.name}"})


@app.post("/profiles", response_class=HTMLResponse)
async def profile_create(request: Request) -> HTMLResponse:
    form = await request.form()
    profile = _profile_from_form(form)
    ProfileStore().save(profile)
    return RedirectResponse(url="/profiles", status_code=303)


@app.post("/profiles/{profile_id}", response_class=HTMLResponse)
async def profile_update(request: Request, profile_id: str) -> HTMLResponse:
    store = ProfileStore()
    if not store.get(profile_id):
        raise HTTPException(status_code=404, detail="profile not found")
    form = await request.form()
    profile = _profile_from_form(form, profile_id=profile_id)
    store.save(profile)
    return RedirectResponse(url="/profiles", status_code=303)


@app.post("/profiles/{profile_id}/delete", response_class=HTMLResponse)
async def profile_delete(request: Request, profile_id: str) -> HTMLResponse:
    ProfileStore().delete(profile_id)
    return RedirectResponse(url="/profiles", status_code=303)


@app.get("/api/profiles")
def api_profiles_list() -> list[dict]:
    """JSON list — used by the compose page JS."""
    return [
        {"id": p.id, "name": p.name, "emoji": p.emoji,
         "color": p.color, "configured": p.configured_platforms()}
        for p in ProfileStore().list()
    ]


def _profile_from_form(form: Any, profile_id: str | None = None) -> Profile:
    """Build a Profile from a submitted HTML form."""
    pid = profile_id or str(form.get("id", "")).strip() or None
    platforms: dict[str, dict[str, str]] = {}
    for platform, fields in PLATFORM_CRED_MAP.items():
        creds: dict[str, str] = {}
        for field_name in fields:
            value = str(form.get(f"{platform}__{field_name}", "")).strip()
            creds[field_name] = value
        if any(v for v in creds.values()):
            platforms[platform] = creds
    return Profile(
        id=pid if pid else Profile().id,
        name=str(form.get("name", "")).strip() or "Unnamed",
        emoji=str(form.get("emoji", "🎭")).strip() or "🎭",
        color=str(form.get("color", "#4ade80")).strip() or "#4ade80",
        platforms=platforms,
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
