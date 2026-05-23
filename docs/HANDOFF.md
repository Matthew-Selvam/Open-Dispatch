# Open-Dispatch — Engineering Handoff

> Self-contained onboarding for a coding agent (or new contributor) picking up
> the next phase. Read this top to bottom; you do **not** need any prior chat
> history. Everything below is verified against the repo at tag/state `v0.4.0`.

---

## 1. What this is

**Open-Dispatch** — *"One API to dispatch content anywhere — open-source cross-poster."*
A self-hosted service that takes one content payload and publishes it to up to 7
social platforms. Two faces:

- **JSON API** for scripts/automation (`POST /dispatch`, etc.).
- **HTMX dashboard** (dark terminal aesthetic, green `#4ade80`) for humans — compose, queue, health, profiles.

A background **worker** polls a pluggable queue (JSONL / Redis / Postgres) and
calls the right platform adapter. AI caption adaptation degrades gracefully
(Ollama → OpenRouter → heuristic), never hard-failing offline.

Repo: `https://github.com/Matthew-Selvam/Open-Dispatch` · local: `~/code/open-dispatch`
Stack: Python 3.11+, FastAPI, Jinja2, HTMX. Landing page: Next.js 15 + Tailwind v4 in `landing/`.

---

## 2. How to run (confirm exact commands in `README.md`)

```bash
pip install -r requirements.txt          # or: pip install -e .
uvicorn api.app:app --reload             # API + dashboard on :8000
python -m scheduler.worker               # background dispatcher (separate shell)
pytest                                    # full test suite — keep it green
```

`.env.example` lists every credential env var. Docker: `docker-compose up`.

---

## 3. Architecture map

```
api/
  app.py        FastAPI app — all routes (JSON + HTMX). Content negotiation: HTML for browsers, JSON for curl.
  schema.py     ContentUnit dataclass + validate() + CAPTION_LIMITS + parse_target().
  queue.py      Pluggable queue backends (JSONL / Redis / Postgres w/ SKIP LOCKED).
adapters/
  __init__.py   ADAPTERS registry dict + Adapter Protocol.
  twitter.py bluesky.py threads.py linkedin.py instagram.py telegram.py youtube.py
scheduler/
  worker.py     Poll loop; writes data/.worker_heartbeat each tick (health uses it).
ai/             Caption adaptation (Ollama → OpenRouter → heuristic).
web/templates/  Jinja2: base, compose, health, queue, profiles.
profiles.py     Named per-platform credential sets.
tests/          pytest — one file per subsystem. Mirror these when adding features.
landing/        Next.js marketing site (blue #3b9eff). COMPARE_POINTS competitive grid already built.
n8n-node/  macos-app/  cli.py  install.sh  Formula/   Distribution surfaces.
```

---

## 4. Core contracts — read before writing code

### ContentUnit (`api/schema.py`)
The single payload every adapter consumes:
```python
ContentUnit(
    id, created_at, category="general",
    targets=["twitter", "bluesky:work"],   # "platform" or "platform:account"
    scheduled_for=None,                      # ISO-8601 or None
    formats={"twitter_thread": {...}},       # per-platform format blocks
    webhook_url=None, profile_id=None,
)
```
- `parse_target("twitter:work")` → `("twitter", "work")`. Platform must match `[a-z]+`.
- `validate(unit)` returns a list of error strings (empty == valid).
- `CAPTION_LIMITS` already has: instagram 2200, twitter 280, telegram 4096, youtube 5000, **tiktok 2200**, bluesky 300, linkedin 3000, threads 500.

### Adapter contract (`adapters/*.py`)
```python
def publish(unit: ContentUnit, account: str | None = None) -> tuple[bool, str, str]:
    # returns (ok, post_id, error_message)
```
- Read your format block from `unit.formats["<platform>_<kind>"]` (e.g. `twitter_thread`).
- Credentials from env vars with optional `_<ACCOUNT>` uppercase suffix
  (e.g. `TWITTER_ACCESS_TOKEN_WORK`, falling back to `TWITTER_ACCESS_TOKEN`).
- Lazy-import the SDK inside `publish` and return a friendly error if it's missing
  (`return False, "", "tweepy not installed (pip install tweepy)"`).
- Register the module in `adapters/__init__.py` → `ADAPTERS` dict.
- Each adapter is ~80 lines. **Copy `adapters/twitter.py` as the template.**

---

## 5. ✅ Already shipped — DO NOT redo

- All 7 adapters; queue backends; worker + heartbeat; health dashboard with
  worker status + retry-all; compose page (datetime-local picker → ISO-8601, live
  char counters); delete/purge; profiles (named credential sets); AI caption adapter.
- README (badges, demo hero, star CTA, star-history), CHANGELOG (keep-a-changelog
  through v0.4.0), `docs/migrating-from-zernio.md`, `docs/social-preview.svg`,
  `docs/DEMO_SCRIPT.md`.
- Landing page `COMPARE_POINTS` "Why not hosted tools?" section.
- **Every GitHub URL is already correct case** (`Matthew-Selvam/Open-Dispatch`) — zero lowercase left. Don't "fix" links.

---

## 6. 🔨 Remaining work — prioritized

Do these in order. One PR/commit per task. Add/extend tests for each. Keep `pytest` green.

### Task 1 — Structured API error codes  *(small, do first)*
Today JSON errors are inconsistent: some `detail` are plain strings, some `{"errors": [...]}`.
Standardize **JSON API** responses (leave HTMX/HTML routes untouched) to:
```json
{ "error": { "code": "VALIDATION_ERROR", "message": "human text",
             "details": [{ "field": "targets", "msg": "must be non-empty" }] } }
```
- Code set: `VALIDATION_ERROR` (400), `NOT_FOUND` (404), `ADAPTER_FAILED` (502),
  `RATE_LIMITED` (429), `INTERNAL` (500).
- Implement a FastAPI exception handler + a small `error_response(code, message, details=None)` helper in `api/app.py`.
- **Accept:** `/dispatch` with bad payload and `/queue/{bad_id}/json` return the new shape; `test_api.py` asserts `code`; HTML dashboard behavior unchanged.

### Task 2 — TypeScript SDK  *(medium)*
A typed client so users can `npm install` and call the API.
- New dir `clients/typescript/` (or `sdk/`). Class `OpenDispatch({ baseUrl, apiKey? })` with
  `dispatch(unit)`, `getQueue()`, `getStatus(id)`, `retry(id)`. Export a typed `ContentUnit`.
- Build with `tsup` (ESM + CJS + `.d.ts`). Include README + a runnable example.
- npm name `open-dispatch` may be taken — if so use scope `@matthew-selvam/open-dispatch`.
- **Accept:** `npm run build` produces dist + types; example script dispatches against a local server.
- **Note:** *publishing* to npm is a human step (requires the owner's npm login) — just build the package, don't publish.

### Task 3 — Bulk video upload  *(medium)*
- Extend media handling (`/media/transcode` + add `POST /media/bulk`) to accept multiple
  files, returning a list of media refs usable in `formats[*].media_paths`.
- Wire chunked/resumable upload for video-capable adapters (youtube, instagram, twitter).
- **Accept:** endpoint accepts N files and returns N refs; `test_media_transcode.py` extended.

### Task 4 — Analytics fetch endpoint  *(large)*
- Add optional adapter fn `fetch_metrics(post_id, account) -> dict | None` (likes, reposts, comments, views).
- New route `GET /analytics/{platform}/{post_id}` returning normalized metrics; unsupported platforms
  return `{"error": {"code": "NOT_SUPPORTED"}}` (reuse Task 1 shape).
- Implement at least **Bluesky + Twitter** first; stub the rest.
- **Accept:** route returns normalized metrics for an implemented platform; tests cover supported + unsupported.

### Task 5 — Inbox webhooks  *(large)*
- `POST /webhooks/{platform}` receiver for mentions/replies/DMs, with per-platform signature verification.
- Persist to an inbox store (reuse the queue backend pattern); expose `GET /inbox`.
- **Accept:** signed sample payload is verified + stored; bad signature → 401; `GET /inbox` lists items; tests added.

### Task 6 — New adapters: Mastodon, Pinterest, TikTok  *(medium each)*
- Copy `adapters/twitter.py`. Format keys: `mastodon_status`, `pinterest_pin`, `tiktok_video`.
- Register each in `adapters/__init__.py` → `ADAPTERS`.
- Add `mastodon` (500) and `pinterest` (~500) to `CAPTION_LIMITS` in `api/schema.py` (tiktok already present).
- Mirror char limits into `web/templates/compose.html` and the landing platform list.
- **Accept:** `test_adapters.py` covers each new adapter (mock the network); missing-creds path returns a clean error.

---

## 7. 🚫 Out of scope for the coding agent (owner does these manually)

- Record `docs/demo.gif` (Kap → `gifsicle -O3 --lossy=80 --colors 128`).
- Convert `docs/social-preview.svg` → 1280×640 PNG, upload via GitHub → Settings → Social preview.
- Tag the GitHub Release `v0.4.0` (paste the CHANGELOG `## [0.4.0]` section).
- Verify/set the Vercel landing URL (`gh repo edit Matthew-Selvam/Open-Dispatch --homepage "..."`).
- Any account creation, publishing, or money/credential entry.

---

## 8. Guardrails

- Keep `pytest` green; add tests with every feature.
- Don't change the HTMX dashboard's HTML behavior when touching JSON error shapes.
- Adapters lazy-import their SDK and never crash the worker on a single failure — return `(False, "", msg)`.
- Match existing style: type hints, `from __future__ import annotations`, small focused functions.
- Don't reformat unrelated files or "fix" already-correct GitHub URLs.
