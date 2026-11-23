# Demo GIF — recording script

The 30-second demo GIF is the README's proof of the core workflow:
**compose once → dispatch to configured destinations → watch the worker confirm publication.**

This is an honest end-to-end demo of the configured test destinations, not a claim
that every platform adapter is exercised.

Target: `docs/demo.gif`, ~760px wide, 15 fps, < 5 MB, looping.

---

## Tooling

| Need | Pick | Notes |
|---|---|---|
| Screen → GIF (macOS) | [Kap](https://getkap.co) (free) | Export as GIF, 760px wide, 15 fps |
| Screen → GIF (alt) | CleanShot X / Gifox | Same settings |
| Clean terminal | iTerm2 or Ghostty, large font (18pt+), dark theme | Hide the dock + menu bar |
| Browser | Brave/Chrome, zoom 110%, hide bookmarks bar | Use a clean profile, no extensions visible |

Compress afterwards with [gifsicle](https://www.lcdf.org/gifsicle/):

```bash
gifsicle -O3 --lossy=80 --colors 128 demo-raw.gif -o docs/demo.gif
```

---

## Pre-flight (do once, off-camera)

1. Create dedicated demo destinations: a **private Telegram test channel** and a
   **throwaway Bluesky test account**. Bluesky posts should be treated as public;
   use neutral demo text and never use a personal, production, client, or brand
   account. Do not include personal information in the post.
2. Put only the Telegram and Bluesky test credentials in the local, git-ignored
   `.env`. Never show the file, tokens, credential screens, or logs containing
   secrets in the recording. Other platforms can remain unconfigured.
3. Use **one worker process only**. With Docker Compose, `docker compose up -d`
   starts both the API and worker; do not also run
   `python -m scheduler.worker`. For a non-Compose local setup, start the API
   and one worker separately.
4. Use a disposable local data directory. For the default JSONL setup, stop the
   Compose services before clearing only that demo instance's
   `data/queue.jsonl`, then start them again. Never delete or reset a shared
   or production data directory. Alternatively, use the dashboard's
   **Clear published** action where appropriate.
5. Have the Compose text pre-decided so you don't fumble typing on camera.

The worker really publishes to the configured test destinations. Do not fake a
`published` state. If a recording is ever made with a simulated/mock flow,
label it clearly as simulated rather than presenting it as a live publish.

---

## Shot list (≈30s)

| Time | Scene | What the viewer sees |
|---|---|---|
| **0:00–0:04** | Terminal | Run `docker compose up -d`, then `docker compose ps`. Show the real API health status and the worker running; do not add a made-up startup banner. |
| **0:04–0:07** | Browser | Switch to the browser at `localhost:8000`. Empty queue, dark dashboard. Clean first impression. |
| **0:07–0:09** | Nav | Click **Compose**. |
| **0:09–0:13** | Compose | Type: `Open-Dispatch v0.5.0 — one post, two destinations.` Char counter ticks up live. |
| **0:13–0:16** | Platforms | Select **Telegram and Bluesky only** — the two destinations configured in pre-flight. Do not select an unconfigured platform. |
| **0:16–0:17** | Submit | Click **Dispatch →**. Show the real success response. |
| **0:17–0:18** | Nav | Click **Dashboard**. |
| **0:18–0:24** | Dashboard | Show the two real queue rows and their actual status transitions. Let `queued → publishing → published` land; do not fake or manually edit statuses. |
| **0:24–0:28** | Health | Click **Health**. Show the worker heartbeat and queue stats. |
| **0:28–0:30** | Hold | Rest on the Health dashboard. Last frame should be visually rich (it's the loop point). |

---

## Direction notes

- **No mouse hunting.** Rehearse the click path 3× before recording so the cursor moves
  decisively. Hesitation reads as "this is fiddly."
- **Let the status transition land.** Dashboard refresh is periodic; wait for the
  actual worker result rather than cutting away early. Never change a status by hand
  to make the recording fit the time target.
- **Keep it safe and real.** Publish only to the dedicated test destinations above.
  The GIF is public, so keep the post neutral and expose no private details. Fake
  demos get called out on HN.
- **One take, no captions.** The GIF should be self-explanatory. Save the words for the
  README copy around it.

## Where it ships

- `README.md` hero (already wired to `docs/demo.gif`)
- ProductHunt gallery (export a higher-res MP4 too for PH — they accept video)
- Reddit/HN posts (Reddit renders GIFs inline; HN gets a link)
- Landing page hero (`landing/` — swap the static screenshot for the GIF)
