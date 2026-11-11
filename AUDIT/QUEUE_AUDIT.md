# Queue and scheduling audit — Phase 5

Environment: macOS arm64, Python 3.12.13; JSONL in a fresh temporary directory; Redis 8.10.2 on an isolated local port and database 15; PostgreSQL 16.15 in the audit's isolated `/tmp/od-pgdata` cluster. No social platform calls were made. `pytest -q tests/test_queue.py tests/test_postgres_queue.py tests/test_redis_queue.py tests/test_duplicate_regressions.py`: 54 passed, 0 failed (1.24 s). Those tests use stubs for Redis/PostgreSQL; the live experiments below supplement them.

## Backend results

| Behavior | JSONL | Redis | PostgreSQL |
|---|---|---|---|
| Enqueue, list due, claim, complete, retry, cancel | Unit tested; live enqueue/claim tested | Unit tested; live enqueue/claim tested | **FAIL**: schema creation is rolled back on close; subsequent enqueue raises `UndefinedTable` |
| Two simultaneous worker claims | **PASS**: two forked processes on one row returned `[False, True]` | **PASS**: two forked processes against real Redis returned `[False, True]` | Blocked by PG-1 until repair |
| Future scheduling and timezone offsets | Unit tests cover due guard and offset comparison | Unit tests cover due guard and score conversion | SQL inspection only; real test blocked by PG-1 |
| Retry backoff / maximum attempts | Unit tests cover atomic reschedule and worker limit | Unit tests cover guarded reschedule; no real outage test in this phase | SQL inspection only; real test blocked by PG-1 |
| Restart recovery | JSONL persists on disk; compose restart verified in Phase 2 | Redis persistence depends on deployment configuration; no isolated restart test here | Blocked by PG-1 |
| Crash during publishing | **FAIL**: stale reaper can trigger duplicate publication | **FAIL**: same | Same reaper policy in SQL; currently inoperative |
| Backend outage | File I/O errors propagate | After connection, operations fail until Redis recovers (Phase 2) | **FAIL**: startup connection failure silently selects another backend |

The simultaneous claim experiments used `multiprocessing.get_context('fork')`, an event to release two workers together, and a queue to capture both return values. Both processes exited 0. For the stale-claim test, a claimed row's `updated_at` was backdated by 901 seconds; `reap_stale_publishing(900)` returned its ID and a second `mark_publishing` returned `True` on both JSONL and Redis. This models a slow live adapter and a second worker, or a crash after a platform accepted a post but before `mark_published` persisted. The first worker can still be in flight. A 900-second lease is not a correctness boundary. The application cannot guarantee exactly-once publication without platform idempotency or an explicit uncertain-outcome state.

## Findings

| ID | Priority | Evidence and impact | Recommended repair |
|---|---|---|---|
| PG-1 | P0 | `PostgresQueue._conn()` uses `closing(conn)` without `with conn` or `commit`; schema and writes roll back. Real PostgreSQL 16 raises `UndefinedTable` after constructor. All PostgreSQL deployments fail. | Wrap every operation in both a transaction context and closing context; add a real PostgreSQL integration test. |
| QUEUE-1 | P0 | JSONL and Redis reaper tests above: a stale `publishing` row becomes `queued` and is claimable again while the first publish may have succeeded. PostgreSQL uses the same policy. Duplicate public posts are possible. | Quarantine uncertain outcomes for manual platform verification; never auto-republish an expired claim. Explain manual retry risk in UI/docs. |
| QUEUE-2 | P1 | With `DATABASE_URL=postgresql://invalid-host:1/test?connect_timeout=1`, `get_queue()` logs a warning then returns `JsonlQueue`. The same silent fallback exists for Redis. During a backend outage, API and worker can use different stores, lose visibility of scheduled jobs, or later duplicate them. | Fail startup or requests when an explicitly configured backend is unavailable. Do not change storage backend implicitly. |
| QUEUE-3 | P2 | JSONL rewrites the complete queue for every state transition; file size and worker latency grow with job history. No retention/compaction policy exists. | Measure throughput, then add archival or bounded history if warranted. |
| QUEUE-4 | P2 | Redis `mark_publishing()` catches all exceptions and returns `False`, potentially treating a connection error as a lost claim. Other mutations propagate. | Catch only transaction conflicts as contention; propagate outages so health/error reporting is accurate. |

## Remaining verification

After PG-1 repair: run real PostgreSQL enqueue, claim, completion, due-time, restart, two-process contention and failure-injection checks. After QUEUE-1 repair: verify crash recovery cannot automatically retry an uncertain post across all three backends. Daylight-saving transitions should be checked through offset-aware timestamps, including ambiguous local input at the API boundary. No claim of live social-platform duplicate prevention is possible without sandbox accounts and platform idempotency support.
