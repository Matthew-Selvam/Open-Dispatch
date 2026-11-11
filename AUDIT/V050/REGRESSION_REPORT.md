# v0.5.0 Cross-System Regression Report

Date: 2026-06-10 session. Branch: `release/v0.5.0-hardening`.
Machine: Apple Silicon Mac, macOS (Darwin), Python 3.13.14 (`/tmp/od-venv`),
PostgreSQL 16.15 (disposable instance, 127.0.0.1:5499), Redis 7 (local, AOF,
disposable DBs 9), Docker Desktop (disposable projects only).

## 1. Full test suite

| Run | Result |
|---|---|
| Baseline (v0.4.1 @ 9e24ca2, before any change) | 350 passed, 7 skipped, 1 warning, 13.49 s |
| Final (all four P1 remediations applied) | **385 passed, 5 skipped, 1 warning, 14.08 s** (with `OPEN_DISPATCH_TEST_POSTGRES_DSN` set) |
| Final without live Postgres | 383 passed, 7 skipped |

Test-count deltas, explained:
- **+21** `tests/test_queue_fail_closed.py` (new: QUEUE-2 failure injection).
- **+8** `tests/test_worker_concurrency.py` (new: PERF-2).
- **+4** `tests/test_compose_security.py` (new: SEC-1).
- **+2** `tests/test_postgres_integration.py` ran live (quarantine + transactions)
  where the disposable DSN was provided (previously counted as skips).
- **−2** skips in `tests/test_redis_queue.py`/`test_postgres_queue.py`: the two
  factory-fallback tests became fail-closed tests (they now assert
  `QueueBackendError` is raised; they were previously counted as passing).
- **5 skips remain**: `tests/test_client_auth.py` MCP tests, skipped by design
  without the `mcp` extra in this venv. The dedicated CI-1 job runs them in a
  clean env with **0 skips** (verified locally: 14 passed).
- Warnings: 1 (Starlette TestClient/httpx deprecation, pre-existing).

## 2. Live cross-system scenarios (all executed on this machine)

| # | Scenario | Method | Result |
|---|---|---|---|
| 1+6 | PostgreSQL outage during worker operation + recovery | Worker loop against live disposable PG; `pg_ctl stop -m immediate` verified down via `psql`; worker polled through the outage; PG restarted | **PASS** — 12 explicit `QueueBackendError` events logged (`connection failed mid-operation`), **no JSONL fallback** (no `queue.jsonl` created), row published after recovery, singleton recovered deterministically |
| 2 | Redis outage during job claiming | Claimed row, `redis-cli shutdown nosave` mid-claim, verified down, `mark_published` attempted | **PASS** — explicit `QueueBackendError` (wrapped redis ConnectionError); after restart a fresh row enqueued and published; no JSONL fallback |
| 3 | Worker crash while publishing | SIGKILL mid-publish (slow synthetic adapter) against live PG | **PASS** — row orphaned in `publishing`; fresh worker with short lease quarantined it: `failed` + "verify on the platform before retrying" — never auto-requeued |
| 4 | Restart after quarantining a stale job | Unit coverage (JSONL/Redis/PG) + scenario 3 lifecycle | **PASS** — quarantined rows keep `attempts` unchanged; `retry()` is the only path back to `queued` |
| 5 | Multiple workers competing for the same job | **3 concurrent worker processes** × live PG, 30 rows, synthetic adapters | **PASS** — 30/30 published exactly once, 30 unique post_ids, zero duplicates |
| 7 | Docker restart with persistent data | Disposable compose project, named volume, enqueue → `docker compose restart` → row readback | **PASS** — row persisted across container restart; project torn down with `-v` (no residue) |
| 8 | API running while the queue is unavailable | Live uvicorn with unreachable `DATABASE_URL` | **PASS** — `/healthz` → `503 {"status":"degraded","queue_error":…}`; `POST /dispatch` → `503` with the operator fix; no 202, no 500 traceback |
| 9 | MCP absent from base install | Fresh venv, `pip install .` | **PASS** — core imports OK; `mcp_server.py` exits 1 with install hint; 5 MCP tests skip by design |
| 10 | MCP-enabled install in a clean environment | Fresh venv, `pip install '.[mcp,test]'` | **PASS** — `import mcp_server` OK; all 14 client-auth tests pass, 0 skips |
| 12 | Fresh source installation | `bash install.sh --version release/v0.5.0-hardening` (branch pushed) into a temp prefix | **PASS** — install completed; server booted; `/healthz` 200; `dispatch doctor` runs |
| 13 | Fresh Docker installation | `docker compose build` from this branch + boot + healthz + enqueue (scenario 7) | **PASS** |
| 11 | macOS installation and launch regression | Bundle-launch mechanism verified on v0.4.1 (relocated DMG app served `/healthz`); no macOS-specific code changed in v0.5.0 work; RC DMG rebuild is a Phase 7 artifact | **PENDING Phase 7** (rebuild + relocate-test before release approval; not published) |
| 14 | Homebrew install/upgrade regression | Public tap intentionally remains at 0.4.1 until release approval; formula sha update is a Phase 7 artifact | **PENDING Phase 7 approval** |

## 3. v0.4.1 P0-fix integrity (must remain intact)

| P0 fix | Verification in this run |
|---|---|
| PG-1: Postgres transactions persist | `tests/test_postgres_integration.py::test_transactions_persist_and_only_one_worker_claims` — live PG: enqueue → get → list_due → competing claims (exactly one True) → mark_published; **PASS** |
| QUEUE-1: stale publishing quarantined, never auto-requeued | Live scenario 3 (SIGKILL → quarantine) + unit tests in all three backends; quarantine message requires operator verification; **PASS** |
| DIMG-1: relocated DMG app self-contained | Mechanism verified at v0.4.1; no macOS app code changed; RC rebuild in Phase 7; **PENDING RC build** |
| install.sh symlink safety | Unchanged since v0.4.1 fix; scenario 12 exercised the tar-copy path against the release-branch archive; **PASS** |
| SEC-1 (v0.5.0): compose loopback | `tests/test_compose_security.py` 4/4 + live `docker port`/`lsof` checks (Phase 2); **PASS** |

## 4. Coverage

Not measured — no coverage tooling is configured in this repo (CI-2, P2, out of
scope for the four P1 findings). The new failure-injection and concurrency
tests are the coverage evidence for the remediated surfaces.

## 5. Environment details

- Python 3.13.14 (local venv), pytest 9.2.0, pytest-timeout 2.4.0.
- FastAPI/starlette/httpx as pinned by `requirements.txt`.
- PostgreSQL 16.15, Redis 7 (AOF), Docker Desktop (compose v2).
- All live scenarios used disposable databases/containers/volumes; the user's
  existing `.env` (real credentials) was never loaded into any test process;
  no real social platform was contacted; no release artifact was published.
