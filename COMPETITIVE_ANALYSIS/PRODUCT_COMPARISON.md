# Product Comparison — Open Dispatch vs Postiz

Date of analysis: 2026-06-11 session.
Evidence base:
- **Open Dispatch**: repository `main` (v0.5.0, tag on merge commit `c3ff2a8`), inspected directly; all capability claims below were verified in this session or in the v0.5.0 remediation work.
- **Postiz**: repository `gitroomhq/postiz-app` @ `3b7e966` ("feat: youtube fixes"), `version.txt` = **v1.47.0**, plus the public docs repo `gitroomhq/postiz-docs` (Mintlify source). Claims are tagged by evidence class.

## Evidence classes

- **[VERIFIED]** — read in source or executed in this session.
- **[ADVERTISED]** — asserted by the project itself (README/docs) but not verified in code.
- **[DOC]** — claim exists only in documentation.
- **[UNKNOWN/UNVERIFIED]** — could not be established in this session.

## Snapshot

| | Open Dispatch | Postiz |
|---|---|---|
| Version | v0.5.0 | v1.47.0 (`version.txt`) |
| License | MIT | AGPL-3.0 (package.json `license: "AGPL-3.0"`) |
| Stars / forks / open issues | 20 / — / 6 | 41,413 / 7,898 / 210 total (133 open issues at query time) |
| Languages | Python 3.11+ (FastAPI) | TypeScript (NestJS + Next.js), Node 22 |

## 1. Target audience

- **Open Dispatch** [VERIFIED]: the developer operating their own machine — `curl \| bash` install, `.env` credentials, CLI (`dispatch`), single-user profiles-as-credential-sets, health dashboard. There is no team/workspace model in the API or schema.
- **Postiz** [VERIFIED]: multi-tenant from the ground up — `Organization`, `UserOrganization`, CASL permissions (`@casl/ability`), Stripe billing/subscriptions, agencies ("customers", submitted-for-org posts), in-app notifications, streaks. Docs market a team/scheduling product ("open-source social media scheduling tool").

## 2. Product positioning

- **Open Dispatch** [VERIFIED]: "One API to dispatch your content anywhere — self-hostable cross-poster." README's own checklist markets install methods and the API surface, not a scheduling UI.
- **Postiz** [ADVERTISED/DOC]: "Open-source social media scheduling tool" with a full calendar/draft/approval UX, cloud offering, and now an agent/automation layer (CLI, MCP, agent skill, CopilotKit in-app assistant).

## 3. Architecture

- **Open Dispatch** [VERIFIED]: single Python process model. FastAPI API + one polling worker (`scheduler/worker.py`) sharing a pluggable queue (JSONL file with cross-process flock / Redis / Postgres). No external orchestrator, no message broker beyond the queue itself.
- **Postiz** [VERIFIED]: monorepo of five apps (backend, frontend, orchestrator, extension, SDK) + shared NestJS libraries. Background work is **Temporal** — one durable workflow per post (`apps/orchestrator/src/workflows/post-workflows/post.workflow.v1.0.1 … v1.1.1`), started from `posts.service.ts` (`client.workflow.start('postWorkflow…')`), with media-processing and clipping workflows too. Requires the Temporal stack (Postgres + Elasticsearch per docs) alongside Postgres + Redis/BullMQ.

## 4. Languages and frameworks

- **Open Dispatch** [VERIFIED]: Python, FastAPI, Jinja2, httpx, Pillow; pytest suite (385 tests on v0.5.0 main with live PG).
- **Postiz** [VERIFIED]: TypeScript, NestJS (backend API), Next.js (frontend), Prisma ORM (schema with **90 models**), BullMQ + ioredis, Temporal SDK, Jest. Package manager pnpm; `engines: node 22.23.4`.

## 5. API capabilities

- **Open Dispatch** [VERIFIED]: `/dispatch`, `/dispatch/bulk` (multipart), queue CRUD + retry + delete, `/campaign/{id}` status + cancel, profiles CRUD, `/media/transcode` + `/media/specs`, `/ai/adapt`, `/healthz` (API-vs-queue status). Bearer token optional (loopback default). **No published OpenAPI document** (FastAPI auto-docs exist at `/docs` [VERIFIED] but no versioned spec artifact or SDK).
- **Postiz** [VERIFIED]: a full public API under `/public/v1/*` (integrations, posts, media/uploads, video, analytics, notifications, clipping, providers) with a **published OpenAPI JSON** (`postiz-docs/public-api/openapi.json`), API-key auth (`Authorization: your-key`) **and** OAuth2 tokens for third-party apps (`pos_…`) [DOC/VERIFIED-in-controller: `public.integrations.controller.ts` handles both]. Documented rate limit: **90 req/hour on the create-post endpoint** (100 on cloud), tunable via `API_LIMIT` [DOC].

## 6. Platform integrations

- **Open Dispatch** [VERIFIED]: 10 adapters — X/Twitter, Bluesky, Instagram, Threads, LinkedIn, Telegram, YouTube, TikTok, Discord, Facebook. Each ~one self-contained file with account-suffix overrides.
- **Postiz** [VERIFIED in repo]: **36 provider files** (`libraries/nestjs-libraries/src/integrations/social/`) covering, beyond Open Dispatch's set: Reddit, Pinterest, Mastodon (+ custom instance), Lemmy, Farcaster, Nostr, VK, Medium, Dev.to, Hashnode, WordPress, Dribbble, Slack, Twitch, Kick, Google My Business, Tumblr, MeWe, Whop, Skool, Listmonk, Moltbook, Threads, TikTok Business. Docs advertise "28+" channels [DOC] — the repo actually contains more than 28 provider implementations.

## 7. Account management

- **Open Dispatch** [VERIFIED]: multiple accounts per platform via `platform:account` keys, plus "profiles" = named credential sets (swappable per post). No teams, no roles, no orgs.
- **Postiz** [VERIFIED]: organizations, users, invites, CASL policies, agencies submitting content for clients with approval flow (`submittedForOrganizationId`, `APPROVED_SUBMIT_FOR_ORDER`), API keys per org.

## 8. Scheduling

- **Open Dispatch** [VERIFIED]: ISO `scheduled_for` per row; worker polls due rows; exponential backoff on failure. No calendar UI (dashboard is a queue table), no drafts, no approval states, no recurring posts.
- **Postiz** [VERIFIED]: calendar UI with drafts/approval states; per-post `publishDate`, `delay` (minute-level staggering between posts in a group), `intervalInDays` recurring posts, batches, timezones handled at the calendar layer [VERIFIED in workflow + schema].

## 9. Queue architecture

- **Open Dispatch** [VERIFIED]: row-per-target state machine (`queued → publishing → published | failed | dead | canceled`) over JSONL/Redis/Postgres. Atomic guarded claims. v0.5.0 fail-closed backend selection. Bounded in-process concurrency (`WORKER_CONCURRENCY`, default 1).
- **Postiz** [VERIFIED]: Postgres is the state store (indexed `state`); Temporal runs the execution; BullMQ/ioredis used for auxiliary jobs. Post.state enum + `Errors` model for failure history.

## 10. Retry and failure handling

- **Open Dispatch** [VERIFIED]: classified errors (auth/permanent/retryable/published-unconfirmed), attempt counter + exponential backoff with jitter, dead-lettering, stale-claim quarantine (never auto-requeue), per-backend failure-injection tests, live-outage verification (v0.5.0 evidence).
- **Postiz** [VERIFIED]: Temporal workflow retries with activity timeouts; error classes — `refresh_token` (auto-refresh then retry), `bad_body`, `timeout` (outcome unknown → distinct "unconfirmed" path telling the user to check for duplicates), `unknown` (transient). Pending posts (async platform acceptance, e.g. TikTok/Instagram publishing) are **durably polled** via read-only status checks with an error budget — arguably the most mature single piece of failure handling in either codebase.

## 11. Rate-limit handling

- **Open Dispatch** [VERIFIED]: per-adapter classification of 429s as retryable with backoff; **no cross-account/cross-worker coordination** — two workers publishing to the same platform concurrently can each be within "their own" budget but jointly exceed the platform's. This is the known gap behind the community-suggested cooldown feature.
- **Postiz** [UNKNOWN/UNVERIFIED]: no centralized per-platform cooldown registry found in this pass. The staggering comes from UI-level defaults (delay between group posts) and Temporal's natural serialization per workflow. [DOC] nothing claims platform-limit coordination.

## 12. Authentication and security

- **Open Dispatch** [VERIFIED]: optional bearer token (empty = unauthenticated), loopback-only compose default, CORS origin checks, SSRF-validated webhooks (IP pinning), streaming-sensitive upload limits in progress (SEC-2 open P2), credentials in `.env`/profiles with 0600 file modes.
- **Postiz** [VERIFIED]: JWT sessions, per-org API keys, OAuth2 app tokens, CASL permission checks on public endpoints, throttler module; Sentry; webhooks with signatures (`Signatures` model). Multi-tenant isolation is part of the schema.

## 13. AI capabilities

- **Open Dispatch** [VERIFIED]: caption adaptation only (`/ai/adapt`; OpenRouter preferred, Ollama local, heuristic fallback). No image generation.
- **Postiz** [VERIFIED]: CopilotKit assistant embedded in the composer (textarea AI), LangGraph/LangChain agent graph, AI image generation, video generation (docs promote Agent Media), video clipping workflows ("clipping"), plus an installable agent **skill** (`npx skills add gitroomhq/postiz-agent`) and `SKILL.md` shipped in the docs repo.

## 14. MCP and agent integrations

- **Open Dispatch** [VERIFIED]: `mcp_server.py` — tools wrapping the local REST API; optional `mcp` extra; token propagation; tested in CI with zero skips. Single-server (stdio/SSE) entry point.
- **Postiz** [VERIFIED in docs + repo]: hosted/local MCP server with **13 documented tools** (integration list, schedule post, posts list, post settings, generate image, clipping, trigger helpers…), usable from Claude/ChatGPT/Cursor, plus the agent skill above. More mature surface (13 tools vs Open Dispatch's 10 (verified)).

## 15. n8n and automation

- **Open Dispatch** [VERIFIED]: community n8n node in-repo (TypeScript, built in CI) targeting its own REST API; webhook notifications on published/failed.
- **Postiz** [ADVERTISED, npm-published]: `n8n-nodes-postiz` on npm (docs link it); also third-party app integration surface (`ThirdParty`, OAuth apps) and "Plugs" (automation rules inside the product).

## 16. CLI and SDKs

- **Open Dispatch** [VERIFIED]: `dispatch` CLI ships with the package (send, queue, campaigns, quick-test, doctor, worker). No published client SDK (the CLI *is* the client).
- **Postiz** [VERIFIED in docs/npm]: `npm install -g postiz` CLI wrapping the public API, official `@postiz/node` SDK, extension (browser), and a documented public API for rolling your own.

## 17. Analytics

- **Open Dispatch** [VERIFIED]: none. No endpoint or worker path fetches post performance. This is a visible product gap vs any commercial scheduler.
- **Postiz** [VERIFIED in code]: per-post analytics pulls (`checkPostAnalytics` in the post service; analytics public API section; org activity endpoint). Depth per platform [UNKNOWN/UNVERIFIED].

## 18. Self-hosting

- **Open Dispatch** [VERIFIED]: five documented install methods (curl\|bash, pip, Homebrew tap, signed-unsigned macOS DMG that bundles its own Python runtime, Docker compose). Minimal requirements: none for JSONL; optional Redis/Postgres. Loopback-only defaults with an explicit remote-exposure runbook.
- **Postiz** [DOC]: docker-compose (now including the Temporal stack), Kubernetes/Helm, devcontainer, and a `postiz` npm wrapper image. System requirements are materially higher: Postgres **+ Redis + a Temporal stack (Temporal services + its own Postgres/Elasticsearch per the migration doc)**.

## 19. Deployment options

- **Open Dispatch** [VERIFIED]: single VPS, laptop, CI box, Raspberry-Pi-class hardware. Compose is loopback-first; a prod compose publishes zero ports.
- **Postiz** [VERIFIED]: docker/helm targets; cloud (postiz.com) is the flagship; self-host needs the full stack above.

## 20. Licensing

- **Open Dispatch** [VERIFIED]: MIT — no copyleft obligations; embeddable in proprietary products.
- **Postiz** [VERIFIED]: **AGPL-3.0** — network copyleft; commercial use inside a SaaS product you operate requires either open-sourcing your fork or a commercial agreement (they sell a cloud + presumably enterprise terms). This is Open Dispatch's cleanest structural advantage and it is real.

## 21. Documentation

- **Open Dispatch** [VERIFIED]: README + INSTALL_METHODS + SECURITY + CONTRIBUTING (verified working in v0.5.0 post-release work) + AUDIT trail (unusually deep). No docs site, no versioned API reference beyond FastAPI auto-docs.
- **Postiz** [VERIFIED]: Mintlify docs site with dedicated sections (self-hosting, providers, public API incl. OpenAPI, CLI, MCP, OAuth apps, troubleshooting). Docs are a first-class product surface.

## 22. Contributor experience

- **Open Dispatch** [VERIFIED]: CONTRIBUTING verified by execution; 5 scoped `good first issue`s with acceptance criteria; 385-test suite runs offline in ~15 s; docs-integrity tests.
- **Postiz** [VERIFIED]: CONTRIBUTING exists, ICLA/CCLA required, SonarCloud config, Jest with coverage, but the dev environment needs the Temporal stack (docs explicitly warn Windows/WSL is unsupported and community help is limited).

## 23. Community and ecosystem

- **Open Dispatch** [VERIFIED]: 20 stars, single maintainer, no third-party ecosystem yet.
- **Postiz** [VERIFIED]: 41k+ stars, 7.9k forks, npm-published SDK/CLI/n8n node, agent skill, Chrome extension, paid cloud. Ecosystem gravity is currently unmatched by any project in this niche except maybe self-hosted suite giants.

## Summary judgment

Postiz is a **product** (team scheduling SaaS, self-hostable, AGPL) with an increasingly agent-facing layer. Open Dispatch is **infrastructure** (an API-first publishing engine with unusually rigorous reliability engineering) that today ships with a minimal UI and 10 platforms. They overlap on "schedule and cross-post to platforms" and diverge on almost everything else that matters for positioning.
