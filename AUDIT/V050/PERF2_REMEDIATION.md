# PERF-2 Remediation — Worker Concurrency and Throughput

Status: **RESOLVED** — branch `release/v0.5.0-hardening`.
Original finding: PERFORMANCE_AUDIT.md #24 — "One slow adapter stalls the single
worker; a 30–120 s Threads settle wait can miss scheduling targets for unrelated
platforms. Isolate blocking work or use bounded concurrency after preserving queue
claims."

## Original defect, reproduced

`run_once()` (scheduler/worker.py) iterated due rows **serially in one thread**.
A synthetic reproduction (tests/test_worker_concurrency.py) confirmed it: with two
due rows, one slow (0.4 s adapter) and one fast (0.01 s), the fast row's publish
started only *after* the slow row finished. A real 30–120 s Threads settle wait
would therefore delay every unrelated platform's scheduled post by up to that
wait — exactly the missed-scheduling-targets symptom in the audit.

## Changes

### `scheduler/worker.py`

1. **`WORKER_CONCURRENCY` env var** (default `1` — the old serial behaviour, fully
   backwards compatible). Parsed by `_parse_concurrency()`:
   - invalid / non-integer / `< 1` → falls back to `1` **with a loud warning naming
     the bad value** (a typo must not crash-restart the worker, but must never
     silently run at a different concurrency than the operator believes).
   - no upper bound is enforced in code; the documentation states the resource
     implication (each slot multiplies platform-API load; JSONL saturates ≈ 4 on
     the benchmark host).
2. **Per-row processing extracted to `_process_row(q, row)`** — claim
   (`mark_publishing`) happens *inside* the task, so at most `WORKER_CONCURRENCY`
   rows are ever claimed at once. The pool bounds outstanding claims; it never
   bypasses them. This preserves the v0.4.1 atomicity invariants (JSONL flock,
   Redis WATCH, Postgres guarded UPDATE) unchanged.
3. **Bounded `ThreadPoolExecutor`** (thread-name prefix `od-publish`) when
   concurrency > 1; futures' exceptions are propagated to the loop. `list_due()`
   order (oldest-first) is preserved for submission; within a batch, completion
   order is not guaranteed — inherent to concurrency, documented.
4. **Graceful shutdown**: the `with ThreadPoolExecutor(...)` block waits for
   in-flight publishes on any exit path (including KeyboardInterrupt from
   `main()`), so no row is orphaned mid-publish; claims are released by
   `mark_published`/`mark_failed` inside `_process_row`. If a worker is killed
   hard mid-publish, the existing v0.4.1 reaper quarantines the row — unchanged.
5. Worker startup log now includes the effective concurrency.

### Rate limits and timeouts

- Platform rate limits: adapters already classify rate-limit responses as
  retryable with exponential backoff (v0.4.1 behaviour, unchanged). Bounded
  concurrency *reduces* burst pressure per platform; `.env.example` documents
  keeping `WORKER_CONCURRENCY` at or below what platform rate limits allow.
- Timeouts: adapter HTTP timeouts are the adapters' own (unchanged); the pool
  adds no new timeout surface — a hung adapter occupies its slot, other slots
  continue (this is the fix).

## Benchmark (synthetic, this machine)

Script: `scripts/benchmark_worker.py` — synthetic adapter (2 ms sleep), 200 rows
per point, every point counted only from the rows it enqueued (persistent
backends keep earlier points' rows; the script fails loudly if any row is lost).
Backends against **live services**: JSONL (disk), PostgreSQL 16 (disposable
instance on 127.0.0.1:5499), Redis 7 (local). Machine: Apple Silicon Mac,
Python 3.13. Full table: `AUDIT/V050/benchmark_results.md`.

| backend | concurrency | jobs/min | p50 ms | p95 ms | duplicates/errored | cpu s | maxrss MB |
|---|---|---|---|---|---|---|---|
| jsonl | 1 | 12,296 | 2.51 | 2.52 | 0 | 0.47 | ~35,400* |
| jsonl | 2 | 25,448 | 2.51 | 2.52 | 0 | 0.39 | ~35,900* |
| jsonl | 4 | 30,458 | 2.52 | 2.55 | 0 | 0.39 | ~36,000* |
| jsonl | 8 | 26,107 | 2.52 | 2.66 | 0 | 0.44 | ~36,200* |
| postgres | 1 | 7,746 | 2.51 | 2.53 | 0 | 0.19 | ~49,700* |
| postgres | 2 | 14,876 | 2.51 | 2.62 | 0 | 0.17 | ~53,600* |
| postgres | 4 | 31,545 | 2.50 | 2.52 | 0 | 0.15 | ~53,600* |
| postgres | 8 | 39,785 | 2.51 | 2.63 | 0 | 0.26 | ~53,600* |
| redis | 1 | 10,435 | 2.51 | 2.54 | 0 | 0.19 | ~45,200* |
| redis | 2 | 19,333 | 2.51 | 2.63 | 0 | 0.13 | ~46,100* |
| redis | 4 | 29,931 | 2.32 | 2.55 | 0 | 0.11 | ~46,600* |
| redis | 8 | 32,792 | 2.22 | 2.52 | 0 | 0.14 | ~47,800* |

\* `maxrss_mb` in the table is `ru_maxrss` in KB on macOS (whole process, not per
worker) — treat as a same-run relative signal, not an absolute footprint.

### Honest reading of the numbers

- **Zero duplicate claims and zero errors at every concurrency level on all three
  backends** — the safety property, which is the point of this finding.
- Throughput scales with concurrency up to ~4, then flattens (JSONL: flock
  contention; Postgres: per-operation connection handshake dominates; Redis: GIL +
  client serialization). These are **local synthetic numbers with a 2 ms fake
  adapter**; real platform publishes are 100–10,000× slower per job, so real
  deployments will be network-bound long before any backend saturates.
- This benchmark does **not** predict production throughput against real platform
  APIs and must not be quoted as such.

## Regression tests (tests/test_worker_concurrency.py, 8 tests)

1. `_parse_concurrency` defaults and invalid-value → 1 **with warning**.
2. Slow adapter does not block other platforms (overlap proven deterministically:
   fast row's publish starts before slow row's publish ends).
3. Concurrency never duplicates publishes (12 rows, concurrency 4, each published
   exactly once).
4. Outstanding claims bounded by `WORKER_CONCURRENCY` (measured max in-publish ≤ 2).
5. `WORKER_CONCURRENCY=1` behaves exactly like the old serial loop.
6. Adapter exception under concurrency is still recorded (no row stranded in
   `publishing` — v0.4.1 invariant).
7. Graceful shutdown: in-flight publish finishes and commits state.
8. (Plus the full-suite run below.)

## Requirements mapping

1. Configurable concurrency — `WORKER_CONCURRENCY`; **met**.
2. Conservative default — `1` (identical to v0.4.1 behaviour); **met**.
3. Explicit bounds documented — `.env.example` + this document; **met**.
4. Atomic job claiming — claims happen inside `_process_row` via the unchanged
   backend primitives; **met** (tests 3, 4).
5. No simultaneous claims of the same row — backend atomicity unchanged; **met**.
6. No duplicate publishing from concurrency — zero duplicates in all benchmark
   points and in the regression tests; **met**.
7. Rate-limit handling — adapters' retryable classification unchanged; concurrency
   documented as the burst-pressure knob; **met**.
8. Timeout handling — hung adapter blocks only its slot; **met** (test 2).
9. Graceful shutdown — executor join; in-flight publishes commit; **met** (test 7).
10. Observable worker health — heartbeat unchanged; `run_once` logs batch size and
    effective concurrency; `/healthz` unchanged (QUEUE-2 work added queue status);
    **met**.
