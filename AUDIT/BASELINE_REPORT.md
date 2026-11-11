# Baseline Report — Phase 1

Environment: macOS 15 (arm64, 26.5.2), Python 3.12.13 venv, pytest 9.2.0 / pytest-asyncio 1.4.1.
Commands were executed on the clean clone at `main` @ `c8c62b7`, branch `audit/v1-forensic`.

## 1. Test suite execution (exactly as documented)

Documented command: `pytest -q` (README §Tests) with `pip install -r requirements.txt` + `pytest pytest-asyncio` (CI recipe).

| Metric | Value |
|---|---|
| Total tests collected | 355 |
| Passed | 350 |
| Failed | 0 |
| Errored | 0 |
| Skipped | 5 |
| Execution time | 12.0 s (pytest), 17.7 s wall with collection |
| Warnings | 2 (pytest-asyncio `asyncio_default_fixture_loop_scope` deprecation; Starlette/TestClient httpx deprecation) |
| Coverage | not available — no coverage tooling configured anywhere in the repo |

### The 5 skipped tests — CI-1 finding

`tests/test_client_auth.py` contains 5 tests gated on `pytest.mark.skipif(not MCP_AVAILABLE)`.
CI (`ci.yml`) installs **only** `pytest pytest-asyncio` — never `mcp` — so the 5 MCP bearer-token
auth tests are skipped on every CI run. They only pass if a developer happens to `pip install mcp`
locally. Locally, after installing the `mcp` extra: **355 passed, 0 skipped, 12.2 s**.
This is an untested-in-CI security-relevant surface (MCP client auth propagation).

### Test-quality inspection

- `FakeRedis` (tests/test_redis_queue.py) and a SQL-generation stub (tests/test_postgres_queue.py)
  validate **generated commands**, not real engines. Redis/Postgres backends have **zero integration
  coverage** against real services. The docstring acknowledges this ("Integration tests with a real
  Postgres are a separate suite (CI-only)") — but no such suite exists anywhere in the repo.
- Mocking level is high for external HTTP (appropriate — no network in tests) but adapters' request
  *payloads* are validated against real documented API shapes only by inspection, not tests.
- No race-condition tests across *processes* (JSONL flock logic is exercised in-process only).
- No failure-injection tests for Redis/Postgres outages (documented requirement of queue audit).
- `tests/test_docs_integrity.py` dynamically skips referrer/doc checks when files "not present"
  (silent skip-on-rename risk: renaming a doc file would silently stop checking it).

## 2. Static checks

| Check | Command | Result |
|---|---|---|
| Syntax/compile | `python -m compileall adapters api scheduler ai media web cli.py profiles.py mcp_server.py` | PASS (all files compile) |
| Core imports | `import api.app, api.queue, api.schema, adapters, scheduler.worker, cli, profiles, ai.caption_adapter, media` | PASS |
| MCP imports | `import mcp_server` (with `mcp` installed) | PASS |
| Dependency consistency | `pip check` | PASS ("No broken requirements found") |
| Lint | `ruff check .` (no config in repo) | 158 findings — 0 errors (`E9xx`/undefined-name), all style-level: 41×UP017, 32×I001, 15×F401, 10×RUF059, 9×UP037, 8×BLE001, etc. 116 auto-fixable |
| Formatting | `ruff format --check .` | 49 of 64 files would be reformatted (no formatter config/CI step exists) |
| Type check | no mypy/pyright config; CI has no type job | not run (n/a) |
| Wheel build | `python -m build --wheel` | PASS — `open_dispatch-0.4.0-py3-none-any.whl`, required files (profiles.py, mcp_server.py, web templates/static) verified in wheel |

## 3. Clean-environment application start

Procedure: fresh venv-free directory, `OPEN_DISPATCH_DATA=/tmp/od-clean-data`, no `.env`, no prior data.

| Verification | Result |
|---|---|
| `uvicorn api.app:app` boots, no errors in log | PASS |
| `GET /healthz` → 200 `{"status":"ok","version":"0.4.0","backend":"JSONL on disk",…}` | PASS |
| Dashboard `GET /` → 200 HTML | PASS |
| `GET /media/specs` → 10 specs JSON | PASS |
| Harmless op: `POST /dispatch` (discord target, queue-only — worker not running) → 202 with unit_id + row id | PASS |
| Failure condition: malformed JSON `POST /dispatch` → 400 | PASS |
| Worker status correctly reports `not running` (no heartbeat file) | PASS |

Data dir auto-created on first enqueue; no crash, no permission issue.

## 4. Baseline gaps and observations

1. **CI-1 (P1):** 5 MCP auth tests silently skipped in CI (deps incomplete). Fix: add `mcp` to CI install or move the tests to an opt-in marker; document skip.
2. **CI-2 (P2):** no lint, no type check, no coverage, no Redis/Postgres integration job — README's "318 tests" is also stale (355 now).
3. **CI-3 (P2):** No release CI: no PyPI publish, no Docker image publish, no DMG build automation — the macOS DMG and `brew` tarball depend on manual tag creation.
4. **DOC-1 (P2):** README says `pytest -q  # 318 tests` → actual 355.
5. **DOC-2 (P2):** README embeds `docs/demo.gif` which does not exist in the repo (broken image).
6. `WORKER_POLL_INTERVAL` is documented/read at import time in worker but `.env.example` documents it — consistent.
7. Queue backend priority is DATABASE_URL > REDIS_URL > JSONL — matches docs.

## 5. Verdict at baseline

The suite is green and the app boots from a clean environment with correct API behavior on the
happy path and on malformed input. The suite is *not* green-equivalent across environments
(MCP tests skipped by default deps), has zero real-service integration coverage for Redis/Postgres,
and has no lint/type/coverage gates. Baseline is healthy but the "tests passing ⇒ works" assumption
fails for the queue backends and install methods — carried into Phases 2 and 5.
