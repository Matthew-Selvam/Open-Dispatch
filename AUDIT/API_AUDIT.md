# API Audit — Phase 3

Live probing of `api.app` (v0.4.0 @ main) with `OPEN_DISPATCH_API_TOKEN` set, plus the
355-test suite as baseline. Every result below was executed against a running server.

## Route-by-route results

| Route | Method | Happy path | Validation | Errors | Notes |
|---|---|---|---|---|---|
| `/healthz` | GET | 200 JSON / 200 HTML | n/a | — | JSON stays open when token set (by design, for monitors). **SEC-LOW:** leaks `configured_platforms`, version, backend, worker liveness, queue counts to unauthenticated probers |
| `/dispatch` | POST | 202 + `{unit_id, enqueued[]}` | 400 empty/bad targets, 413 >100 KB, 400 bad webhook_url, 400 path traversal in `*_path` | 400 malformed JSON, 401/403 auth/origin | **API-1 (P2): unknown platform names accepted** — `{"targets":["nonsense"],…}` → 202 + row id; fails later in worker as "no adapter", burning 3 retries + backoff + webhook. `/ai/adapt` rejects unknown platforms; `/dispatch` does not |
| `/dispatch/bulk` | POST | 202 `{imported, errors, …}` | 413 >1 MiB/1000 rows, per-row errors reported | — | Same API-1: bogus platform accepted (verified `imported:1` for target `bogus`) |
| `/queue` | GET | 200 wrapped `{count, offset, limit, has_more, rows}` | 400 limit>500/limit<1/negative offset | — | Pagination params validated |
| `/queue/{id}` | GET | 200 JSON or HTML (content-negotiated) | — | 404 (HTML 404 escapes row_id — verified safe) | README documents this correctly |
| `/queue/{id}/json` | GET | 200 | — | 404 | Undocumented in README table (minor) |
| `/queue/{id}/retry` | POST | 200 `{id, status:"queued"}` | 409 canceled, 409 non-retryable state | 404 | |
| `DELETE /queue/{id}` | DELETE | 200 `{deleted}` | — | 404 | |
| `/queue/{id}/delete` | POST | 200/303 | — | 404 | HTML alias, undocumented |
| `/_purge?status=` | POST | 200 `{purged}` | 400 for statuses outside {published, dead} | — | Safe allowlist |
| `/_retry-all` | POST | 200 `{requeued}` | — | — | Retries failed+dead+publishing-with-error rows |
| `/campaign/{id}` | GET | 200 | 400 bad pagination | 404 | |
| `/campaign/{id}/cancel` | POST | 200 `{canceled}` | — | 404 | Status-guarded in all backends |
| `/ai/adapt` | POST | 200 `{ok, formats}` | 400 empty text/platforms/unknown platform, 413 >10 KB or >20 platforms | 400 AdaptError | Falls back to heuristic on LLM failure (verified) |
| `/media/specs` | GET | 200 (10 specs) | — | — | |
| `/media/transcode` | POST | 200 image bytes | 400 unknown platform/empty, 413 >10 MiB, 400 corrupt image | — | 10 MiB cap verified |
| `/profiles*` (HTML) | GET/POST | 303 redirects | — | 404 unknown profile | Secrets never rendered back (value=""); explicit `__clear` checkbox for rotation |
| `/api/profiles` | GET | 200 | — | — | Returns only id/name/emoji/color/configured — no secrets |
| `/_compose`, `/_compose-adapt` | POST | HTML fragments | server-side validation | — | XSS-escaped output (verified in source + hardening tests) |

## Cross-cutting checks

- **Authentication:** 401 without/with-wrong bearer on every protected route (JSON and HTML);
  `/healthz` JSON exempt by design; HTML healthz requires auth. `secrets.compare_digest`
  prevents timing oracles. **PASS** (plus 5 dedicated tests skipped in CI — see CI-1).
- **Origin check:** POST/PUT/PATCH/DELETE with a mismatching `Origin` → 403. PASS. Same-origin
  forms unaffected. Documented reverse-proxy caveat in README is accurate.
- **CSRF:** JSON API requires bearer header (browser forms can't send it); HTML mutations rely on
  the Origin check. Reasonable for the threat model; documented in README/SECURITY.md.
- **Rate limiting:** none on any route. **SEC-LOW/INFO:** unauthenticated `/healthz` and
  (when no token set) everything else can be hammered; self-host mitigation documented as
  "put it behind a proxy". Acceptable for v1.0.0 if documented (it is).
- **Concurrent load:** 30 parallel `/dispatch` POSTs → 30×202, 30 rows persisted correctly
  (JSONL flock held). PASS.
- **Malformed input:** malformed JSON → 400 (not 500) on `/dispatch` and `/ai/adapt`. PASS.
- **Information leakage:** error bodies are FastAPI `detail` messages; no stack traces in
  responses (500s only from backend outages, e.g. Redis down). Adapter errors in queue rows are
  redacted by `adapters/errors.redact()` (Telegram token / bearer / secret params) — covered by tests.
- **OpenAPI:** `/openapi.json` serves; **no request-body schemas** (handlers take raw `Request`),
  so the interactive docs are minimal — informational gap, not incorrect.
- **Duplicate routes:** none found in the route table.
- **Response structure consistency:** list endpoints wrap (`{count, rows…}`); single-row endpoints
  return the raw row; both stable and documented.

## Findings

| ID | Severity | Finding | Fix |
|---|---|---|---|
| API-1 | P2 | Unknown platform targets accepted at enqueue time (202), fail late in the worker (3 wasted retries, backoff, webhook noise, false client success). Repro: `POST /dispatch {"targets":["nonsense"],…}` → 202 | Add platform-membership check against `ADAPTERS` in `api/schema.validate()`; regression test |
| API-2 | P3 | README API reference omits `/dispatch/bulk`, `/queue/{id}/json`, `/_retry-all`, `/api/profiles` | Docs update (handled in Phase 10) |
| API-3 | P3 | OpenAPI docs carry no request schemas | Derive Pydantic models, or document "see README" (informational) |
| SEC-3 | Low | Unauthenticated `/healthz` JSON reveals configured platforms/queue stats | Optional: strip platform names from the open JSON, or document explicitly (README partially does) |

## Verdict

The API surface is in good shape: consistent status codes, real validation on limits/webhooks/paths,
working auth and origin checks, XSS-safe HTML rendering, and correct 4xx handling. The one real
defect is API-1 (late platform-name failure); everything else is documentation-level.
