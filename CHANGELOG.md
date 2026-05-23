# Changelog

All notable changes to Open-Dispatch are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
