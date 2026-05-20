# Open-Dispatch

> **One API to dispatch your content anywhere.**
> Twitter / X, Instagram, Telegram, Bluesky, LinkedIn, Threads — self-host free, source-available.

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

- **Queue**: JSONL on disk by default (single file, append-safe, atomic rewrite for updates). Redis+RQ stub lives in `api/queue.py:get_queue` — drop it in when you outgrow JSONL.
- **Retry**: exponential backoff (`WORKER_BACKOFF_BASE * 2^(attempts-1)` + jitter), gives up after `WORKER_MAX_ATTEMPTS`.
- **State**: `queued → publishing → published | failed | dead`. Failed rows are re-queued with a future `scheduled_for`. Dead rows stay for inspection.
- **No-cloud option**: everything runs from one `python` process if you `python cli.py worker` alongside `uvicorn`.

## Roadmap

- [x] Twitter / X, Instagram, Telegram, Bluesky, LinkedIn adapters
- [x] JSONL queue, exponential retry, webhooks
- [x] Docker compose self-host
- [x] **Web UI** (HTMX + Jinja, dark theme — dashboard, composer, retry, row detail, live auto-refresh)
- [x] **Threads adapter** (Meta Threads Graph API — text / image / video posts)
- [ ] TikTok adapter (Content Posting API once approved)
- [ ] YouTube Shorts adapter
- [ ] Redis + RQ backend
- [ ] Postgres queue (for >1 worker)
- [ ] AI caption-adaptation per platform (uses OpenRouter or local Ollama)
- [ ] Media transcoding (resize per platform spec)
- [ ] n8n node (official integration)

## Tests

```bash
pip install pytest
pytest -q
```

The schema, queue, API, and Threads adapter tests run with no network and no real credentials.

## License

MIT.
