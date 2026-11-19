# Credential rotation and recovery

Use this guide when a platform credential expires, is revoked, or may have
been exposed. Open-Dispatch does not renew most platform credentials for you.
Obtain a replacement through that platform's official developer settings or
OAuth flow, update the credential source below, then verify publishing with a
small, intentional post.

## 1. Replace the credential

Open-Dispatch can read credentials from environment variables or named
profiles. Replace only the affected platform/account values:

- **Environment:** update the relevant variables in `.env` (or the service's
  environment). Restart the API and worker processes that load that file; they
  read `.env` at startup.
- **Named profile:** edit that profile in the dashboard. Profile credentials
  are read for each dispatch, so a profile update takes effect without a
  process restart. The profile store is plain JSON at
  `$OPEN_DISPATCH_DATA/profiles.json`; protect the data directory and backups.
- **Account-specific environment values:** for a target such as `twitter:work`,
  set the supported variable with the account suffix, such as
  `TWITTER_ACCESS_TOKEN_WORK`. An account-specific value takes precedence over
  the global value. See [`.env.example`](../.env.example) for the exact
  variables.

Never paste credentials into issues, logs, screenshots, or commit them to the
repository. If a credential may have leaked, revoke it at the provider before
or immediately after replacing it.

## 2. Provider credentials

The adapter's environment variable names are listed for each platform. Account
suffixes may be used where the adapter supports them; keep shared app/client
credentials at the global level unless the adapter's profile map supports
overrides.

| Platform | Credential variables | Replacement / provider guidance |
| --- | --- | --- |
| Telegram | `TELEGRAM_BOT_TOKEN`; `TELEGRAM_CHAT_ID` (and optional `TELEGRAM_CHAT_ID_<ACCOUNT>`) | Use [@BotFather](https://core.telegram.org/bots/tutorial#obtain-your-bot-token) to manage or replace the bot token. Verify the bot still has access to the target chat/channel. |
| Twitter / X | `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET` | This adapter uses Tweepy with OAuth 1.0a user credentials. Regenerate/re-authorize the app's user credentials in the [X developer portal](https://developer.x.com/en/portal/dashboard); replace the matching values together and confirm the app still has write access. |
| Instagram | `IG_USER_ID`, `IG_TOKEN` | Obtain a token for the Instagram account using the [Instagram Platform documentation](https://developers.facebook.com/docs/instagram-platform/). Confirm the app, account type, permissions, and token flow match the API product used by this installation; do not assume every Meta token has the same lifetime. |
| Bluesky | `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` | Create a replacement app password in [Bluesky app password settings](https://bsky.app/settings/app-passwords), then revoke the old one there. Use an app password, not the account's main password. |
| LinkedIn | `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_URN` | Reauthorize through the LinkedIn app's OAuth flow with the required `w_member_social` permission. Follow [LinkedIn's access-token guidance](https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens); refresh-token availability depends on the app's eligibility. Keep the author URN for the same member or organization. |
| Threads | `THREADS_USER_ID`, `THREADS_ACCESS_TOKEN` | Obtain a replacement with the required `threads_basic` and `threads_content_publish` permissions using [Threads API token guidance](https://developers.facebook.com/docs/threads/get-started/long-lived-tokens/). This adapter does not refresh the token automatically. |
| YouTube | `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | Reauthorize the Google account with the YouTube upload scope and replace the refresh token if it was revoked or invalidated. The adapter exchanges the refresh token for a short-lived access token during each upload. See [YouTube OAuth documentation](https://developers.google.com/youtube/data/guides/authentication). |
| TikTok | `TIKTOK_ACCESS_TOKEN` | Reauthorize the user through the app's TikTok OAuth flow with `video.publish`, then replace the token. The adapter does not refresh it automatically. See [TikTok user access-token management](https://developers.tiktok.com/docs/en/oauth-user-access-token-management). |
| Facebook Pages | `FACEBOOK_PAGE_ID`, `FACEBOOK_ACCESS_TOKEN` | Generate a replacement Page token with the required Page permissions using the app's configured Meta login flow. Check the token's validity and expiry with Meta's [Access Token Debugger API](https://developers.facebook.com/docs/graph-api/reference/debug_token/). Token type and expiry depend on how it was issued. |
| Discord | `DISCORD_WEBHOOK_URL` (and optional `DISCORD_WEBHOOK_URL_<ACCOUNT>`) | Create a replacement webhook in the channel's Integrations settings and update the full webhook URL. Treat that URL as a secret: anyone who has it can post to the channel. See [Discord webhook guidance](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks). |

### Token lifetimes

Lifetimes depend on the token type, the app's configuration, and how the token
was issued. Confirm against the provider's current documentation before you
plan a rotation schedule.

- **TikTok user access token:** valid for 2 hours; its refresh token is valid
  for 180 days. TikTok rotates the refresh token on each successful refresh, so
  the latest value must replace the previous one. This adapter stores only
  `TIKTOK_ACCESS_TOKEN` and does not refresh it automatically. Open-Dispatch
  cannot renew TikTok credentials today; the operator must replace the access
  token when it expires unless a separate process refreshes it and securely
  updates the stored token. See TikTok's [user access-token management
  documentation](https://developers.tiktok.com/docs/en/oauth-user-access-token-management).
- **LinkedIn access token:** documented as valid for 60 days. A programmatic
  refresh token, where the app is eligible for one, is documented as valid for
  365 days from the original authorization. See
  [LinkedIn's programmatic refresh token guidance](https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens).
- **Threads long-lived token:** documented as valid for 60 days. A refresh resets
  the 60-day period, and a token that expires cannot be refreshed. See
  [Threads long-lived access tokens](https://developers.facebook.com/docs/threads/get-started/long-lived-tokens/).
- **Google (YouTube) refresh token:** if the external OAuth consent screen is
  left in **Testing** status, refresh tokens expire after 7 days. The exception
  for identity-only scopes does not apply to YouTube uploads. In **Production**,
  refresh tokens can still be revoked and may expire after six months without
  use. See Google's [OAuth 2.0 refresh-token expiration
  rules](https://developers.google.com/identity/protocols/oauth2#expiration).
- **Facebook Page and Instagram tokens:** lifetime depends on how the token was
  issued. Long-lived user tokens are documented as lasting about 60 days, and
  Page tokens derived from them may differ. Check the token's `expires_at` with
  the [Access Token Debugger API](https://developers.facebook.com/docs/graph-api/reference/debug_token/)
  instead of assuming a duration.
- **Twitter / X, Bluesky, Telegram, and Discord:** this guide does not record a
  timed expiry for these credentials. They remain valid until revoked or
  regenerated, so follow the provider link in the table above.

## 3. Recover failed queue rows safely

Replacing a credential does not automatically retry rows already marked
`dead`. The worker classifies explicit `auth:` and `permanent:` errors as
non-retryable and dead-letters those rows immediately. Other failures, such as
rate limits and many server/network errors, are retried with backoff up to
`WORKER_MAX_ATTEMPTS` (default `3`). Missing-credential messages are not
uniformly tagged `auth:`, so use the recorded error and row status rather than
assuming every credential problem has the same classification.

1. In the health dashboard, inspect the failed row's platform, account,
   attempts, and `last_error`. Correct the credential and restart the
   environment-configured services if applicable.
2. Before retrying, check the destination account to see whether the post was
   already created. Some adapters can publish part of a multi-part post, and
   some ambiguous outcomes are deliberately marked `published:` to prevent an
   automatic duplicate. A stale `publishing` row is quarantined for the same
   reason; verify its outcome on the platform first.
3. If the post did **not** go out and the credential is fixed, manually retry
   the row with the dashboard's **Retry** action, or with the API endpoint
   `POST /queue/{row_id}/retry` (send the bearer token when
   `OPEN_DISPATCH_API_TOKEN` is set). The `dispatch queue` CLI only lists rows.
   Do not retry a row whose post is already live.
4. Watch the health dashboard or worker logs for the new result. A successful
   retry marks the row published; another authentication failure will need
   further credential or permission investigation.

The `auth:` prefix is an adapter classification, not a guarantee that every
provider reports expired credentials as HTTP 401/403. For example, OAuth
providers may return other status codes for revoked refresh credentials.
Review the full (redacted) error and the provider's current app permissions.

## Related configuration

`OPEN_DISPATCH_API_TOKEN` protects Open-Dispatch's own API; it is separate from
platform publishing credentials. Rotate it in the API and client/service
configuration together, then restart those processes. `OPENROUTER_API_KEY` is
optional for AI caption generation and is not needed to publish posts. Manage
it in OpenRouter's [API key settings](https://openrouter.ai/settings/keys).
