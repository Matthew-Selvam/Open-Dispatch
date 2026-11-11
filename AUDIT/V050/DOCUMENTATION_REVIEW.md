# v0.5.0 Documentation Review

Scope: every operator-facing document that the four P1 remediations touch.
Review performed against the **actual implementation** on
`release/v0.5.0-hardening`; every claim below was verified against code or a
live run in this session.

## Documents reviewed and their state

| Document | Claim checked | State |
|---|---|---|
| `README.md` — Queue section | fail-closed behaviour, `/healthz` 200 vs 503, no silent store switch | **Updated + verified** (matches `api/queue.py` `get_queue`, `QueueBackendError`, `api/app.py` handler) |
| `README.md` — new "Operations" section | queue-down behaviour, quarantined-job recovery steps, worker concurrency | **Added + verified** (recovery steps match `retry()` semantics; `WORKER_CONCURRENCY` matches `_parse_concurrency`) |
| `README.md` — Docker quick-start | loopback binding warning before first launch | **Updated + verified** (matches `docker-compose.yml` `127.0.0.1:8000:8000`; live `docker port`/`lsof` check) |
| `README.md` — "Exposing the API remotely" | token + TLS reverse proxy required; host-level verification commands | **Added** (commands are real: `ss -tlnp`, `lsof -nP -iTCP:8000 -sTCP:LISTEN`) |
| `.env.example` | `WORKER_CONCURRENCY` documented with rate-limit guidance | **Added + verified** (`tests/test_docs_integrity.py` requires every code-read env var here — passes) |
| `docker-compose.prod.yml` | self-documenting header: no published ports, token required, Redis password guidance | **Added + verified** (resolved config: 0 published ports) |
| `CHANGELOG.md` | v0.5.0 entry describes the four P1 fixes; v0.4.1 section dated; stale "re-queues" wording corrected to "quarantines" | **Updated** |
| `INSTALL_METHODS.md` | no changes required — install paths untouched by the P1 work | **Verified unchanged** |
| `SECURITY.md` | points to SECURITY_AUDIT; SEC-1 remediation now closes the audit's release blocker | **Verified** (content still accurate) |
| MCP install docs (README + `mcp_server.py` docstring) | `pip install 'open-dispatch[mcp]'` is the documented path and the error hint matches | **Verified** (`mcp_server.py` exit-1 hint verified in a clean env) |

## Claims deliberately NOT made

- No production-scale performance claims: the benchmark is local + synthetic
  (2 ms fake adapters) and is labelled as such everywhere it appears.
- No claim that the macOS DMG or Homebrew tap has been updated for v0.5.0 —
  both are explicitly pending release approval (Phase 7).
- No claim that rate limiting exists (it does not — documented as a known
  limitation with reverse-proxy mitigation).
- No claim that SEC-2 (buffered request bodies) is fixed — it is a separate
  P2 finding, untouched.

## Docs-integrity tests

`tests/test_docs_integrity.py` (11 tests) enforces: every env var read by code
appears in `.env.example`, credential env vars appear in the credentials
guide, and relative doc links resolve. **11/11 pass** after these changes.
