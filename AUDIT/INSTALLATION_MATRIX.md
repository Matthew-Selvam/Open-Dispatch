# Installation Method Verification Matrix — Phase 2

Environment: macOS 26.5 arm64 (Docker Desktop 29.4.3, Homebrew 7.0.12, Node 26, Python 3.11–3.14 available).
Every method was tested from a clean environment following the published docs exactly.
All commands and evidence below were actually executed on the audit date.

**Headline finding (P0): the `v0.4.0` git tag contains `version = "0.1.0"` code** — two feature
generations behind `main` (no `dispatch doctor`/`campaign` subcommands, no `/dispatch/bulk`,
no auth/SSRF/XSS hardening — those commits post-date the tag). Every artifact that fetches the
tag (install.sh default, Homebrew formula) therefore installs stale, **pre-security-hardening** code.

## Matrix

| # | Method | Status | Evidence |
|---|--------|--------|----------|
| 1 | pip (GitHub URL) | **PASS** | `pip install "open-dispatch @ git+…"` + extras in clean venv; `open-dispatch` server boots; `/healthz` 200 `version 0.4.0`; `POST /dispatch` → 202 enqueued; bad target → 400; `dispatch queue` lists rows; `dispatch doctor` exit 1 with actionable output; `dispatch send --local` works |
| 2 | Source install | **PASS** | venv + `-e .` editable install used for the whole audit; suite green; server boots (see BASELINE_REPORT) |
| 3 | install.sh (macOS) | **PARTIAL (functional) / FAIL (content)** | `bash install.sh --prefix /tmp/od-install --data-dir /tmp/od-install-data --no-service` completed; wrappers created; server boots; `dispatch doctor` available only after upgrade-rerun. **But default `--version v0.4.0` fetched the stale tag**: installed `/healthz` reports `0.2.0` and CLI lacks `doctor`/`campaign` (re-run of installer with current tree restores features). Python 3.14 accepted by the version check while `pyproject` classifiers claim only 3.11/3.12 (works, but unsupported claim) |
| 4 | install.sh (Linux) | **PARTIAL (functional) / FAIL (content)** | Verified inside `ubuntu:24.04` container (apt python3.12-venv): install completes, server boots, `dispatch queue` works. Same stale-tag content problem as (3). launchd/systemd service units created but not loaded (`--no-service`); unit files validated by inspection only |
| 5 | Docker (single container) | **PASS** | `docker build -t open-dispatch:audit .` succeeds; container starts as non-root `dispatch` (uid 999); `HEALTHCHECK` reports `healthy`; enqueue → data persists across `docker restart`; `docker stop -t 10` graceful; no errors in logs |
| 6 | Docker Compose (api+worker+JSONL) | **PASS with caveat** | `cp .env.example .env; docker compose up -d` → api healthy, worker running (heartbeat visible in `/healthz`); enqueue processed. Caveat: `./data` volume mounts whatever exists in the checkout — a developer's leftover `data/queue.jsonl` gets picked up and old `queued` rows **publish for real** once credentials are added. Docs don't warn about this |
| 7 | Redis-backed deployment | **PASS** | `docker compose --profile redis up -d` with `REDIS_URL=redis://redis:6379/0`; `/healthz` reports `backend: Redis`; enqueue creates `dispatch:row:*`, `dispatch:due`, `dispatch:all_ids` keys in the real redis container. Redis outage: API returns **500** on `/queue` (no graceful degradation — P2), worker survives and keeps polling; recovery automatic after redis restart |
| 8 | Postgres-backed deployment | **FAIL — P0 defect PG-1** | Real Postgres 16 (`postgres:16-alpine`) with `DATABASE_URL=postgresql://…`: container API 500s; direct reproduction: `PostgresQueue.enqueue()` raises `psycopg2.errors.UndefinedTable: relation "open_dispatch_queue" does not exist`. Root cause: `_conn()` wraps the connection in `contextlib.closing` but **nothing ever calls `conn.commit()`** — psycopg2 rolls back the open transaction (including `_ensure_schema()`'s DDL) when the connection closes. The Postgres backend has never worked against a real server; the repo's SQL-generation stub tests cannot catch transaction semantics. *Postgres DDL was NOT visible via `\dt` after a successful "enqueue".* |
| 9 | Homebrew formula | **PARTIAL / FAIL (content)** | Formula installs via a local tap (`brew tap matthew-selvam/open-dispatch` + `brew install --build-from-source`); tarball sha256 `05de98a6…` matches the v0.4.0 tag — but that tag **is the stale 0.1.0-era code**, so brew users get the stale build. Formula mechanics (venv, three wrappers, `brew services` stanza, caveats) verified by install + server boot (`/healthz` → `0.2.0`). `brew test` could not run: local brew deps outdated (environment limitation, not a formula defect) |
| 10 | macOS DMG app | **FAIL (core function) / PARTIAL (bundle)** | `bash scripts/make-dmg.sh` builds `Open-Dispatch-0.4.0.dmg` (52 MB, arm64). Bundle verified: `CFBundleIdentifier dev.open-dispatch.macos`, `LSUIElement`, launches as a menubar process (verified via System Events; interactive clicking requires assistive access — unavailable). **P0 DIMG-1:** the bundled `Contents/Resources/bin/open-dispatch` wrapper embeds **relative build-time paths** (`cd "dist/build/bundle-prefix/opt/open-dispatch"`; `exec "dist/build/bundle-prefix/opt/open-dispatch/venv/bin/uvicorn" …`) because `make-dmg.sh` passes a relative `--prefix` and `install.sh` does not absolutize it. Running the bundled wrapper fails: `cannot execute: No such file or directory`. The shipped app **cannot start its bundled server** on any machine |
| 11 | n8n community node | **PARTIAL** | `npm install --ignore-scripts && npm run build` succeeds; `dist/credentials/OpenDispatchApi.credentials.js`, `dist/nodes/OpenDispatch/OpenDispatch.node.js`, `opendispatch.svg` all present (matches CI checks). Loading into a real n8n instance not tested (no n8n runtime available; heavy install) — operations verified by code inspection against the documented API |
| 12 | MCP server | **PASS** | stdio JSON-RPC: `initialize` + `tools/list` → 10 tools (`health, dispatch, get_queue, campaign_status, cancel_campaign, get_row, retry_row, delete_row, adapt_caption, list_platforms`). README's "Available tools" list omits `campaign_status`/`cancel_campaign` (doc drift) |
| 13 | PyPI | **NOT APPLICABLE** | Not published (`pip install open-dispatch` fails; README discloses "publish pending" in one place, but the Install table implies instant pip install) |
| 14 | CLI (as installed artifact) | **PASS** | All six subcommands execute; global `--url/--token` must precede the subcommand (documented but still a UX trap — argparse rejects `dispatch doctor --url …`) |

## Uninstall / upgrade verification

- install.sh re-run over an existing install: **PASS** (re-copies source, rebuilds venv, data dir untouched).
- No uninstall instructions exist anywhere (docs gap — P2, DOC-x).
- Homebrew: `brew uninstall open-dispatch` standard; formula leaves `var/open-dispatch` data (acceptable, undocumented).
- Docker compose: `docker compose down -v` removes volumes; `./data` bind mount persists (documented nowhere).

## External blockers

- Live social-platform publishing was **not** tested in any install path (per rules: no real posts).
- DMG signing/notarization path requires a paid Apple Developer account — not available; unsigned-build
  Gatekeeper bypass documented by README.
- n8n runtime not installed on this host.

## Reproduction commands (key results)

```bash
# pip
python3.12 -m venv /tmp/od-pip && /tmp/od-pip/bin/pip install "open-dispatch @ git+https://github.com/Matthew-Selvam/Open-Dispatch.git"
OPEN_DISPATCH_DATA=/tmp/od-pip-data /tmp/od-pip/bin/open-dispatch --port 8200 &
curl -s localhost:8200/healthz   # {"status":"ok","version":"0.4.0",…}

# stale tag proof
bash install.sh --prefix /tmp/od-install --data-dir /tmp/od-install-data --no-service
/tmp/od-install/bin/open-dispatch --port 8201 & curl -s localhost:8201/healthz
# → {"status":"ok","version":"0.2.0",…}   and: dispatch: invalid choice: 'doctor'

# Postgres commit bug (real server)
psql "$PG" -c "\dt"                       # Did not find any relations.
python -c "from api.queue import PostgresQueue; PostgresQueue(factory).enqueue(…)"
# → psycopg2.errors.UndefinedTable: relation "open_dispatch_queue" does not exist

# DMG wrapper defect
cat dist/build/Open-Dispatch.app/Contents/Resources/bin/open-dispatch
# cd "dist/build/bundle-prefix/opt/open-dispatch"   ← relative, broken after relocation
```
