# Platform Adapter Audit — Phase 4

Scope: all ten advertised platforms. Method: full source review of each adapter, cross-check of
the existing 355-test suite (which exercises every adapter with mocked HTTP), live probing of
validation paths, and documentation-vs-implementation comparison. **No real posts were made**
(per operating rules); live sandbox E2E was not possible — see "Live verification" below.

## Capability & verification matrix

Legend: ✅ = implemented/verified · ⚠️ = partial/caveat · ❌ = not implemented · 🧪 = unit-tested (mocked) · 🔒 = external approval required · 🚫 = live-verified NOT done

| Platform | Adapter LOC | Auth flow | Token refresh | Text | Image | Video | Mock tests | Live verified | External approval needed |
|---|---|---|---|---|---|---|---|---|---|
| X / Twitter | 116 | API keys + user tokens (OAuth1 for media upload, OAuth2-ish Client for v2) | ❌ (static tokens; 3-legged OAuth out of scope) | ✅ threads w/ reply chaining | ✅ ≤4 via v1.1 media_upload (local files) | ❌ | 🧪 44 tests | 🚫 | 🔒 paid API tier for write access (Basic $200/mo) |
| Bluesky | 121 | handle + app password (session login per publish) | n/a (session created per call) | ✅ + threads | ✅ ≤4 blobs w/ alt text | ❌ | 🧪 | 🚫 | none (open protocol) |
| Telegram | 213 | bot token + chat id | n/a | ✅ HTML-safe chunking @4096 | ✅ sendPhoto (caption 1024) | ✅ sendVideo | 🧪 | 🚫 | none (bot token) |
| Instagram | 146 | IG user id + Graph token | ❌ | ✅ caption ≤2200 | ✅ image_url (public URL) | ✅ REELS video_url | 🧪 | 🚫 | 🔒 Meta app review + Business/Creator account |
| LinkedIn | 86 | bearer + author URN | ❌ (60-day tokens, no refresh) | ✅ ≤3000 | ⚠️ pre-uploaded asset_urn only; `image_url` documented but unused | ❌ | 🧪 | 🚫 | 🔒 LinkedIn app approval (`w_member_social`) |
| Threads | 172 | user id + long-lived token | ❌ | ✅ ≤500 | ✅ image_url | ✅ video_url | 🧪 | 🚫 | 🔒 Meta app review (threads_content_publish) |
| YouTube | 223 | OAuth2 refresh-token flow | ✅ (refresh token → access token each publish) | ✅ title/description ≤5000, auto-#Shorts | ❌ (thumbnails not implemented) | ✅ resumable upload, streams file | 🧪 | 🚫 | 🔒 Google OAuth consent + API enabled; **quota: videos.insert = 1600 units/day default → ~6 uploads/day** (not documented) |
| TikTok | 166 | OAuth user token (video.publish scope) | ❌ | ✅ caption ≤2200 | ❌ | ✅ PULL_FROM_URL (public URL required) + status polling | 🧪 | 🚫 | 🔒 TikTok developer app audit required for Content Posting API |
| Facebook | 97 | page id + page token | ❌ | ✅ ≤63206 (+ link preview) | ✅ photos (public URL) | ✅ videos (file_url) | 🧪 | 🚫 | 🔒 Meta app review + Page token |
| Discord | 67 | webhook URL (no bot) | n/a | ✅ ≤2000 | ❌ (no attachment upload) | ❌ | 🧪 | 🚫 | none (webhook) |

Status summary: **Implemented: 10/10 · Unit tested (mocked): 10/10 · Integration tested against
real platforms: 0/10 · Approval-dependent: 6/10** (Instagram, LinkedIn, Threads, YouTube, TikTok, Facebook —
plus Twitter's paid tier).

## Detailed verification (per audit checklist)

1. **Authentication flow** — all ten read env/profile credentials with per-account `_<ACCT>`
   suffix overrides; verified for telegram/twitter/bluesky/discord/facebook via tests and code.
2. **Credential validation** — presence-only checks (no network probe to validate tokens before
   publish). `dispatch doctor` reports which vars are set but cannot verify them. Acceptable;
   documented behavior ("The API does not complain about targets whose env vars are unset").
3. **Token refresh** — implemented for YouTube only. LinkedIn (60-day expiry), Instagram (60-day
   Graph tokens), Threads, TikTok require manual token rotation with no docs on how expiry
   manifests (a row dead-letters as `auth:` — user must know to rotate). **DOC gap (P2).**
4. **Account-specific credentials** — `<PLATFORM>_<FIELD>_<ACCOUNT>` verified end-to-end
   (adapter `_tokens()/_creds()` fallback chains + tests).
5. **Content types** — see matrix. Notable gaps vs the task brief: no video on Twitter/X
   (v1.1 video upload not implemented), no Discord file attachments, no Bluesky video.
   These match the README (which does not claim them) — not defects.
6. **Character/file limits** — Twitter 280 (rejects, does not truncate — good), Bluesky 300
   (rejects), Telegram 4096 chunking + 1024 media caption, IG 2200, LinkedIn 3000, Threads 500,
   TikTok 2200, YouTube title 100/desc 5000, Discord 2000/embeds ≤10, Facebook feed limit.
   All verified in tests. **INFO:** Bluesky's real limit is 300 *graphemes*; `len()` counts
   codepoints — can only over-count (rejects valid emoji-heavy posts), never under-count. Safe.
7. **Platform formatting** — Telegram HTML entity/tag-aware chunking (tested); YouTube auto-#Shorts
   (tested); Twitter thread reply chaining (tested).
8. **API response parsing** — Telegram's HTTP-200-with-`ok:false` envelope handled (`_result_message_id`);
   TikTok's error envelope + `publicaly_available_post_id` string/list defensiveness; Instagram
   container polling; LinkedIn `x-restli-id` header. All tested.
9. **Rate-limit handling** — Twitter `TooManyRequests`, Bluesky `RateLimitExceeded`, and HTTP 429
   in all httpx-based adapters → `RETRYABLE` class → worker backoff. Tested.
10. **Retry behaviour** — worker-side: exponential backoff `30×2^(n-1)+jitter`, 3 attempts,
    dead-letter on `auth`/`permanent` immediately. Verified by tests + live compose run.
11. **Expired-token behaviour** — 401/403 → `auth` class → immediate dead-letter with
    "check your credentials" message. Tested (test_adapter_errors).
12. **Permission failures** — 403 → `auth` class with actionable message (Twitter Forbidden test).
13. **Duplicate publication prevention** — strongest area: every two-step adapter (Instagram
    media_publish, Threads threads_publish, TikTok post-init, Telegram multi-chunk, Twitter
    partial thread, Bluesky partial thread, LinkedIn missing-id) classifies ambiguous outcomes as
    `published` (never retried) and the worker marks rows done with `unconfirmed` webhook flag.
    14 dedicated regression tests (`test_duplicate_regressions.py`, `test_partial_publish.py`).
14. **Error messages** — classified prefixes (`auth:`, `permanent:`, `retryable:`, `published:`)
    + redaction of Telegram tokens/bearer/secret params from any user-visible string. Tested.
15. **Logging** — worker silences httpx INFO (which leaks Telegram bot tokens in URLs); comment
    documents the verified leak. Secrets redacted before storage in `last_error`.
16. **Documentation accuracy** — LinkedIn docstring/README imply `image_url` support that the
    code ignores (**DOC-3, P3**); YouTube daily quota unstated (**DOC-4, P2**); README's
    "Media upload flow" for Twitter says "media_paths applied to first tweet" — matches code.

## Approval requirements (documented, not treated as failures)

- **X/Twitter:** write access requires a paid API tier; the free tier cannot post.
- **Instagram:** Meta App Review + Instagram Business/Creator account linked to a Facebook Page.
- **Threads:** Meta App Review for `threads_content_publish`.
- **LinkedIn:** approved app with `w_member_social` (3-legged OAuth; 60-day tokens).
- **YouTube:** Google Cloud project + OAuth consent screen; ~6 Shorts/day at default quota.
- **TikTok:** Content Posting API requires app audit/approval; unverified clients are limited.
- **Facebook:** Page-scoped token via approved Meta app.

These adapters are correctly implemented against the documented APIs but **cannot be live-verified
without approvals**; the audit treats them as implemented-and-unit-tested, not "live verified".

## Findings

| ID | Severity | Finding |
|---|---|---|
| ADPT-1 | P2 | No token-refresh/expiry guidance for LinkedIn/Instagram/Threads/TikTok — dead-lettered `auth:` rows don't tell the user *which* token expired or how to rotate (error bodies do carry the platform response, partially mitigating) |
| ADPT-2 | P2 | Threads media publishes sleep 30 s (default) inside the single-threaded worker, stalling the entire queue for that duration per post (MAX 120 s) |
| DOC-3 | P3 | LinkedIn `image_url` documented in adapter docstring but never read by the code |
| DOC-4 | P2 | YouTube quota (~6 uploads/day at default 10k units) not documented in README/.env.example |
| ADPT-3 | INFO | Bluesky grapheme-vs-codepoint limit mismatch can reject valid emoji-heavy posts (fail-safe direction) |
