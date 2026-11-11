# Defect backlog — Phase 11

Priorities reflect release impact. Evidence and reproduction details are in the linked phase reports. Status is updated as repairs land; unlisted minor observations remain in those reports.

| ID | Priority | Root cause / impact | Repair | Status |
|---|---|---|---|---|
| PG-1 | P0 | PostgreSQL connection closes without commit; schema and all writes roll back. Backend unusable. | Transaction context plus real-service regression test. | Fixed — verified on a live disposable PostgreSQL 16 instance (`tests/test_postgres_integration.py`) |
| QUEUE-1 | P0 | Stale `publishing` claims auto-requeue; a slow or crashed worker can duplicate an accepted post. | Quarantine uncertain outcomes and require explicit verification before retry. | Fixed — reapers in all three backends quarantine into `failed` with a verify-before-retrying error; covered by unit + live-Postgres tests |
| INST-1 | P0 | v0.4.0 tag contains 0.1.0-era package; install.sh/Homebrew fetch stale, pre-hardening code. | Correct artifact/version routing without rewriting an existing tag; validate fresh installs. | Open |
| DIMG-1 | P0 | DMG bundled wrapper embeds relative build-time paths and cannot start server after relocation. | Absolutize installer paths and rebuild/relocate/test DMG. | Open |
| QUEUE-2 | P1 | Configured PostgreSQL/Redis outages silently select JSONL, splitting queue data. | Fail closed on explicit backend configuration. | Open |
| SEC-1 | P1 | Default Compose port binds all host interfaces with bearer auth off. | Loopback default plus prominent remote-access instructions. | Open |
| PERF-2 | P1 | One blocking adapter stalls entire worker. | Bounded concurrency or isolate long-running adapter work. | Open |
| CI-1 | P1 | Five MCP auth tests skip in CI because `mcp` extra is absent. | Install extra in CI and require zero skips for security tests. | Open |
| API-1 | P2 | Unknown platform targets accepted at enqueue then fail in worker. | Validate membership in registered adapters. | Open |
| SEC-2 | P2 | API buffers entire uploads before limits. | Stream with size bounds and test. | Open |
| UI-1/UI-2 | P2 | Mobile horizontal overflow and unlabeled composer controls. | Responsive navigation and programmatic labels. | Open |
| AI-1 | P2 | Malformed LLM JSON value raises uncaught AttributeError. | Validate model schema and fall back. | Open |
| N8N-1 | P2 | Credential test uses open health probe; invalid token passes. | Probe protected route. | Open |
| DOC-1/DOC-2 | P2 | Test count and demo image claims stale. | Correct README. | Open |
| ADPT-1/ADPT-2 | P2 | Manual token expiry guidance missing; Threads wait blocks worker. | Document rotation; address worker blocking. | Open |

Release remains **NO-GO** until P0 and core P1 issues are resolved and all installation artifacts are rebuilt and verified. Platform live publishing is still blocked by external credentials/approvals and must be labeled as such.
