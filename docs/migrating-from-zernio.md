# Migrating from a hosted scheduler to Open-Dispatch

> Moving off a hosted social scheduler (Buffer, Hootsuite, Zernio, Publer, and friends)?
> This guide gets you from "paying per account every month" to "self-hosting for free" in
> about ten minutes.

Open-Dispatch is a self-hosted dispatch API. You run it on your own machine or a cheap VPS,
your platform credentials never leave that box, and there are no per-account fees because
there's no "platform" charging you — it's MIT-licensed software you own.

---

## Why people switch

| | Typical hosted scheduler | Open-Dispatch |
|---|---|---|
| **Pricing** | Per-connected-account, monthly — costs scale with how many accounts you run | Self-host free; one box runs unlimited accounts |
| **Credentials** | Stored on the vendor's servers | Stay in your own `.env` / database |
| **Errors** | Often surfaced vaguely, if at all | Every failure is visible and retryable in the dashboard |
| **Inbox / analytics / extra platforms** | Frequently sold as separate paid tiers | All adapters included; add more in ~80 lines |
| **Your data** | Lives with the vendor | You own the queue end-to-end |
| **Lock-in** | Proprietary | MIT — fork it, extend it, never get rug-pulled |

These are properties of *self-hosting*, not accusations about any one product — the point
is that owning the infrastructure removes a whole class of recurring costs and constraints.

---

## What you'll need

- A machine to run it on (your laptop, a Raspberry Pi, or a $5/mo VPS)
- Docker, **or** Python 3.11+
- Developer/API credentials for the platforms you post to (the same ones any tool needs —
  you're just holding them yourself now)

---

## Step 1 — Install Open-Dispatch

The fastest path is Docker:

```bash
git clone https://github.com/Matthew-Selvam/Open-Dispatch
cd Open-Dispatch
cp .env.example .env
docker compose up -d
curl http://localhost:8000/healthz   # → {"status":"ok"}
```

Prefer no Docker? `pip install git+https://github.com/Matthew-Selvam/Open-Dispatch.git`
and run `uvicorn api.app:app`. Five install methods are documented in
[INSTALL_METHODS.md](../INSTALL_METHODS.md).

---

## Step 2 — Move your accounts into `.env`

Hosted tools connect accounts behind an OAuth screen. Self-hosting means you create the
equivalent credentials once and paste them into `.env`. You only configure the platforms you
actually use — missing variables are silently skipped.

```env
# Twitter / X
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...

# Bluesky
BLUESKY_HANDLE=you.bsky.social
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-...
TELEGRAM_CHAT_ID=@your_channel
```

The full variable list for all seven platforms is in [`.env.example`](../.env.example).

> **Running several brands or clients?** Use **Profiles** instead of one flat `.env`. Each
> profile is a named set of per-platform credentials you pick at dispatch time — the
> self-hosted equivalent of "connected accounts," with no per-account bill. Create them at
> `http://localhost:8000/profiles`.

---

## Step 3 — Map your workflow

| What you did in the hosted tool | How you do it here |
|---|---|
| Pick accounts from a dropdown | `targets: ["twitter", "bluesky:brandB", "telegram"]` |
| Schedule a post for later | `scheduled_for` (ISO-8601) in the request, or the datetime picker in the composer |
| "Customize per network" | A per-platform `formats` block (thread vs single post vs caption) |
| Bulk/CSV upload | Loop over `POST /dispatch` from a script, cron, or n8n |
| Zapier / Make automations | The [n8n community node](../n8n-node) or a plain HTTP call |
| Retry a failed post | The dashboard's retry button, or `POST /queue/{id}/retry` |

A single dispatch to several platforms:

```bash
curl -X POST http://localhost:8000/dispatch \
  -H "Content-Type: application/json" \
  -d '{
    "targets": ["twitter", "bluesky", "telegram"],
    "formats": {
      "twitter_thread":   {"tweets": ["moved off my paid scheduler today"]},
      "bluesky_post":     {"text": "moved off my paid scheduler today"},
      "telegram_message": {"text": "moved off my paid scheduler today"}
    }
  }'
```

Or skip the JSON entirely and use the composer at `http://localhost:8000/compose` — type
once, tick the platforms, hit **Dispatch**.

---

## Step 4 — Keep it running

For a single machine, run the worker alongside the API:

```bash
python -m scheduler.worker        # or: dispatch worker
```

The Docker Compose file already runs the worker as its own service, and the Homebrew /
install.sh paths wire up launchd or systemd so it starts at boot. Check the **Health**
dashboard (`/healthz` in a browser) to confirm the worker is alive — it shows a live
heartbeat and your queue stats.

---

## Step 5 — Cancel the subscription

Once your posts are flowing through Open-Dispatch, close the hosted account. Because your
credentials live in your own `.env`, nothing depends on the vendor anymore — revoke the app
tokens on each platform's developer settings if you want a clean break.

---

## FAQ

**Do I lose scheduling reliability by self-hosting?**
The worker polls on an interval and retries with exponential backoff. On a VPS with systemd
(or Docker's `restart: unless-stopped`) it runs as durably as any always-on service you own.

**What about platforms Open-Dispatch doesn't support yet?**
The adapter contract is one function (~80 lines). [CONTRIBUTING.md](../CONTRIBUTING.md) walks
through adding one — TikTok, Mastodon, and Pinterest are common requests and good first PRs.

**Can a team use it?**
Yes — point it at the Postgres backend (`DATABASE_URL`) for multi-worker, multi-region
operation, and put it behind your own auth proxy.

**Is there a hosted version?**
No — that would reintroduce the exact costs and lock-in this project exists to remove. It's
self-host by design.

---

Stuck on a step? Open a [Discussion](https://github.com/Matthew-Selvam/Open-Dispatch/discussions)
— and if this saved you a subscription, a ⭐ on the
[repo](https://github.com/Matthew-Selvam/Open-Dispatch) helps other people find it.
