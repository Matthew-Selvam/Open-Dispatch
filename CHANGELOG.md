# Changelog

All notable changes to Open-Dispatch are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **CLI and MCP server authenticate against a secured instance** — both now read
  `OPEN_DISPATCH_API_TOKEN` and send it as a bearer header, so they no longer 401 when the
  server requires auth. The CLI also takes `--token`. A 401/403 from either client now names the
  variable instead of surfacing a bare HTTP error. The n8n node already supported this via its
  **API Key Header** credential field.
- **MCP server works with mcp 2.x** — `FastMCP` was renamed `MCPServer` in the 2.0 SDK and the
  previous import raised `SystemExit` on any current install, breaking the server outright. The
  import now accepts either major version.
- **Optional API access control** — set `OPEN_DISPATCH_API_TOKEN` to require an
  `Authorization` header carrying a bearer token on every route except `/healthz`,
  plus an `Origin` check on state-changing requests. Unset by default; see the
  README before exposing the port.
- **Campaign status and cancellation** — `GET /campaign/{unit_id}` reports every platform row;
  `POST /campaign/{unit_id}/cancel` cancels queued rows without touching in-flight or completed rows.
  The CLI exposes `dispatch campaign <unit_id> [--cancel]`, and MCP exposes matching tools.
- **Health dashboard** at `/healthz` — visual server + queue status (content-negotiated:
  HTML for browsers, JSON for monitors/curl). Pulsing liveness dot, queue stat grid,
  top-platforms bar chart, recent-failures table with one-click "Retry all".
- **Worker heartbeat** — the scheduler writes a timestamp every poll loop; the Health
  dashboard reports `running / stale / not running` with the last-beat time.
- **Live character counter** in the composer — shows the most restrictive limit across the
  selected platforms (Twitter 280, Bluesky 300, Threads 500, LinkedIn 3000, Instagram 2200)
  with green/warn/over colour coding.
- **Native datetime picker** for scheduling — replaces the raw ISO-8601 text field; converts
  to ISO-8601 with timezone offset on submit.
- **Per-row delete** and **bulk purge** (clear published / clear dead) in the dashboard.

### Fixed
- **Stored profile credentials can now be deleted.** The edit form renders credential inputs
  empty (secrets are never sent to the browser) and only applied non-empty submissions, so a
  stale token could never be removed through the UI — the only way to drop it was editing
  `profiles.json` by hand. Added a per-field **remove stored value** checkbox.
- **Profile form now covers all 10 platforms** — tiktok, facebook and discord were missing from
  the credential form despite having adapters, so their credentials could not be set via the UI.
- **Retry backoff is now atomic with the status flip.** The worker used to call
  `mark_failed()` (status -> `queued`) and then patch `scheduled_for` in a second write. In
  that window the row was `queued` but still carried its original past `scheduled_for`, so a
  second worker's `list_due()` saw it as immediately due and claimed it — the exponential
  backoff was silently skipped, and the first worker's reschedule then landed on a row already
  in `publishing`. `mark_failed()` now takes `retry_at` and applies status, attempts and
  reschedule in one status-guarded write on all three backends.
- **`mark_publishing()` now requires the row to actually be due**, not just `queued`. A worker
  holding a row id from an earlier poll could otherwise claim a row that another worker had
  since backed off to a future time. Guarded with `_row_due()` on JSONL/Redis and
  `scheduled_for <= now()` in the Postgres UPDATE.
- `POST /dispatch/bulk` returns 400 instead of 500 when a client sends a non-numeric
  `Content-Length` header.
- `transcode_image`'s docstring now matches behavior: output is confined to the media root
  rather than written next to the source file.
- Removed an inert `is_symlink()` check in `media/paths.py` that could never fire after
  `.resolve()` dereferenced the link; containment is enforced by the `relative_to(root)` check.
- `/_retry-all` now uses the guarded `retry()` method instead of reaching into the private
  `_update()` helper, so it honors the same status preconditions as the single-row endpoint.
- Queue due-time comparison now parses timezone-aware timestamps as instants instead of comparing
  ISO-8601 strings lexically; malformed schedule values are logged and treated as due.
- Campaign cancellation is respected by retry endpoints and bulk retry, so canceled rows cannot be revived.
- Version string now derives from installed package metadata instead of a stale hard-coded
  constant.
- Corrected GitHub repository URLs (casing) across templates, docs, and the n8n node.

## [0.4.0] — 2026-05-19

### Added
- **Postgres queue backend** — ACID with `SELECT … FOR UPDATE SKIP LOCKED` for safe
  cross-region multi-worker operation. Swap in with a single `DATABASE_URL` env var.
- **Media transcoding** — per-platform image resize via Pillow, 10 platform specs, exposed
  over REST (`/media/transcode`, `/media/specs`) and a Python API. Honors EXIF, never upscales.
- **Profiles** — named sets of per-platform credentials so you can dispatch as different
  accounts without editing `.env`.
- **Five install methods** — Homebrew tap, universal `install.sh` (launchd + systemd),
  Docker Compose, pip, and a SwiftUI macOS menubar app + DMG.
- **GitHub Actions CI** — runs the full test suite, builds the n8n node, and smoke-tests the
  Docker image on every push.
- `CONTRIBUTING.md`, `SECURITY.md`, and a multi-stage non-root `Dockerfile`.
- Public landing page.

## [0.3.0] — 2026-05-12

### Added
- **YouTube Shorts adapter** — Data API v3 resumable upload with OAuth2 refresh-token flow.
- **Redis queue backend** — multi-worker-safe queue via a single `REDIS_URL` env var.
- **Adapter test coverage** — schema, queue, API, and adapter tests; no network, no real
  credentials required.

## [0.2.0] — 2026-05-05

### Added
- **Web UI v1** — dark terminal-aesthetic dashboard and composer (HTMX + Jinja, no build step):
  queue list, status filters, live auto-refresh, retry, and row detail.
- **Threads adapter.**
- **AI caption adaptation** — one source text rewritten per platform, with an
  Ollama → OpenRouter → heuristic provider fallback that never 500s on missing credentials.
- **n8n community node** — Dispatch / Adapt / Get Row / Retry / List Queue.

## [0.1.0] — 2026-04-28

### Added
- **`POST /dispatch`** — the core enqueue endpoint and the one-function adapter contract.
- Adapters for **Twitter/X, Telegram, Bluesky, Instagram, LinkedIn.**
- **JSONL queue** with a state machine (`queued → publishing → published | failed | dead`),
  exponential-backoff retries, and publish/failure webhooks.
- **Docker Compose** self-host and the first README.

[Unreleased]: https://github.com/Matthew-Selvam/Open-Dispatch/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Matthew-Selvam/Open-Dispatch/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Matthew-Selvam/Open-Dispatch/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Matthew-Selvam/Open-Dispatch/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Matthew-Selvam/Open-Dispatch/releases/tag/v0.1.0
