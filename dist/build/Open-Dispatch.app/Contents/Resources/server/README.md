# Open-Dispatch

> **One API to dispatch your content anywhere.**
> Twitter / X, Instagram, Telegram, Bluesky, LinkedIn, Threads, YouTube Shorts — self-host free, source-available.

Open-Dispatch is the **infrastructure layer** for content distribution. Like Stripe is to payments, this is to posting. Integrate it from any app, n8n workflow, cron job, or AI agent: one HTTP call, every platform.

```bash
curl -X POST http://localhost:8000/dispatch -H "Content-Type: application/json" -d '{
  "targets": ["twitter:default", "bluesky:default", "telegram:default", "threads:default"],
  "formats": {
    "twitter_thread":  {"tweets": ["hello world", "thanks for reading"]},
    "bluesky_post":    {"text": "hello bluesky"},
    "telegram_message":{"text": "hello telegram"},
    "threads_post":    {"text": "hello threads"}
  }
}'
```

…or use the built-in web UI at `http://localhost:8000/` — compose, schedule, retry, watch the queue live.

## Why

- Zapier-like SaaS cross-posters are paid, closed, no API. Self-hosters get nothing.
- Open-Dispatch is **API-first** AND **UI-included**: every feature reachable from code AND a dark-themed dashboard for humans.
- One adapter contract — `publish(unit, account) -> (ok, id, err)`. Adding a new platform is ~80 LOC.

## Quick start

```bash
git clone https://github.com/Matthew-Selvam/open-dispatch
cd open-dispatch
cp .env.example .env  # fill in the platform creds you actually use
docker compose up -d
curl http://localhost:8000/healthz
open http://localhost:8000/    # web UI
```

Or local Python:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit
uvicorn api.app:app --reload         # API + UI
python -m scheduler.worker           # worker (separate terminal)
```

## Web UI

```
http://localhost:8000/         # dashboard — queue, filters, auto-refresh
http://localhost:8000/compose  # post composer
http://localhost:8000/queue/<id>  # row detail + retry
```

Dark terminal aesthetic, HTMX-driven (no JS build), 51KB of vendored htmx.min.js. Runs on the same port as the API — same `uvicorn api.app:app` covers both.

## API

| Method | Path                  | Purpose                                                |
|--------|-----------------------|--------------------------------------------------------|
| GET    | `/healthz`            | Liveness                                               |
| POST   | `/dispatch`           | Enqueue a ContentUnit for one or many platforms        |
| GET    | `/queue?status=…`     | List queue rows (queued/publishing/published/failed/dead) |
| GET    | `/queue/{id}`         | One row (JSON for API consumers, HTML for browsers)    |
| POST   | `/queue/{id}/retry`   | Reset a failed/dead row to `queued`                    |

The `/queue/{id}` endpoint content-negotiates: `Accept: application/json` returns the row dict, `Accept: text/html` (browsers) returns the detail page.

### ContentUnit shape

```json
{
  "category": "general",
  "targets": ["twitter:work", "bluesky", "threads"],
  "scheduled_for": "2026-05-19T18:00:00+00:00",
  "formats": {
    "twitter_thread":  { "tweets": ["t1", "t2"], "media_paths": [] },
    "bluesky_post":    { "text": "…", "images": [{"path": "…", "alt": "…"}] },
    "telegram_message":{ "text": "…", "photo_path": "…", "parse_mode": "HTML" },
    "instagram_post":  { "caption": "…", "image_url": "https://…" },
    "linkedin_post":   { "text": "…", "asset_urn": "urn:li:digitalmediaAsset:…" },
    "threads_post":    { "text": "…", "image_url": "https://…", "video_url": "https://…" }
  },
  "webhook_url": "https://example.com/dispatch-callback"
}
```

**Target syntax**: `platform[:account]`. Per-account env vars are `<PLATFORM>_<FIELD>_<ACCOUNT>` (uppercase). `telegram:broadcast` resolves to `TELEGRAM_CHAT_ID_BROADCAST`.

### Webhooks

If `webhook_url` is set, the worker fires `POST {url}` after each publish/fail:

```json
{ "event": "published", "id": "<row id>", "post_id": "<platform id>", "platform": "twitter:work" }
{ "event": "failed",    "id": "<row id>", "error": "…", "platform": "…", "dead": false }
```

## CLI

```bash
# One-liner from any shell, no env-var leak — talks to the running API
python cli.py send --platforms telegram --text "hello"

# Or bypass HTTP and write directly to the JSONL queue
python cli.py send --local --platforms telegram --text "hello"

python cli.py queue --status queued
python cli.py worker           # run scheduler in-process
python cli.py quick-test       # Telegram ping
```

Install as `dispatch` once you `pip install -e .`:

```bash
dispatch send --platforms twitter:work,bluesky,threads --text "shipped a thing"
```

## Adapter contract

Each `adapters/<platform>.py` exposes:

```python
def publish(unit: ContentUnit, account: str | None) -> tuple[bool, str, str]:
    """Returns (ok, post_id, error_message)."""
```

Add a platform in three steps:

1. `adapters/myplatform.py` — implement `publish`.
2. Add it to the `ADAPTERS` dict in `adapters/__init__.py`.
3. Document its `<platform>_post` format in this README.

That's the whole integration surface.

## Architecture

```
   POST /dispatch  ─▶  Queue (JSONL)  ─▶  scheduler/worker.py
                                              │
                                              ▼
                                        adapters/{tg,tw,ig,bs,li,th}.py
                                              │
                                              ▼  on publish/fail
                                          webhook_url
```

- **Queue**: JSONL on disk by default (single file, append-safe, atomic rewrite for updates). Set `REDIS_URL` in `.env` to switch to the Redis backend — multi-worker safe, `dispatch:row:<id>` strings + a ZSET for due queries. Bring up the bundled Redis service with `docker compose --profile redis up -d`. Both backends implement the same `QueueProtocol` — no API or worker changes needed to swap.
- **Retry**: exponential backoff (`WORKER_BACKOFF_BASE * 2^(attempts-1)` + jitter), gives up after `WORKER_MAX_ATTEMPTS`.
- **State**: `queued → publishing → published | failed | dead`. Failed rows are re-queued with a future `scheduled_for`. Dead rows stay for inspection.
- **No-cloud option**: everything runs from one `python` process if you `python cli.py worker` alongside `uvicorn`.

## n8n integration

Community node lives in [`n8n-node/`](./n8n-node). One node, five operations:

| Operation | Endpoint | Purpose |
|---|---|---|
| Dispatch | `POST /dispatch` | Send content (now or scheduled) |
| Adapt Caption with AI | `POST /ai/adapt` | Per-platform rewrite |
| Get Queue Row | `GET /queue/{id}` | Fetch one row |
| Retry Queue Row | `POST /queue/{id}/retry` | Re-queue a failed row |
| List Queue | `GET /queue` | List rows by status |

Build locally:
```bash
cd n8n-node
npm install --ignore-scripts && npm run build
# In your n8n install: npm link n8n-nodes-open-dispatch
```

The credential just needs your Open-Dispatch base URL (plus an optional bearer if you front it with auth).

## Media transcoding

Per-platform image resize via Pillow — Instagram square, IG Reels portrait, Twitter 16:9, LinkedIn share, YouTube Shorts cover, etc. 10 platform specs out of the box. Honors EXIF orientation, flattens RGBA to JPEG, never upscales.

```bash
# REST: transcode a Twitter card from a phone photo
curl -X POST "http://localhost:8000/media/transcode?platform=twitter" \
  -H "Content-Type: image/jpeg" \
  --data-binary @photo.jpg --output photo.twitter.jpg

# Inspect the spec for any platform
curl http://localhost:8000/media/specs | jq .twitter
```

Python:
```python
from media import transcode_image
transcode_image("photo.jpg", "instagram")  # → photo.instagram.jpg
```

## AI caption adapter

One source caption → per-platform posts. Respects character limits, style conventions (Twitter punchy, LinkedIn formal, Instagram hashtag-heavy), and falls back to a heuristic when no LLM is configured (so the endpoint never 500s on missing creds).

```bash
curl -X POST http://localhost:8000/ai/adapt -H "Content-Type: application/json" -d '{
  "text": "Open-Dispatch v0.2: web UI, Threads, AI caption rewriter. Self-host free, MIT.",
  "platforms": ["twitter", "bluesky", "linkedin", "instagram", "threads"]
}'
```

Provider priority: **Ollama** (free + local) → **OpenRouter** (any model) → **heuristic** (no LLM). Set `OPENROUTER_API_KEY` to enable cloud, set `OLLAMA_HOST` to prefer local.

The web composer has an **✦ Adapt with AI** button that previews per-platform rewrites before you dispatch.

## Roadmap

- [x] Twitter / X, Instagram, Telegram, Bluesky, LinkedIn, Threads, YouTube Shorts adapters
- [x] JSONL queue, exponential retry, webhooks
- [x] Docker compose self-host
- [x] **Web UI** (HTMX + Jinja, dark theme — dashboard, composer, retry, row detail, live auto-refresh)
- [x] **Threads adapter** (Meta Threads Graph API — text / image / video posts)
- [x] **AI caption-adaptation per platform** (OpenRouter / Ollama / heuristic fallback)
- [x] **YouTube Shorts adapter** (Data API v3 resumable upload, OAuth2 refresh-token flow)
- [ ] TikTok adapter (Content Posting API once approved)
- [x] **Redis queue backend** (set `REDIS_URL` to opt in — multi-worker safe, includes `docker compose --profile redis`)
- [x] **Postgres queue backend** (set `DATABASE_URL` to opt in — true ACID + SKIP LOCKED for cross-region multi-worker)
- [x] **Media transcoding** (per-platform image resize via Pillow — 10 specs, REST endpoint, Python API)
- [ ] Video transcoding (ffmpeg-backed, future)
- [x] **n8n community node** (`n8n-node/` — Dispatch / Adapt / Get Row / Retry / List Queue)

## Tests

```bash
pip install pytest
pytest -q
```

The schema, queue, API, and Threads adapter tests run with no network and no real credentials.

## License

MIT.
