# Security audit — Phase 6

Scope: FastAPI routes and middleware, queue/worker, profile storage, media paths and uploads, Docker/Compose, dependencies and existing hardening tests. No external systems were attacked. The API probe used a temporary data directory and enqueued only a fake Discord-target row; no worker ran and no social post was made. Dependency scan: `/tmp/od-venv/bin/pip-audit --local --format=json` on the audit virtualenv, 2026-11-10.

## Confirmed findings

### SEC-1 — High: unauthenticated API exposed by default Compose configuration

**Evidence:** `api/app.py` makes `_authorized()` return `True` when `OPEN_DISPATCH_API_TOKEN` is empty. The supplied `.env.example` leaves it empty. `docker-compose.yml` publishes `8000:8000`, which binds all host interfaces. With no token in an isolated test, `GET /profiles` returned 200 and `POST /dispatch` returned 202 and persisted a queue row. README warns about this but the default quick-start still creates the exposure.

**Impact:** anyone who can reach a default deployment can create or delete profiles and queue rows, trigger platform posts using configured credentials, and see queue content. **Safe reproduction:** start the supplied Compose configuration on a trusted test host, then request `/profiles` or POST a harmless row to `/dispatch` without a bearer header. **Fix:** bind the default Compose port to loopback (`127.0.0.1:8000:8000`) and require an explicit token or authenticated reverse proxy for remote access; make the quick-start instructions state this before first launch.

### SEC-2 — Medium: whole request bodies are read before size enforcement

**Evidence:** `/dispatch` calls `await request.json()` then measures serialized size; `/dispatch/bulk` calls `await request.body()` or `await upload.read()` before checking its 1 MiB limit; `/media/transcode` calls `await request.body()` or `await upload.read()` before checking its 10 MiB limit. The multipart parser also runs before these checks. **Impact:** a remote client of an exposed instance can consume memory and CPU with oversized concurrent requests despite the advertised limits. **Safe reproduction:** code path inspection; no resource exhaustion was performed. **Fix:** enforce limits during streaming and set reverse-proxy body limits. Include a bounded integration test.

### SEC-3 — Low: open health probe reveals deployment metadata

**Evidence:** unauthenticated JSON `/healthz` includes version, backend, worker liveness, counts, failures and configured platform names. **Impact:** minor reconnaissance data for anyone who can reach the service. **Safe reproduction:** `GET /healthz` without authorization when a token is configured. **Fix:** keep the liveness probe minimal and move detailed status behind authentication.

### SEC-4 — Low: dependency finding needs applicability review

**Evidence:** `pip-audit --local` found `oauthlib 3.3.1` advisories `PYSEC-2026-4114` and `CVE-2026-49272` (fix version 4.0.1), and `pip 26.1.2` advisory `PYSEC-2026-3721` (fix 26.2). The oauthlib issues concern OAuth **server** authorization-code/device-code grants; Open Dispatch uses client-side publishing through Tweepy, so exploitability in this product is not established. The pip issue concerns installing from a malicious package index and is a toolchain issue, not a running-service path. `requirements.txt` and `requirements-docker.txt` use lower bounds and no lock, so future installs can resolve different dependency versions. **Fix:** pin or constrain a tested dependency set; verify Tweepy compatibility before moving oauthlib to 4.0.1; upgrade build tooling.

## Reviewed controls and limits

| Area | Observation |
|---|---|
| Authentication/authorization | Bearer token comparison uses `secrets.compare_digest`; all routes except JSON `/healthz` are protected when token is configured. One global token, no account isolation or roles. |
| CSRF/CORS | Mutating requests with an `Origin` header must match `request.base_url`. No permissive CORS middleware. Browser dashboard cannot send bearer header when token protection is on; README acknowledges proxy requirement. |
| SSRF | Webhook URL validation requires HTTPS/public host, checks DNS results, and pins the connection to the validated IP; redirects disabled. Existing hardening tests cover private addresses and malformed ports. |
| SQL/command injection | PostgreSQL values are parameterized; table name is a code constant. No `shell=True` or dynamic shell invocation found in the reviewed runtime paths. |
| Path traversal | API rejects absolute/`..` media paths; `media.paths` resolves symlinks and enforces root containment when a media root is configured. `.env.example` correctly warns that an unset `OPEN_DISPATCH_MEDIA_DIR` weakens direct file API confinement. |
| XSS | Jinja autoescaping and `html.escape` cover reviewed dynamic HTML; profile form never renders stored credential values. Existing XSS tests cover key routes. |
| Credential storage/logging | `profiles.json` stores plaintext credentials with directory mode 0700 and file mode 0600 after save. Worker suppresses HTTP client INFO logs that can include token-bearing URLs. Queue errors use redaction. Data-directory permissions and backups remain operator responsibilities. |
| Docker | Runtime is non-root. Redis is internal to Compose network and not host-published. Base image and Python dependencies are not digest/version pinned, which weakens reproducibility. |
| Rate limiting | No API rate limits. With SEC-1, public deployments are exposed to request flooding. |

## Release impact

SEC-1 is a release blocker for the documented default Compose setup. SEC-2 needs a streaming or proxy limit before recommending any exposed deployment. The scan is a snapshot of the audit virtualenv, not proof that every installation artifact has the same dependency versions; scan the final release image and wheel environment after repairs.
