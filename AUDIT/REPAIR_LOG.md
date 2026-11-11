# Repair Log — v0.5.0 Hardening

Chronological record of every change on `release/v0.5.0-hardening`, with the
verification evidence for each. Branch forked from `main` @ `9e24ca2`
(v0.4.1 + 2 docs commits).

| Commit | Finding | Change | Verification |
|---|---|---|---|
| `b399951` | QUEUE-2 | Fail-closed `get_queue()` (`QueueBackendError`); API 503 handler + `/healthz` API-vs-queue distinction + dashboard banner; Redis connection errors propagate (WatchError stays benign); JSONL corrupt-line sidecar + unreadable-file raise; worker logs outage and retries | 21 new failure-injection tests; suite 371 passed; factory-fallback tests rewritten to assert the new contract |
| `0dd71c5` | SEC-1 | Compose API → `127.0.0.1:8000:8000`; new `docker-compose.prod.yml` (zero published ports); README pre-launch warning + "Exposing the API remotely" | Disposable-container verification: `docker compose config`, `docker port`, `lsof`, `netstat`; 4 new compose-security regression tests; suite 375 passed |
| `ba4bc30` | PERF-2 | `WORKER_CONCURRENCY` (default 1) + bounded ThreadPoolExecutor in `run_once()`; claim inside task; graceful shutdown; `_parse_concurrency` loud fallback | 8 new concurrency tests (overlap proof, zero dupes, claim bound, serial compat, exception recording, shutdown); `scripts/benchmark_worker.py`; live JSONL/PG/Redis benchmarks, zero duplicate claims; suite 383 passed |
| `6e7d03e` | CI-1 | New CI `mcp` job (clean env, zero skips gate); base job asserts no-mcp imports + `mcp_server` exit-1 hint + wheel `Provides-Extra: mcp` | Clean-venv verification: base 9+5 skips by design; `[mcp,test]` 14/14 with 0 skips; wheel metadata checked |
| `ddb6b63` | docs (Phase 6) | README Operations section; CHANGELOG v0.5.0 entry + v0.4.1 date + stale reaper wording fixed; `.env.example` concurrency docs | docs-integrity tests 11/11; suite 383 passed |
| `c7769c8` | release prep | Version 0.5.0 across pyproject/app/install.sh/make-dmg/README/INSTALL_METHODS; `make-dmg.sh --source-ref` | Version grep sweep clean; docs-integrity pass |
| `25d9280` | DMG staging defect (found during RC verification) | `make-dmg.sh` clears `dist/staging` before assembly — previously `cp -r` merged fresh code into the previous build's app (RC DMG silently shipped a 0.4.1 server) | Rebuilt RC DMG; relocated app now serves `0.5.0` (was `0.4.1` before the fix) |

## Post-commit hardening found during Phase 5/7 (same commits as above)

- Redis mid-operation failures wrapped in `QueueBackendError` via
  `_fail_closed_redis` (transport-class failures only), matching the Postgres
  contract — discovered by the live Redis-outage scenario, not by unit tests.
- Postgres `_conn()` wraps connection acquisition failures so mid-operation
  outages are actionable (previously raw driver errors → API 500 traceback).
- `get_queue()` no longer double-wraps constructor-raised `QueueBackendError`.

## Live scenarios executed (details in REGRESSION_REPORT.md)

PG outage+recovery (12 explicit outage events, no fallback) · Redis outage
mid-claim → explicit error → functional recovery · SIGKILL mid-publish →
quarantine (never auto-requeue) · 3 competing workers → 30/30 exactly once ·
Docker restart persistence · API-with-dead-queue → live 503s · fresh source
install · fresh Docker install · MCP base/MCP-extra clean-env installs ·
relocated RC DMG serving 0.5.0.

## Environment hygiene

All live scenarios used disposable DBs/containers/volumes; the user's real
`.env` was never loaded into any test process; a temporary copy of `.env`
created by mistake was deleted immediately; pre-existing containers were
returned to their pre-session state; nothing published to any platform; no
release artifact published.
