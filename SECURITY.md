# Security Policy

## Supported versions

The latest tagged release receives security patches. Older releases do not.

| Version | Supported |
| ------- | --------- |
| 0.4.x   | ✅ Yes    |
| 0.3.x   | ❌ Upgrade to 0.4.x |
| 0.2.x   | ❌ Upgrade to 0.4.x |
| < 0.2   | ❌ Upgrade to 0.4.x |

We're pre-1.0 — patch releases ship as new minor versions until we cut 1.0.

## Reporting a vulnerability

**Don't open a public GitHub issue.**

Send vulnerability reports privately via one of:

1. **GitHub private security advisories**: https://github.com/Matthew-Selvam/Open-Dispatch/security/advisories/new
   (preferred — keeps everything in-platform and gives us a private discussion channel)
2. **Direct email**: the maintainer email in the `pyproject.toml` author field.

Please include:

- A description of the vulnerability + the impact
- Steps to reproduce (curl invocations / config / minimal repro repo are gold)
- The version / commit SHA you tested against
- Whether you've already disclosed this to anyone else

You'll get an acknowledgement within **3 business days**. We'll work with you on a fix and a coordinated disclosure timeline (typically 30–90 days depending on severity).

## What counts as a vulnerability

In scope:

- Authentication or authorization bypass against the `/admin/*` style routes once those exist
- SSRF via webhook URLs, oEmbed fetches, image URLs (instagram_post.image_url, etc.)
- Injection (SQL/NoSQL/template) via any user-supplied input
- Path traversal via `video_path`, `photo_path`, image upload paths
- Secret leakage via logs, error pages, or HTTP responses
- Privilege escalation across accounts via target string manipulation
- Denial-of-service via crafted ContentUnits / images

Out of scope:

- Findings that require root on the host running Open-Dispatch (you already lost)
- Rate limiting concerns (this is a self-host tool; rate limiting is your reverse proxy's job)
- Missing CSP / HSTS headers on the API itself (front it with a real reverse proxy in prod)
- Self-XSS in the dashboard composer (the dashboard is single-user trusted)
- Brute-forcing the *external* platforms (Twitter, IG, etc.) — that's their problem

## Third-party adapter backends

Some adapters can be switched to an alternative backend (e.g. `TWITTER_BACKEND=xquik`). These are **opt-in** and carry a different trust model from the default direct-API path:

- Your tweet content and API key are sent to a third-party server, not just to the platform.
- Open-Dispatch has no control over that third party's security posture, uptime, or data-retention policy.
- A compromise of the third-party service could expose credentials or allow unauthorized posting.

**Mitigations if you use an alternative backend:**

1. Create a dedicated, scoped API key for Open-Dispatch and rotate it on a schedule.
2. Limit that key's OAuth scopes to write-only / no read-DM where the platform allows it.
3. Read the third party's privacy policy before enabling.
4. Disable the alternative backend (`unset TWITTER_BACKEND`) if you no longer need it.

These backends are in scope for SSRF and credential-leakage reports — if you find the alternative-backend path sending data somewhere unexpected, report it.

## Threat model — what Open-Dispatch assumes

Open-Dispatch is designed for **trusted self-hosting**. It assumes:

1. The deployer controls the network it runs on (or fronts it with proper auth)
2. The platform credentials in `.env` are trusted to the deployer
3. Webhooks fired from the worker hit URLs the deployer controls
4. Only authorized humans + automations can reach the API

If you're exposing Open-Dispatch directly to the internet without auth in front of it, you're inviting trouble — that's not a vulnerability in Open-Dispatch, that's a deployment mistake. Put it behind Cloudflare Access, Tailscale, oauth2-proxy, or your reverse proxy's basic auth. The Open-Dispatch credential UI in n8n already supports a bearer-token header for exactly this use case.

## What we will NOT do

- Pay bug bounties (we're MIT — sorry, no budget)
- Sue researchers who follow this policy in good faith
- Disclose your contact details without permission

## Hall of fame

Anyone who reports a valid vulnerability via the channel above (and consents to being credited) will be listed here.

_— maintainers_
