# SEC-1 Remediation — Docker Compose Network Security

Status: **RESOLVED** — branch `release/v0.5.0-hardening`.
Original finding: SECURITY_AUDIT.md #7 (High) — unauthenticated API exposed by the
default Compose configuration: `_authorized()` returns `True` when
`OPEN_DISPATCH_API_TOKEN` is empty, `.env.example` leaves it empty, and
`docker-compose.yml` published `8000:8000` (all host interfaces). Verified in the
audit: `GET /profiles` → 200, `POST /dispatch` → 202 without a bearer header on an
isolated test host.

## Changes

### `docker-compose.yml` (default local)

- API port mapping changed `8000:8000` → `127.0.0.1:8000:8000`, with a comment
  explaining why and pointing to the remote-exposure docs. The API is reachable
  only from the host machine by default.
- Redis remains unpublished (internal compose network only) — unchanged.

### `docker-compose.prod.yml` (new, production-oriented)

- **Zero published ports.** The API is `expose: 8000` only; an authenticated TLS
  reverse proxy joins the compose network and is the only access path.
- Documents the required `OPEN_DISPATCH_API_TOKEN` (generate with
  `openssl rand -hex 32`).
- Redis enabled by default, still never published, with a comment on setting a
  Redis password for production (`REDIS_URL=redis://:pw@redis:6379/0`).
- API healthcheck (200 on `/healthz`) so orchestration detects a degraded API.
- External managed Postgres supported via `DATABASE_URL` in `.env` — no DB service
  is added, so no Postgres port can leak from this file at all.

### `README.md`

- Quick-start now carries a **SEC-1 warning before first launch**: loopback-only by
  default, unauthenticated without a token, and where to look to expose remotely.
- New section **"Exposing the API remotely"**: requires both a strong bearer token
  and a TLS-terminating reverse proxy; explicitly warns against merely changing the
  port mapping to `"8000:8000"`; includes a minimal Caddy example; tells operators
  how to verify listening interfaces from the host
  (`ss -tlnp | grep 8000` / `lsof -nP -iTCP:8000 -sTCP:LISTEN`).

## Verification (actual host-level inspection, disposable containers)

Environment: disposable compose project (`-p od-sec1`) with an empty env file; **api
service only** (no worker started → no possibility of publishing to real platforms);
torn down afterwards with `down -v`.

| Check | Method | Result |
|---|---|---|
| Resolved compose binding | `docker compose config` | `host_ip: 127.0.0.1`, `target: 8000` |
| Actual container mapping | `docker port open-dispatch-api` | `8000/tcp -> 127.0.0.1:8000` |
| Actual host listener | `lsof -nP -iTCP:8000 -sTCP:LISTEN` | `TCP 127.0.0.1:8000 (LISTEN)` — loopback only |
| Wildcard exposure | `netstat -anv -p tcp` filtered for `*:8000` | none |
| Functional from host | `curl http://127.0.0.1:8000/healthz` | `200 {"status":"ok",...}` |
| Redis published ports | `docker compose --profile redis config` | `published:` count = **0** |
| Prod compose published ports | `docker compose -f docker-compose.prod.yml config` | `published:` count = **0**, one `expose: 8000` |
| No leftover state | `docker compose -p od-sec1 down -v` | no disposable containers/volumes remain; pre-existing containers returned to pre-session state (stopped, data intact) |

## Requirements mapping

1. Database ports not publicly exposed by default — no DB service in compose;
   external DBs are env-config only; **met**.
2. Redis not publicly exposed by default — never published, verified **0 published
   ports** in both compose files; **met**.
3. Internal services communicate through private Docker networks — api/worker/redis
   share the default compose network; no host publishing for internal traffic; **met**.
4. User-facing services bind an appropriate interface — loopback by default; **met**.
5. Local development remains straightforward — unchanged quick-start except the
   mapping (still `localhost:8000` from the host); **met**.
6. Production deployment instructions explain reverse proxy + HTTPS — README section
   added; **met**.
7. No hardcoded credentials — none added; token generation documented; **met**.
8. Authentication not weakened — no auth code changed in this remediation (the
   unauthenticated-by-default API behavior is documented as a known limitation and
   paired with the loopback default; see "Known limitations" below); **met with note**.
9. Existing install methods unbroken — compose is the only touched deployment
   surface; JSONL/pip/Homebrew/DMG paths untouched; **met**.

## Known limitations (explicitly documented, not silently waived)

- The API is still **unauthenticated when `OPEN_DISPATCH_API_TOKEN` is unset**. With
  the loopback default this is defensible for a single-user local deployment (the
  documented quick-start), but operators exposing the API must set a token — the
  README now says so before first launch and in the remote-exposure section.
- SEC-2 (request bodies buffered before size enforcement) is a separate P2 finding,
  **not** addressed here; reverse-proxy body limits are the interim mitigation, as
  the original audit recommended.
- No API rate limiting (audit table note) — unchanged; reverse proxy rate limits are
  the interim mitigation for exposed deployments.
