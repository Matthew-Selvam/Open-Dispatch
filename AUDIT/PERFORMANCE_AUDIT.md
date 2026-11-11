# Performance and reliability audit — Phase 7

Measurements are local, isolated, and **not production capacity claims**. Host: macOS 26.5.2 arm64, Python 3.12.13; fresh temporary JSONL data directories; 100–10,000 small synthetic rows; one process; no adapter network calls. Timing used `time.perf_counter()` and includes filesystem work. No user queue or social account was touched.

| Workload | Result |
|---|---:|
| Enqueue 100 small rows | 0.0074 s |
| Enqueue next 400 rows | 0.0274 s |
| Enqueue next 500 rows | 0.0338 s |
| List 1,000 due rows | 0.0019 s |
| Claim one row in a 1,000-row queue | 0.0051 s |
| Enqueue 10,000 small rows in a fresh queue | 0.736 s |
| List 10,000 due rows | 0.019 s |
| Claim one row in a 10,000-row queue | 0.057 s |
| 10,000-row JSONL file size / observed process peak RSS | 3.18 MB / 50.5 MB |

The 10,000-row claim rewrites the full file (`JsonlQueue._write_all`); every complete/fail/retry does likewise. Claim latency scaled roughly with row count in this small experiment. The worker processes due rows serially and calls adapters synchronously. Threads media publishing sleeps up to 120 seconds, so one post can delay every other due row in the same worker. PostgreSQL opens a new connection per operation with no pool; latency and connection load remain unmeasured because PG-1 blocks live operations. Redis uses a single client with no bulk due-row read and scans all IDs for stale claims; long history increases poll cost.

## Reliability findings

| ID | Priority | Observation |
|---|---|---|
| PERF-1 | P2 | JSONL is O(queue size) for each state change and has no history retention. Suitable for small self-hosted queues; needs explicit scale limit or archival guidance. |
| PERF-2 | P1 | One slow adapter stalls the single worker; a 30–120 s Threads settle wait can miss scheduling targets for unrelated platforms. Isolate blocking work or use bounded concurrency after preserving queue claims. |
| PERF-3 | P2 | PostgreSQL creates a fresh TCP connection per queue operation; no pooling or statement timeout is configured. Measure after PG-1 repair, then add pooling/timeouts if needed. |
| PERF-4 | P2 | Request bodies are fully buffered before size checks (SEC-2), making concurrent large uploads a memory pressure path. |

## Not yet measured

No sustained worker soak, large video upload, slow external API, network-disconnect, retry-storm or database failover benchmark was run. Those need controlled fixtures and the queue repairs first. The Phase 3 API probe completed 30 concurrent dispatches with all 30 persisted; it did not measure latency distribution or sustained throughput. Resource measurements above are local snapshots, not leak tests.
