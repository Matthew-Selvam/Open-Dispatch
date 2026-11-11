# v0.5.0 Executive Summary

Branch: `release/v0.5.0-hardening` (pushed). Scope: resolve all four P1
findings from the v0.4.1 forensic audit, independently verify, and prepare a
release candidate. **Nothing has been published** — the tag, DMG upload, and
Homebrew tap update await explicit approval.

## 1. P1 findings resolved

| ID | Status | One-line evidence |
|---|---|---|
| QUEUE-2 (fail-closed backends) | **RESOLVED** | `QueueBackendError` raised for unreachable/misconfigured backends; API 503s; `/healthz` API-vs-queue; worker retries deterministically; live PG and Redis outage scenarios passed with zero fallback |
| SEC-1 (compose exposure) | **RESOLVED** | loopback-only default verified at host level (`docker port`, `lsof`, `netstat`); production compose publishes zero ports; 4 CI regression tests |
| PERF-2 (worker concurrency) | **RESOLVED** | `WORKER_CONCURRENCY` bounded pool; slow adapter blocks only its slot (deterministic overlap test); zero duplicate claims across 12 benchmark points on 3 live backends; graceful shutdown |
| CI-1 (MCP dependency/coverage) | **RESOLVED** | clean-env CI job runs the 5 MCP auth tests with zero skips (verified locally 14/14); base-install assertions + wheel metadata gate |

## 2. Partially resolved
- None at P1 level. (QUEUE-4 — Redis error-swallowing, P2 — was incidentally
  resolved by the QUEUE-2 work for transport failures; contention semantics
  deliberately retained.)

## 3. Remaining open (all P2 or below, pre-existing)
- SEC-2: request bodies buffered before size limits (proxy mitigation documented).
- QUEUE-3: JSONL file growth, no compaction.
- API rate limiting: none.
- CI-2/CI-3: lint/type-check/coverage and release automation.
- DOC/ADPT P2 items from the original audit.
- Platform live publishing: blocked by external credentials/approvals (unchanged).

## 4. Tests executed and actual results
- Full suite: **385 passed, 5 skipped** (with live disposable PostgreSQL;
  the 5 skips are MCP tests without the extra in the local venv — they pass
  with zero skips in the clean-env MCP verification). Without the DSN:
  383 passed, 7 skipped. Runtime ~14 s. One pre-existing warning.
- New tests this release: 33 (+21 fail-closed, +8 concurrency, +4 compose
  security), plus 2 previously-skipped PG integration tests now running live.
- Baseline at session start: 350 passed, 7 skipped. Every count change is
  accounted for in `REGRESSION_REPORT.md` §1.

## 5. Security findings
- SEC-1 (High) closed with host-level verification; no new vulnerabilities
  introduced (no auth code weakened, no secrets logged — Redis/PG connection
  errors are wrapped without echoing credentials; the log redaction from
  v0.4.1 is unchanged and re-covered by existing tests).
- A build-chain defect (stale DMG staging contamination) was found and fixed;
  it had no security impact but silently shipped old code.

## 6. Performance measurements
- Local synthetic benchmark (2 ms fake adapters, 200 rows/point, live
  JSONL/PostgreSQL 16/Redis 7): zero duplicate claims and zero errors at
  concurrency 1/2/4/8 on all three backends; throughput scales to ~4 then
  plateaus (JSONL flock contention, PG per-op handshake, GIL). Full table in
  `AUDIT/V050/benchmark_results.md`. **These are local synthetic numbers and
  are not predictive of real platform-API throughput.**

## 7. Installation verification
curl|bash (release branch) · fresh Docker build + restart persistence ·
compose loopback/redis-exposure checks · relocated RC DMG serving 0.5.0 ·
pip base and `[mcp,test]` clean-venv installs · wheel metadata. Homebrew tap
intentionally remains at 0.4.1 until approval; the v0.5.0 formula sha is a
post-approval step (documented in the runbook).

## 8. Compatibility risks
- Compose users who intentionally exposed the API must now set a token and
  change the mapping (documented; the only behaviour change to defaults).
- `WORKER_CONCURRENCY` defaults to `1` — identical to v0.4.1 behaviour.
- No queue data-format changes; v0.4.1 data is read as-is and rollback of code
  is safe with data in place (the new `.corrupt` sidecar is ignored by old
  readers).
- The 5 MCP tests skip in local base venvs by design; CI now enforces zero
  skips for that file.

## 9. Known limitations
As listed in `RELEASE_READINESS.md` §7 (unauthenticated-by-default API with
loopback mitigation, SEC-2, no rate limiting, JSONL growth, Redis durability
without AOF, intra-batch ordering, synthetic-only benchmark scope).

## 10. Release-candidate approval
**v0.5.0 is ready for release-candidate approval.** Acceptance criteria:
all four P1s resolved with evidence ✓; no unresolved P0s ✓; PG persistence and
crash-recovery safety re-verified live ✓; backends fail safely ✓; compose
defaults defensible and verified ✓; concurrency tested/documented ✓; base and
MCP installs verified ✓; full regression green ✓; docs match reality ✓; no
unresolved critical/high security issue ✓; no release artefacts published ✓.
The single open verification item is observing CI on the merge PR (the
workflow triggers on push/PR to `main`), which by design can only happen at
release time.
