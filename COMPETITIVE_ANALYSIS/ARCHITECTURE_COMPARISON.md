# Architecture Comparison — Open Dispatch vs Postiz

Both inspected from current source. Postiz @ `3b7e966` (v1.47.0); Open Dispatch @ v0.5.0 `main`.
The purpose is contrast, not flattery in either direction: Postiz's architecture is the
product of headcount Open Dispatch does not have, and copying it wholesale would be fatal.
The honest question is which parts of each design serve which *positioning*.

## 1. Job scheduling

**Open Dispatch**: rows carry ISO `scheduled_for`; the worker polls `list_due(now)` and
claims atomically. Scheduling lives **in the queue**, resolution ≤ `WORKER_POLL_INTERVAL`
(default 5 s). No durable timer; a post's wait is just a row sitting in `queued`.

**Postiz**: each scheduled post group becomes a **Temporal workflow** that sleeps on a
durable timer until `publishDate` (`post.workflow.v1.1.0.ts` — `sleep(diff)`), then
publishes. Resolution is milliseconds and the "scheduler" survives process restarts
because it is *inside* the workflow, not a query over a table. The trade: every scheduled
post is a running workflow in a separate Temporal cluster with its own storage.

Verdict: for sub-second schedule precision and restart-proof waits, Temporal is
genuinely better engineering. For a single-machine self-hosted tool, it is a heavy
dependency that raises the minimum install from "one process" to "three services
plus an observability stack". Open Dispatch's polling design is adequate for its
positioning; sub-minute precision is not currently a developer requirement.

## 2. Queue processing

**Open Dispatch**: one worker process, bounded `ThreadPoolExecutor`
(`WORKER_CONCURRENCY`, default 1), claim-then-process per row; three backends
(JSONL flock / Redis WATCH / PG guarded UPDATE). Verified with zero duplicate claims
across concurrency 1–8 on live backends.

**Postiz**: the "queue" is Postgres state; execution is Temporal activities. Concurrency
is whatever the Temporal workers allow (task-queue based). BullMQ/ioredis handles
side jobs (notifications, media). There is a **versioned workflow system** (v1.0.1 …
v1.1.1 files) — workflows pinned per feature version — which is how they evolve
publishing logic without breaking in-flight posts. That is a real capability Open
Dispatch has no equivalent for, and matters only once you have long-lived
multi-day in-flight posts at scale.

## 3. Worker concurrency

**Open Dispatch**: verified in-process bound, claims inside tasks, graceful shutdown,
benchmark documented (zero duplicate claims at every level). Multi-*process* story:
JSONL is single-host by design; Postgres backend is multi-worker safe (verified with 3
competing processes); Redis is WATCH-safe. What's missing: a documented multi-worker
deployment recipe and true `SKIP LOCKED` claiming (current PG claims use guarded
UPDATE, which is correct but contended).

**Postiz**: concurrency is inherited from Temporal's worker fleet; per-post workflows
serialize per integration naturally. Their `delay` mechanism staggers posts inside a
group by minutes. Neither project has a cross-account platform-cooldown coordinator.

## 4. Rate-limit coordination

**Open Dispatch**: per-adapter 429 classification + backoff only [VERIFIED].
**Postiz**: same class of handling at activity level; UI staggering; no cooldown
registry found [UNKNOWN — searched for cooldown/rate-limit coordination, none found].

Honest note: **neither** project has the distributed rate-limit cooldown feature the
Open Dispatch community suggested. It would be *leading* in this category for both.
This is an opportunity precisely because it's unclaimed — see ROADMAP (v0.7 candidate).

## 5. Account isolation

**Open Dispatch**: accounts are `platform:account` rows and credential "profiles".
One process, one data dir; isolation is per-row `platform_key`. No concept of tenant
[VERIFIED].

**Postiz**: `Organization` is the tenant boundary throughout (90 Prisma models,
every query org-scoped, CASL on the public API). If a contributor or business needs
teams/clients, Postiz has it and Open Dispatch does not.

Verdict: do **not** build multi-tenancy to chase this — it is the AGPL SaaS's home
turf and irrelevant to Open Dispatch's intended audience (a developer, their machine,
their accounts).

## 6. Platform adapter design

**Open Dispatch** [VERIFIED]: one self-contained Python module per platform exposing
`publish(unit, account) -> (ok, post_id, err)`; classified error vocabulary
(`auth/permanent/retryable/published`) consumed by the worker; account suffixes; ~80 LOC
per adapter by design; adapters tested offline with mocked HTTP.

**Postiz** [VERIFIED]: 36 provider TS files implementing a shared
`SocialIntegration` interface (validate, post, analytics hooks, refresh token support,
pending-check hooks for async platform acceptance). The pending-polling hooks
(`checkPostStatus`, `finalizePost`) are more advanced than Open Dispatch's
publish-unconfirmed vocabulary: they let a *provider* drive durable async completion.

Verdict: Open Dispatch's model is simpler to extend (this is genuine — a contributor
can add a platform without understanding Temporal); Postiz's is richer where platforms
have async acceptance semantics (TikTok ingestion, Instagram containers). If Open
Dispatch pursues more platforms, a light "verify" hook (read-only status check) would
capture most of the value without the workflow machinery.

## 7. Database architecture

**Open Dispatch**: zero-schema-by-default (JSONL), or one table (PG) / three key types
(Redis). Migrations: none needed [VERIFIED].

**Postiz**: Prisma, 90 models, `db push` migrations, Postgres-only. Rich domain
(organizations, subscriptions, comments, signatures, errors, notifications, credits…).

Verdict: incomparable on purpose. Open Dispatch's minimalism is a feature for its
audience; the cost is no history model (no post timeline, no error ledger beyond
`last_error`).

## 8. API boundaries

**Open Dispatch**: one FastAPI app; queue state IS the API response; bearer token
optional; loopback default [VERIFIED]. No versioned public contract, no OpenAPI
artifact, no API keys, no idempotency keys [VERIFIED gaps].

**Postiz**: public API (`/public/v1`) is a *separate* boundary from the app API, with
API keys per org, OAuth2 `pos_` tokens for third-party apps, OpenAPI JSON published,
documented 90 req/h create-post limit [VERIFIED controller + DOC limits].

Verdict: this is the single largest architectural gap relative to the recommended
positioning (see PRODUCT_POSITIONING): Open Dispatch is API-*first* in spirit but not in
contract. A machine cannot safely integrate against an API that has no versioned
document and no idempotency guarantee.

## 9. Authentication

**Open Dispatch**: optional bearer token; loopback default; no multi-user [VERIFIED].
**Postiz**: JWT sessions, org API keys, OAuth2 for apps, CASL policies, throttler
[VERIFIED].

## 10. Failure recovery

**Open Dispatch**: stale-claim quarantine (never auto-requeue — verified live with
SIGKILL), fail-closed backend selection with actionable `QueueBackendError`, JSONL
corrupt-line preservation, deterministic recovery after outages, `/healthz`
API-vs-queue distinction [VERIFIED, v0.5.0 evidence + tests].

**Postiz**: Temporal activity retries, token-refresh-and-retry, timeout ⇒
outcome-unknown ⇒ distinct "unconfirmed" marking with user notification, durable
pending-polling with interrupted-attempt detection [VERIFIED in workflow code]. In-app
notifications on failures.

Verdict: Postiz's pending-polling is the more complete *user-facing* failure story.
Open Dispatch's fail-closed/quarantine story is the more verifiable *operator* story.
They are complementary; Open Dispatch's is a differentiator in the self-hosted
reliability niche it should own.

## 11. Observability

**Open Dispatch**: `/healthz` (JSON: version, uptime, backend, worker heartbeat,
queue counts, recent errors), HTML dashboard, structured logs with credential
redaction [VERIFIED]. No metrics endpoint, no traces.

**Postiz**: Sentry integration, admin stats service, monitor controller
[VERIFIED]. Temporal's own UI is part of the deployment's observability.

## Net architectural assessment

1. Postiz's Temporal-based design is the right call *for a multi-tenant product* and
   an over-commitment *for a single-binary self-hosted tool*. Its minimum deployment
   (Postgres + Redis + Temporal + Elasticsearch, per their own migration docs) is
   precisely what Open Dispatch's audience refuses to run.
2. Open Dispatch's architecture is aligned with its recommended positioning (program-
   mable publishing infrastructure) **except** at the API boundary (no versioned
   contract/keys/idempotency) and in platform breadth.
3. Do not copy: Temporal, multi-tenancy, Stripe, Next.js UI, 90-model domain. Do
   selectively adopt: versioned public API contract; a read-only "verify" hook for
   async-platform acceptance; an error ledger (post timeline) if post history becomes
   product.
