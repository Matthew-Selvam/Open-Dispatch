# n8n-nodes-open-dispatch

n8n community node for [Open-Dispatch](https://github.com/Matthew-Selvam/Open-Dispatch).

## What it does

One node, six platforms: Twitter / X, Bluesky, Telegram, Instagram, LinkedIn, Threads. Hits your self-hosted Open-Dispatch instance.

## Operations

| Operation | Endpoint | Purpose |
|---|---|---|
| **Dispatch** | `POST /dispatch` | Send content to one or many platforms (now or scheduled) |
| **Adapt Caption with AI** | `POST /ai/adapt` | Rewrite a caption per platform via OpenRouter / Ollama / heuristic |
| **Get Queue Row** | `GET /queue/{id}` | Fetch a single queue row |
| **Retry Queue Row** | `POST /queue/{id}/retry` | Re-queue a failed/dead row |
| **List Queue** | `GET /queue` | List queue rows, optionally filtered by status |

## Install

### From npm (when published)
```bash
npm install n8n-nodes-open-dispatch
```

### Locally (during development)
```bash
cd n8n-node
npm install
npm run build
# In your n8n install:
npm link n8n-nodes-open-dispatch
```

Add `~/.n8n/custom` to your n8n setup if needed. Restart n8n.

## Credential

Open-Dispatch by default has no auth (designed for trusted-network self-host). The credential has two fields:

- **Base URL** (required) — e.g. `http://opendispatch:8000`
- **API Key Header** (optional) — bearer token if you front it with a reverse proxy that requires auth

n8n tests the credential by hitting `/healthz`.

## Example workflows

### Cross-post a new blog post
```
[RSS Trigger] → [Open-Dispatch: Dispatch]
                ├── platforms: twitter, bluesky, linkedin, threads
                ├── text: {{ $json.title }} — {{ $json.link }}
                └── useAdapter: true   (AI rewrites per platform)
```

### Schedule a campaign batch from a Google Sheet
```
[Google Sheets: Read] → [Open-Dispatch: Dispatch]
                        ├── text: {{ $json.caption }}
                        ├── scheduledFor: {{ $json.publish_at }}
                        └── platforms: {{ $json.platforms.split(',') }}
```

### Retry every failed row nightly
```
[Cron: 02:00] → [Open-Dispatch: List Queue (status=failed)] → [Open-Dispatch: Retry Queue Row]
```

## License

MIT.
