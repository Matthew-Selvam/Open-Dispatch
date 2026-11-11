# QUEUE-2 Remediation — Queue Backends Fail Closed

Status: **RESOLVED** (core) — commit `b399951` on `release/v0.5.0-hardening`.
Related: QUEUE-4 (P2, Redis error swallowing) partially addressed by the same change.

## Original finding (QUEUE_AUDIT.md #25)

With `DATABASE_URL=postgresql://invalid-host:1/test?connect_timeout=1`, `get_queue()`
logged a warning and returned `JsonlQueue`. The same silent fallback existed for Redis.
During a backend outage the API and worker could use different stores, lose visibility
of scheduled jobs, or later duplicate them.

## Why silent fallback is unsafe

- A fallback splits the queue across two stores. Jobs enqueued while the configured
  backend is down land in JSONL; jobs already in the backend stay there. Reconciliation
  is impossible without manual migration, and the operator has no signal this happened.
- An in-memory/other-store fallback can answer `202 Accepted` for an enqueue that the
  *configured* durable store never saw — a false success.
- During a Redis outage the old `mark_publishing`/`_conditional_update` swallowed
  connection errors and returned `False` ("claim lost"), masking the outage entirely:
  the operator saw a queue that never moved with no error anywhere.

## Changes

### `api/queue.py`

1. New `QueueBackendError(RuntimeError)` with backend name + actionable detail
   (missing driver with install hint, or connect failure with the underlying error).
2. `get_queue()` **fails closed**:
   - `DATABASE_URL` set + psycopg2 missing → raise (was: warn + Redis/JSONL).
   - `DATABASE_URL` set + connect/schema failure → raise (was: warn + Redis/JSONL).
   - `REDIS_URL` set + redis missing → raise (was: warn + JSONL).
   - `REDIS_URL` set + ping failure → raise (was: warn + JSONL).
   - JSONL remains the default **only** when neither backend is configured — the
     documented zero-infra path is unchanged (backwards compatible).
   - The singleton is cached only after successful construction, so a backend that
     comes back is picked up on the next `get_queue()` call — deterministic recovery.
   - `WatchError` (redis-py) is imported lazily with a sentinel fallback so the
     optional `redis` extra is not a hard import dependency.
3. `RedisQueue.mark_publishing` / `_conditional_update`: connection/timeout/auth errors
   now **propagate**; only `WatchError` (concurrent-write contention) returns `False`.
   Rationale: a swallowed outage in `mark_published` makes the worker believe the
   published-ack write never happened while the platform accepted the post — the row
   then sits in `publishing` until the reaper quarantines it, and nothing told the
   operator the backend was down.
4. `JsonlQueue._read_all`: corrupt (torn-write) lines are preserved verbatim in
   `queue.jsonl.corrupt` before being skipped — a crash mid-append no longer silently
   destroys a job. Unreadable files (permissions) raise; a read that returned `[]` on
   error would look like an empty queue and invite re-enqueueing duplicates.

### `api/app.py`

5. Global `QueueBackendError` exception handler → `503` + `Retry-After: 10` + the
   operator fix in the body. No bare 500 traceback for a known, diagnosable condition.
6. `/healthz` distinguishes a running API from a functioning queue:
   - queue OK → `200 {"status": "ok", ...}`.
   - queue down → `503 {"status": "degraded", "queue_error": "<fix>", ...}`.
   - HTML dashboard renders a "Queue backend down" banner with the error detail
     (no traceback page, no false "online" claim).

### `scheduler/worker.py`

7. `main()` catches `QueueBackendError` explicitly: logs a clear, actionable error and
   retries on the next poll. Rationale:
   - No silent store switch (that splits the queue — the exact QUEUE-2 defect).
   - No crash-restart loop (would lose heartbeat/state tracking continuity).
   - Recovery is deterministic: once the backend is reachable the next poll resumes;
     any row that was mid-publish when the outage hit is quarantined by the
     v0.4.1 reaper for operator verification (QUEUE-1 fix intact).

## Failure-injection coverage (tests/test_queue_fail_closed.py, 21 tests)

| Scenario | Backends | Assertion |
|---|---|---|
| Driver missing (`psycopg2`/`redis` hidden) | PG, Redis | `QueueBackendError` raised, no JSONL fallback |
| Server unreachable | PG, Redis | `QueueBackendError` with underlying error type |
| JSONL when nothing configured | JSONL | unchanged default (backwards compat) |
| Outage → recovery | PG | next `get_queue()` succeeds; singleton cached only on success |
| Mid-operation outage | PG (enqueue, list_all), Redis (enqueue, mark_publishing, mark_published) | raises; no false success |
| Constructor with dead backend | PG | raises immediately |
| WATCH contention | Redis | `False` (benign), outage raises |
| Corrupt JSONL line | JSONL | skipped + preserved verbatim in `.corrupt` sidecar |
| Write failure (disk full/read-only) | JSONL | raises on enqueue |
| Unreadable queue file | JSONL | raises on read (never reads as empty) |
| Worker during outage | worker loop | raises from `run_once`; loop survives, retries, singleton stays `None` |
| API during outage | healthz, dispatch | 503 + `queue_error`; dispatch never returns 202 |

## Backend-specific guarantees and limitations

| Backend | Guarantee | Limitation (documented for operators) |
|---|---|---|
| JSONL | Mutations are flock-atomic across processes; corrupt lines never destroyed (sidecar); write failures raise | Single-host only; no compaction (QUEUE-3, P2, open); sidecar recovery is manual |
| Redis | WATCH transactions make claims atomic; outages raise and are visible in worker logs and API 503s | Requires the `redis` extra; transient Redis restarts surface as errors until `ping` succeeds again |
| Postgres | ACID transactions; guarded-UPDATE claims; outages raise | Requires the `postgres` extra; connection storm during recovery depends on server `max_connections` |

## Acceptance criteria mapping

1. No silent backend switching — `get_queue()` raises; worker retries; **met**.
2. No in-memory fallback — none existed; none added; **met**.
3. No successful enqueue when persistence failed — enqueue raises → API 503; **met**.
4. No false publishing state — outages propagate; row stays `publishing` → reaper
   quarantines (never auto-requeues); **met**.
5. No lost jobs — JSONL corrupt-line sidecar; outages never delete state; **met**.
6. No duplicates from retry/recovery — quarantine semantics unchanged and tested; **met**.
7. Clear actionable errors — `QueueBackendError` messages name the backend and the fix; **met**.
8. Graceful shutdown when backend unusable — worker logs and retries (no corrupt
   half-writes); API returns 503; **met** (documented choice: retry-in-place rather than exit).
9. Health checks distinguish API vs queue — `/healthz` 200 vs 503 degraded; **met**.
10. Deterministic recovery — singleton cached on success only; reaper quarantine on
    mid-publish outage; **met**.
