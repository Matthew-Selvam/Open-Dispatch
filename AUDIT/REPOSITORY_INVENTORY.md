# Repository Inventory — Open Dispatch (v0.4.0 pre-release baseline)

Audit branch: `audit/v1-forensic` (cloned from `main` @ `c8c62b7`).
Audit date: 2025-11-10 (local). All paths relative to repo root.

## 1. Component map

| Component | Path(s) | Language | Entry points | Notes |
|---|---|---|---|---|
| FastAPI app + web dashboard | `api/app.py` (1037 LOC), `api/schema.py`, `web/templates/*`, `web/static/*` | Python | `uvicorn api.app:app`, `open-dispatch` entry point, `python cli.py` (argparse `server()`) | JSON API + HTMX UI on one port |
| Queue layer | `api/queue.py` (879 LOC) | Python | imported | JSONL (default), Redis, Postgres backends; `QueueProtocol` |
| Scheduler worker | `scheduler/worker.py` (246 LOC) | Python | `python -m scheduler.worker`, `open-dispatch-worker`, `dispatch worker` | poll loop, heartbeat file, retry/backoff, webhook egress policy |
| Platform adapters (10) | `adapters/{twitter,bluesky,telegram,instagram,linkedin,threads,youtube,tiktok,facebook,discord}.py`, `adapters/errors.py` | Python | registry dict `ADAPTERS` | contract: `publish(unit, account) -> (ok, post_id, error)` |
| CLI | `cli.py` (362 LOC) | Python | `dispatch` entry point (`pyproject [project.scripts]`) | subcommands: send/queue/campaign/worker/quick-test/doctor |
| AI caption adapter | `ai/caption_adapter.py` (419 LOC) | Python | `POST /ai/adapt` | OpenRouter, Ollama, heuristic fallback |
| Media transcoding | `media/transcode.py` (240 LOC), `media/paths.py` (60 LOC) | Python | `POST /media/transcode`, `GET /media/specs` | Pillow-only; 10 image specs |
| MCP server | `mcp_server.py` (316 LOC) | Python | `python mcp_server.py [--transport sse]` | wraps REST API; mcp 1.x/2.x compat |
| Profiles store | `profiles.py` (266 LOC) | Python | imported | plaintext JSON credential store `$OPEN_DISPATCH_DATA/profiles.json` |
| Docker | `Dockerfile` (2-stage), `docker-compose.yml` (api + worker + optional redis profile), `.dockerignore`, `requirements-docker.txt` | — | `docker compose up -d` | non-root `dispatch` user, healthcheck |
| install.sh | `install.sh` (executable) | bash | `curl … \| bash` | macOS/Linux; launchd + systemd user units; venv in `$PREFIX/opt/open-dispatch` |
| Homebrew formula | `Formula/open-dispatch.rb` | Ruby | `brew tap matthew-selvam/open-dispatch <repo>` | pinned v0.4.0 tarball + sha256; `brew services` support |
| macOS menubar app | `macos-app/OpenDispatch/` (SwiftPM: 5 Swift sources + Info.plist), `scripts/make-dmg.sh` | Swift | `OpenDispatch.app` | bundles Python server; arm64 native |
| n8n community node | `n8n-node/` (TypeScript: node, credential, index) | TS | `npm link n8n-nodes-open-dispatch` | 5 operations documented in README |
| Landing page | `landing/` (Next.js) | TS/TSX | Vercel deploy | separate deploy from this repo |
| Docs | `README.md`, `INSTALL_METHODS.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `CREDENTIALS_GUIDE.html`, `docs/{DEMO_SCRIPT,HANDOFF,migrating-from-zernio}.md` | md/html | — | README references `docs/demo.gif` (missing) |
| Examples | `examples/twitter_bluesky.json` | json | — | single example only |
| Tests | `tests/` (23 files, ~5100 LOC, 355 tests) | Python | `pytest` | no network; stub-based Redis/Postgres backends |

## 2. External dependencies (Python)

Declared in `pyproject.toml` (== `requirements.txt` base):
`fastapi>=0.115`, `uvicorn[standard]>=0.32`, `httpx>=0.27`, `python-dotenv>=1.0`,
`tweepy>=4.14`, `atproto>=0.0.50`, `jinja2>=3.1`, `python-multipart>=0.0.20`, `Pillow>=10`.

Extras: `redis>=5.0`, `psycopg2-binary>=2.9`, `mcp>=1.0`, test: `pytest>=8`, `pytest-asyncio>=0.23`.

`requirements-docker.txt` mirrors redis+postgres extras (commented as "keep in sync").

**No lockfiles exist** for the Python side (no `requirements.lock`, no pip-tools/poetry/uv lock).
Resolution drift is possible between installs; latest-at-install resolution was used during this audit.

JS deps: `landing/package-lock.json` exists (locked), `n8n-node/package.json` has **no lockfile**.
macOS app: SwiftPM (`Package.swift`) — no lock file.

## 3. Environment variables (from `.env.example` + code scan)

| Var | Purpose | Read by |
|---|---|---|
| `OPEN_DISPATCH_DATA` | data dir (queue, profiles, media root, heartbeat) | api.app, queue, worker, profiles, cli doctor |
| `OPEN_DISPATCH_MEDIA_DIR` | confine media reads/writes | media/paths (import time) |
| `OPEN_DISPATCH_API_TOKEN` | bearer auth for all routes except JSON `/healthz` | api.app (import time), clients |
| `REDIS_URL` / `DATABASE_URL` | queue backend selection (priority DB > Redis > JSONL) | api/queue.get_queue |
| `WORKER_POLL_INTERVAL` / `WORKER_MAX_ATTEMPTS` / `WORKER_BACKOFF_BASE` / `WORKER_PUBLISHING_LEASE` | worker tuning (import time) | scheduler/worker |
| `THREADS_SETTLE_SECONDS` | Threads publish settle delay | adapters/threads |
| `TIKTOK_PRIVACY_LEVEL` / `TIKTOK_ACCESS_TOKEN` | TikTok defaults | adapters/tiktok |
| Platform creds (10 platforms) | see `profiles.REQUIRED_ENV_VARS` | adapters |
| `OPENROUTER_API_KEY/MODEL/BASE_URL/REFERER`, `OLLAMA_HOST/MODEL`, `AI_CAPTION_TEMPERATURE`, `AI_CAPTION_TIMEOUT_SECONDS` | AI caption adapter | ai/caption_adapter |
| `HOST` / `PORT` | server bind | cli.server, wrappers |
| `OPEN_DISPATCH_URL` | API base for MCP/n8n/CLI clients | mcp_server, n8n node |

Not documented in `.env.example` but read by code: none found beyond the above (verified by scan).

## 4. API surface (registered routes, `api/app.py`)

| Method | Path | Handler |
|---|---|---|
| GET | `/healthz` | `healthz` (JSON or HTML content-negotiated) |
| POST | `/dispatch` | `dispatch` (202) |
| GET | `/queue` | `list_queue` |
| GET | `/queue/` | redirect to `/` (307, schema-hidden) |
| GET | `/queue/{row_id}` | `row_detail` (HTML or JSON) |
| GET | `/queue/{row_id}/json` | `get_row_json` |
| POST | `/queue/{row_id}/retry` | `retry_row` |
| DELETE | `/queue/{row_id}` | `delete_row` |
| POST | `/queue/{row_id}/delete` | `delete_row_post` (HTML alias) |
| POST | `/_purge` | `purge_queue` |
| POST | `/_retry-all` | `retry_all` |
| GET | `/campaign/{unit_id}` | `campaign_status` |
| POST | `/campaign/{unit_id}/cancel` | `cancel_campaign` |
| GET | `/` | dashboard |
| GET | `/_queue-fragment` | `queue_fragment` |
| GET | `/compose` | compose page |
| POST | `/_compose` | compose submit |
| POST | `/_compose-adapt` | HTMX AI adapt |
| POST | `/ai/adapt` | AI adapt (JSON) |
| GET/POST | `/profiles`, `/profiles/new`, `/profiles/{id}/edit`, `/profiles/{id}`, `/profiles/{id}/delete` | profile CRUD |
| GET | `/api/profiles` | profiles JSON |
| GET | `/media/specs` | image specs |
| POST | `/media/transcode` | image transcode |
| POST | `/dispatch/bulk` | CSV bulk import |
| `/docs` | FastAPI OpenAPI UI | — |

Note: README's API reference table omits `/dispatch/bulk` (documented only in roadmap/checklist),
`/_retry-all`, `/_queue-fragment`, `/_compose*`, `/profiles*`, `/api/profiles` — some are internal UI
endpoints, but `/dispatch/bulk` is a public feature claim.

## 5. Installation methods inventory

| # | Method | Advertised in | Implemented artifacts |
|---|---|---|---|
| 1 | Docker Compose | README, INSTALL_METHODS | Dockerfile, docker-compose.yml |
| 2 | Homebrew | README, INSTALL_METHODS | Formula/open-dispatch.rb (in-repo tap) |
| 3 | install.sh | README, INSTALL_METHODS | install.sh |
| 4 | macOS DMG app | README, INSTALL_METHODS | macos-app/, scripts/make-dmg.sh |
| 5 | pip (from GitHub) | README, INSTALL_METHODS | pyproject.toml |
| 6 | Source install | implicit | any checkout |
| 7 | Redis backend deploy | README/.env.example | compose redis profile |
| 8 | Postgres backend deploy | .env.example, README roadmap | psycopg2 extra |
| 9 | PyPI | README: "publish pending" | **not published** |
| 10 | n8n community node | README | n8n-node/ |
| 11 | MCP server | README | mcp_server.py |
| 12 | CLI | README | `dispatch` entry point |

## 6. CI/CD (`.github/workflows/ci.yml`)

Four jobs: `python` (matrix 3.11/3.12: build wheel + pytest), `n8n-node` (tsc build + dist checks),
`landing` (npm ci/audit/build), `docker` (buildx + healthz smoke test).
CI installs only `pytest pytest-asyncio` → the 5 MCP-dependent tests in `tests/test_client_auth.py`
are silently skipped on every CI run (MCP not installed in CI). **Finding CI-1.**
No lint/type-check job; no coverage tooling; no release/publish workflow (no GitHub Releases automation,
no Docker image publishing, no PyPI publishing).

## 7. Database / queue implementations

- `JsonlQueue` — default; in-process RLock + cross-process `flock` on a sidecar `.lock` file; whole-file rewrite on update.
- `RedisQueue` — sets/zsets; WATCH-based optimistic transactions; `FakeRedis`-stub tests only.
- `PostgresQueue` — single table `open_dispatch_queue`, `SKIP LOCKED` not actually used (claims; uses plain UPDATE guards); SQL-generation stub tests only, no real-Postgres integration test.

## 8. Background workers

Single polling worker (`scheduler/worker.py`): heartbeat file, stale-publishing reaper
(`WORKER_PUBLISHING_LEASE`), error classification (`retryable|auth|permanent|published`),
webhook fire with SSRF egress policy + SNI pinning. No worker pool, no per-platform parallelism (by design).

## 9. Third-party integrations

OpenRouter (AI), Ollama (AI), Meta Graph v21 (Instagram), v19 (Facebook), Threads Graph v1.0,
Telegram Bot API, Twitter API v2 via tweepy + v1.1 media upload, LinkedIn ugcPosts v2,
YouTube Data API v3 resumable upload, TikTok Content Posting API v2 PULL_FROM_URL,
Discord webhooks, Bluesky ATProto, n8n, MCP clients, xquik.com (opt-in third-party Twitter backend).

## 10. Identified testing requirements (per component)

| Component | Test types needed | Currently present |
|---|---|---|
| JSONL queue | unit + concurrent-process integration | unit only (concurrency covered in-process) |
| Redis queue | integration w/ real Redis | stub-based (`FakeRedis`) only |
| Postgres queue | integration w/ real Postgres | SQL-stub only |
| Adapters (10) | unit w/ mocked HTTP; live sandbox E2E | unit w/ mocks/stubs; no live tests |
| API | contract/validation/auth | extensive TestClient suite |
| Worker | crash/restart recovery, race conditions | unit + regression tests in-process |
| Install methods | clean-env verification each | **none automated** |
| Security | auth, SSRF, XSS, path traversal | `test_hardening.py`, `test_client_auth.py` (partial) |
| Docs | link + claim integrity | `test_docs_integrity.py` (partial) |
