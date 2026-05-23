# Demo GIF — recording script

The 30-second demo GIF is the single highest-converting asset on the README and
ProductHunt listing. It must prove the core promise in one unbroken take:
**compose once → dispatch to every platform → watch it publish live.**

Target: `docs/demo.gif`, ~760px wide, < 8 MB, looping.

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
gifsicle -O3 --lossy=80 --colors 128 demo-raw.gif -o demo.gif
```

---

## Pre-flight (do once, off-camera)

1. Seed `.env` with **Telegram + Bluesky** creds (the two easiest to make real posts to a
   test channel/account). Everything else can be unconfigured — green dots only show for
   what's real, which is honest.
2. Start the worker in a background tab so posts actually flip to `published`:
   `python -m scheduler.worker`
3. Clear the queue so the dashboard starts empty: delete `data/queue.jsonl` (or click
   "Clear published").
4. Have the Compose text pre-decided so you don't fumble typing on camera.

---

## Shot list (≈30s)

| Time | Scene | What the viewer sees |
|---|---|---|
| **0:00–0:04** | Terminal | Type `docker compose up -d` → `✔ open-dispatch started on :8000`. Crisp, one line. |
| **0:04–0:07** | Browser | Switch to browser already at `localhost:8000`. Empty queue, dark dashboard. Clean first impression. |
| **0:07–0:09** | Nav | Click **Compose**. |
| **0:09–0:13** | Compose | Type the post: `shipped open-dispatch v0.4 — self-host your social posting 🚀`. Char counter ticks up live. |
| **0:13–0:16** | Platforms | Tick **Telegram, Bluesky, Twitter**. Green dots light next to the configured ones. |
| **0:16–0:17** | Submit | Click **Dispatch →**. Success panel slides in. |
| **0:17–0:18** | Nav | Click **Dashboard**. |
| **0:18–0:24** | Dashboard | 3 rows appear: status flips `queued` → `publishing` → `published` (green). This is the money shot — let it breathe. |
| **0:24–0:28** | Health | Click **Health**. Pulsing green dot, "Worker: running", queue stats, top-platforms bars. |
| **0:28–0:30** | Hold | Rest on the Health dashboard. Last frame should be visually rich (it's the loop point). |

---

## Direction notes

- **No mouse hunting.** Rehearse the click path 3× before recording so the cursor moves
  decisively. Hesitation reads as "this is fiddly."
- **Let the status flip land.** The `queued → publishing → published` transition is the
  whole pitch — don't cut away early. Auto-refresh is every 5s; if it's too slow for the
  take, temporarily set `WORKER_POLL_INTERVAL=2` and the dashboard `hx-trigger="every 2s"`.
- **Keep it real.** Use a throwaway Telegram channel + Bluesky test account so the posts
  genuinely go out. Fake demos get called out on HN.
- **One take, no captions.** The GIF should be self-explanatory. Save the words for the
  README copy around it.

## Where it ships

- `README.md` hero (already wired to `docs/demo.gif`)
- ProductHunt gallery (export a higher-res MP4 too for PH — they accept video)
- Reddit/HN posts (Reddit renders GIFs inline; HN gets a link)
- Landing page hero (`landing/` — swap the static screenshot for the GIF)
