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
- **`CREDENTIALS_GUIDE.html` now exists.** The README and the landing page both pointed at it as
  the answer to "where do I get API keys", but the file was never committed — a 404 on the main
  conversion path, with no equivalent elsewhere in the repo. Built it for all 10 platforms,
  organised by where each credential is acquired rather than by variable name, with troubleshooting
  and a security-notes section.
- **Documented `OPEN_DISPATCH_MEDIA_DIR` in `.env.example`.** It is what enables media path
  confinement (`media/paths.py` skips the `relative_to(root)` check when it is unset), so an
  operator had no way to discover the one variable that turns a security control on.
- **A typo in `THREADS_SETTLE_SECONDS` silently lost the post.** `int("abc")` raised out of
  `publish()`, and because `list_due()` only returns `queued` rows with no reaper for stuck claims,
  the row stayed in `publishing` forever with `attempts=0` and no recorded error. The value is now
  parsed defensively and clamped to 120s, so an unbounded value cannot stall the single-threaded
  worker either. Reproduced before the fix: row stuck in `publishing`, invisible to `list_due()`.
- **Over-length content is now rejected instead of silently truncated.** `text[:280]` on Twitter and
  `[:300]` on Bluesky posted a broken mid-sentence fragment with no warning; `media_paths[:4]`,
  `images[:4]` and `carousel[:10]` silently dropped the extras and published the post with the wrong
  images. All now return a `permanent` error naming the limit. Length checks run before any SDK
  client is constructed, so a bad request never spins up client objects.
- **Threads catches `httpx.InvalidURL`, which is not an `httpx.HTTPError` subclass**, so a malformed
  user id escaped the adapter's handlers and stranded the row the same way.
- **Adapters no longer report success when a post did not publish.** Verified reproductions of the
  pre-fix behavior:
  - Telegram reports failure as HTTP 200 with `"ok": false`; the adapter never checked it, so a
    chat-not-found returned success with an empty post id. The row was marked published, no failure
    webhook fired, and the message was lost with no retry.
  - Instagram returned `ok=True` when `media_publish` answered 200 with no `id`.
  - LinkedIn posts with `lifecycleState: PUBLISHED`, so a 2xx means the post is live. A missing
    `x-restli-id` header made the adapter call `.json()` on an empty 201 body, fail, and return
    `ok=False` — so the worker retried and re-published the same post up to 3 times.
  - TikTok returned `(True, publish_id, "")` when polling never reached a terminal state,
    marking a video that never published as published. Its `publicaly_available_post_id` was also
    indexed with `[0]`, so a bare-string response yielded the first *character* of the real post id.
- **Bot tokens and access tokens no longer reach error strings or logs.** Telegram puts the token in
  the URL path and Instagram put it in the query string; httpx logs every request at INFO with the
  full URL, which the worker enables. Added `adapters/errors.py` with `redact()`/`clip()` and silenced
  the httpx/httpcore/tweepy/atproto loggers in the worker.
- **Retry classification.** Adapters now tag failures as `retryable`, `auth`, `permanent`, or
  `published`. The worker dead-letters `auth` and `permanent` immediately instead of burning three
  attempts and two backoffs on a bad token, and a `published` failure is never retried.
- **An adapter that raises no longer strands its row.** The row stayed in `publishing` forever —
  `list_due()` only returns `queued` rows and nothing reaped stuck claims — so the post was silently
  lost. `run_once()` now converts any adapter exception into a recorded failure.
- **YouTube upload is bounded and host-pinned.** The `Location` header from the resumable-session
  response was PUT with the whole video and no timeout; it is now restricted to `*.googleapis.com`
  over HTTPS, given a bounded timeout, and streamed instead of read into memory. An invalid
  `privacy` value now fails instead of silently publishing publicly.
- **Error bodies are no longer truncated below what the queue stores** — adapters cut at 200-400
  while the queue keeps 500, losing the actionable tail of Meta and Google errors.
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
