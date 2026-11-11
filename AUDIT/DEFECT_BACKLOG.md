# Defect backlog — Phase 11

Priorities reflect release impact. Evidence and reproduction details are in the linked phase reports. Status is updated as repairs land; unlisted minor observations remain in those reports.

| ID | Priority | Root cause / impact | Repair | Status |
|---|---|---|---|---|
| PG-1 | P0 | PostgreSQL connection closes without commit; schema and all writes roll back. Backend unusable. | Transaction context plus real-service regression test. | Fixed — verified on a live disposable PostgreSQL 16 instance (`tests/test_postgres_integration.py`) |
| QUEUE-1 | P0 | Stale `publishing` claims auto-requeue; a slow or crashed worker can duplicate an accepted post. | Quarantine uncertain outcomes and require explicit verification before retry. | Fixed — reapers in all three backends quarantine into `failed` with a verify-before-retrying error; covered by unit + live-Postgres tests |
| INST-1 | P0 | v0.4.0 tag contains 0.1.0-era package; install.sh/Homebrew fetch stale, pre-hardening code. | Correct artifact/version routing without rewriting an existing tag; validate fresh installs. | Fixed — released v0.4.1 (tag, DMG asset, Homebrew tap matthew-selvam/homebrew-open-dispatch); fresh curl\|bash + brew installs verified serving 0.4.1 |
| DIMG-1 | P0 | DMG bundled wrapper embeds relative build-time paths and cannot start server after relocation. | Absolutize installer paths and rebuild/relocate/test DMG. | Fixed — install.sh --bundle emits relocatable wrappers; bundle ships a Python runtime; relocated DMG app verified serving /healthz 0.4.1. Also fixed: release-tree symlinks made cp -r pull the whole /Applications into installs |
| QUEUE-2 | P1 | Configured PostgreSQL/Redis outages silently select JSONL, splitting queue data. | Fail closed on explicit backend configuration. | Fixed — QueueBackendError with actionable fix; API 503s; healthz distinguishes API vs queue; worker retries deterministically; 21 failure-injection tests + live PG/Redis outage scenarios |
| SEC-1 | P1 | Default Compose port binds all host interfaces with bearer auth off. | Loopback default plus prominent remote-access instructions. | Fixed — 127.0.0.1:8000:8000 default; docker-compose.prod.yml publishes nothing; README pre-launch warning + remote-exposure section; host-level verification + 4 regression tests |
| PERF-2 | P1 | One blocking adapter stalls entire worker. | Bounded concurrency or isolate long-running adapter work. | Fixed — WORKER_CONCURRENCY (default 1); claims atomic inside tasks; slow adapter blocks only its slot; benchmarked on 3 live backends with zero duplicate claims; 8 regression tests |
| CI-1 | P1 | Five MCP auth tests skip in CI because `mcp` extra is absent. | Install extra in CI and require zero skips for security tests. | Fixed — dedicated clean-env CI job installs '.[mcp,test]' and fails on any skip; base job asserts core imports work without mcp + wheel metadata; verified 14/14 with 0 skips locally |
| API-1 | P2 | Unknown platform targets accepted at enqueue then fail in worker. | Validate membership in registered adapters. | Open |
| SEC-2 | P2 | API buffers entire uploads before limits. | Stream with size bounds and test. | Open |
| UI-1/UI-2 | P2 | Mobile horizontal overflow and unlabeled composer controls. | Responsive navigation and programmatic labels. | Open |
| AI-1 | P2 | Malformed LLM JSON value raises uncaught AttributeError. | Validate model schema and fall back. | Open |
| N8N-1 | P2 | Credential test uses open health probe; invalid token passes. | Probe protected route. | Open |
| DOC-1/DOC-2 | P2 | Test count and demo image claims stale. | Correct README. | Open |
| ADPT-1/ADPT-2 | P2 | Manual token expiry guidance missing; Threads wait blocks worker. | Document rotation; address worker blocking. | Open |

All four P0 defects are fixed and verified; **v0.4.1 has been released** (tag, DMG, Homebrew tap). All four P1 defects are now fixed and verified on `release/v0.5.0-hardening` (385 tests pass; live failure-injection scenarios documented in AUDIT/V050/). **v0.5.0 has been released** (tag, GitHub release + DMG, Homebrew tap) on 2026-11-11 after CI passed on the merge PR; post-release verification in AUDIT/V050/POST_RELEASE_VERIFICATION.md. Remaining open: P2s (QUEUE-3 compaction, QUEUE-4 residual Redis semantics, SEC-2 streaming limits, CI-2/CI-3, DOC items, ADPT items). Platform live publishing is still blocked by external credentials/approvals and must be labeled as such.
