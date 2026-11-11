# v0.5.0 Release Notes (draft — publish only on approval)

**Open Dispatch v0.5.0** — hardening release. All four P1 findings from the v0.4.1
forensic audit are resolved and independently verified on real services.

## Queue correctness
- **Fail-closed backends (QUEUE-2).** With `DATABASE_URL` or `REDIS_URL` set but that
  backend down (or its driver missing), Open Dispatch raises an explicit error with the
  operator fix instead of silently falling back to JSONL — a fallback that split the queue
  across two unreconcilable stores. API: `503` + `Retry-After`, never a bare 500.
  `/healthz` now reports a running API (`200`) separately from a functioning queue
  (`503 degraded`). Worker: logs the outage and retries each poll; recovery is
  deterministic. Redis mid-operation connection failures surface in the same actionable
  error; JSONL torn-write lines are preserved to `queue.jsonl.corrupt` instead of being
  silently dropped.
- **Crash-safe publishing preserved (QUEUE-1, v0.4.1).** Re-verified live: a worker
  SIGKILLed mid-publish leaves the row quarantined for operator verification; retry always
  requires explicit verification. Three competing workers published 30/30 rows exactly once.

## Security
- **Compose binds loopback by default (SEC-1).** `127.0.0.1:8000:8000` instead of
  all-interfaces on an unauthenticated API. New production compose publishes zero host
  ports (reverse proxy joins the network). README documents token + TLS reverse proxy
  requirements *before* first launch, with host-level verification commands.

## Performance
- **Bounded worker concurrency (PERF-2).** `WORKER_CONCURRENCY` (default `1` = previous
  serial behaviour) publishes up to N due rows in parallel; claims stay atomic, so rows are
  never double-published, and one slow adapter (e.g. the Threads settle wait) no longer
  delays unrelated platforms. Benchmarked on synthetic workloads against live
  JSONL/PostgreSQL/Redis: zero duplicate claims at every level; results in
  `AUDIT/V050/benchmark_results.md`. Local synthetic numbers — not production-API predictions.

## Build & CI
- **MCP extra exercised in CI (CI-1).** A clean-environment CI job installs `.[mcp,test]`
  and runs the 5 MCP bearer-token auth tests with **zero skips allowed** — previously
  skipped on every CI run. Base job asserts core imports work without `mcp` and that
  `mcp_server.py` fails with the actionable install hint.
- **DMG staging fix.** `make-dmg.sh` now clears the staging dir; previously a stale app
  from the previous build could silently ship (found and fixed during RC verification).

## Upgrade notes
- From v0.4.1: no data migration. `docker-compose.yml` users who exposed the API
  intentionally must now set `OPEN_DISPATCH_API_TOKEN` and change the port mapping — see
  README → "Exposing the API remotely".
- `WORKER_CONCURRENCY` defaults to `1` (identical behaviour); opt in per platform rate
  limits.
- Homebrew users: the tap updates to 0.5.0 at release time (`brew upgrade open-dispatch`).

**Install:** `curl -fsSL https://raw.githubusercontent.com/Matthew-Selvam/Open-Dispatch/main/install.sh | bash`
· DMG attached below · `brew tap matthew-selvam/open-dispatch && brew install open-dispatch`
