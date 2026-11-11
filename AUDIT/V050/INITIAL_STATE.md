# v0.5.0 Remediation — Initial State

Date: 2026-06-10 (session start). Branch: `release/v0.5.0-hardening`.

## Starting commit

- `main` @ `9e24ca2` ("docs(homebrew): tap the dedicated formula repo")
- `git describe --tags`: `v0.4.1-2-g9e24ca2` — i.e. two docs commits after the retagged v0.4.1.
- Working tree: `dist/build/Open-Dispatch.app/*` and `macos-app/OpenDispatch/.build/*` are
  modified build artifacts (tracked in the repo, rebuilt during the v0.4.1 DMG build). These are
  **preserved untouched** and excluded from the hardening branch's commits. `graphify-out/` and
  `macos-app/OpenDispatch/.build/.lock` are untracked.

## Current test results (baseline)

- Command: `python -m pytest` (venv at `/tmp/od-venv`, Python 3.13.14, no `mcp` extra installed).
- Result: **350 passed, 7 skipped, 1 warning in 13.49s**.
- Skips:
  - 5 × `tests/test_client_auth.py` — `mcp extra not installed` (finding CI-1)
  - 2 × `tests/test_postgres_integration.py` — requires `OPEN_DISPATCH_TEST_POSTGRES_DSN`
    (skipped by design without a live disposable PostgreSQL; the DSN is documented in `.env.example`)
- No coverage tooling configured.

## Original P1 findings (from AUDIT/*)

| ID | Source | Original finding | Original remediation plan |
|---|---|---|---|
| QUEUE-2 | QUEUE_AUDIT.md #25 | With `DATABASE_URL=postgresql://invalid-host:1/test?connect_timeout=1`, `get_queue()` logs a warning then returns `JsonlQueue`. Same silent fallback for Redis. During an outage, API and worker can use different stores, lose visibility of scheduled jobs, or later duplicate them. | Fail startup or requests when an explicitly configured backend is unavailable. Do not change storage backend implicitly. |
| SEC-1 | SECURITY_AUDIT.md #7 | `api/app.py` `_authorized()` returns `True` when `OPEN_DISPATCH_API_TOKEN` is empty; `.env.example` leaves it empty; `docker-compose.yml` publishes `8000:8000` (binds all host interfaces). Verified: `GET /profiles` → 200 and `POST /dispatch` → 202 without auth on an isolated test host. | Bind default Compose port to loopback (`127.0.0.1:8000:8000`); require explicit token or authenticated reverse proxy for remote access; document before first launch. |
| PERF-2 | PERFORMANCE_AUDIT.md #24 | One slow adapter stalls the single worker; a 30–120 s Threads settle wait can miss scheduling targets for unrelated platforms. | Isolate blocking work or use bounded concurrency after preserving queue claims. |
| CI-1 | BASELINE_REPORT.md #21, REPOSITORY_INVENTORY.md #119 | `ci.yml` installs only `pytest pytest-asyncio`; the 5 MCP bearer-token auth tests in `tests/test_client_auth.py` are skipped on every CI run. They pass only if a developer happens to `pip install mcp`. | Install `mcp` extra in CI (or move tests to an opt-in marker and document); the security-relevant surface must be exercised in CI. |

## Reproduction status at baseline

- **QUEUE-2**: reproduced by code inspection — `get_queue()` (api/queue.py:846-893) catches
  `ImportError` and connection errors and falls through to `JsonlQueue()`. Each queue backend
  needs live failure-injection tests (see Phase 1).
- **SEC-1**: confirmed by code inspection — `docker-compose.yml` has `ports: - "8000:8000"` and no
  auth token requirement; the audit ran a live test on an isolated host. Reproduction will be via
  `ss`/`lsof` host-level port checks in Phase 2.
- **PERF-2**: `run_once()` (scheduler/worker.py:154-230) iterates `due` rows **serially** in a
  single thread; a slow adapter (e.g. Threads settle wait) blocks the whole loop. Reproduction
  with synthetic adapters is planned in Phase 3.
- **CI-1**: `ci.yml` "Install dependencies" step installs only `requirements.txt` + `pytest
  pytest-asyncio`; `mcp` never installed. The 5 skips are observed in the baseline run above.

## Architectural constraints

- Queue backends: `JsonlQueue` (default, JSONL + flock), `RedisQueue` (WATCH-based optimistic
  transactions), `PostgresQueue` (single table, guarded UPDATE claims). Selection order
  DATABASE_URL → REDIS_URL → JSONL, cached in a module singleton (`_QUEUE_SINGLETON`).
- Worker: single-threaded polling loop (`scheduler/worker.py`), heartbeat file, quarantine reaper
  (v0.4.1 fix), `PUBLISHING_LEASE` 900 s, `MAX_ATTEMPTS` 3, exponential backoff.
- API: FastAPI, bearer auth via `OPEN_DISPATCH_API_TOKEN` (empty = unauthenticated).
- CI: 4 jobs (python matrix 3.11/3.12, n8n-node, landing, docker smoke).
- Docker: multi-stage Dockerfile (python:3.12-slim), compose api + worker + optional redis profile.
- install.sh: tar-based copy, relocatable bundle mode (`--bundle`), DMG build via make-dmg.sh.
- Homebrew: formula in main repo + public tap repo `Matthew-Selvam/homebrew-open-dispatch`.

## Known risks

- **Do not duplicate-publish**: all concurrency work must preserve the v0.4.1 quarantine semantics
  (stale `publishing` → `failed`, never auto-requeue).
- Docker Compose: no `depends_on` for redis; changing binding defaults must not break the
  documented quick-start; CI smoke test uses `-p 8000:8000` on all interfaces.
- Worker concurrency: `mark_publishing` is atomic per backend (JSONL flock, Redis WATCH, PG
  guarded UPDATE) — concurrency must be added on top of these claims, not bypass them.
- The v0.4.1 release DMG is already published; the v0.5.0 artifacts must not be published without
  explicit approval (Phase 7).
- 5 MCP tests skip in CI — CI-1 must make CI install the `mcp` extra in a clean environment and
  verify zero security-relevant skips.
- Backwards compatibility: `get_queue()` fallback is currently relied upon by the default JSONL
  path (no env vars set). Fail-closed must apply only when a backend is *explicitly configured*.
