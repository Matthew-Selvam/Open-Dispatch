# Competitive Analysis — Executive Summary

Open Dispatch (v0.5.0, MIT, Python) vs Postiz (v1.47.0, AGPL-3.0, TypeScript).
Evidence: both repositories inspected at source (Postiz @ `3b7e966`), Postiz docs
repo (`postiz-docs`), GitHub API stats at query time. Full detail in the companion
files in this directory.

## Where Open Dispatch stands — the honest sentence

Postiz is a **team scheduling product** (calendar, analytics, teams, agencies,
billing, 37 providers, 41.4k stars) that has begun bolting on agent/automation
surfaces. Open Dispatch is a **publishing engine** with 10 platforms, no analytics,
no calendar, and 20 stars — but with verified reliability engineering (fail-closed
backends, atomic claims, quarantine-never-requeue, zero duplicate claims across
benchmark levels) that Postiz does not expose or evidence anywhere. On feature
breadth and UX, Open Dispatch loses clearly. On *trustworthiness as an embedded
component*, Open Dispatch is currently the only project in the category showing its
work.

## Verified facts that anchor everything

| Claim | Evidence |
|---|---|
| Postiz requires Postgres + Redis + Temporal stack self-hosted | their own docs (migration/installation pages) + Temporal workflows in `apps/orchestrator` |
| Postiz is AGPL-3.0 | LICENSE, package.json |
| Postiz public API: keys + OAuth2 + published OpenAPI + 90 req/h create-post limit | `public.integrations.controller.ts`, `postiz-docs/public-api/` |
| Postiz MCP: 13 tools + agent skill + npm CLI/SDK | docs repo (cli/, mcp/, SKILL.md) |
| Open Dispatch: JSONL zero-infra default, 5 install methods incl. self-contained DMG | v0.5.0 verified install matrix |
| Open Dispatch: fail-closed queues, quarantine semantics, 0 duplicate claims at concurrency 1-8 on 3 live backends | AUDIT/V050/ evidence + tests |
| Open Dispatch gaps: 10 platforms, no analytics, no calendar, no versioned API contract, no API keys, no idempotency | source inspection |

## Advantages (ranked)

1. **MIT license** — real; removes the AGPL blocker for embedding in proprietary
   software. Postiz structurally cannot follow.
2. **Zero-infra operation** (JSONL default, one process) — real; decisive for
   laptop/VPS/homelab; Postiz's minimum stack is 4+ services.
3. **Demonstrated duplicate-safety and failure semantics** — real as evidence today,
   product advantage once idempotency keys + cooldown registry ship.
4. **Python-native embeddability** — potential; requires the PyPI SDK + recipes to
   become real.
5. Self-contained macOS DMG / Homebrew / pip surface — real distribution edge.

## Weaknesses that matter (ranked for the intended audience)

1. **No versioned API contract, keys, or idempotency** (Critical — the core bet,
   position C, cannot be credible without it).
2. **Platform breadth: 10 vs 28+ documented** (Important — pick developer-automatable
   platforms, don't chase 37).
3. **No analytics data at all** (Important for trust; expose data via API, do not
   out-chart Postiz).
4. **No async-acceptance verify hooks** (Important — quarantine rate on 3-4
   platforms).
5. Docs site, npm-published n8n node, SDK (Important hygiene, low complexity).
6. Team/multi-tenant features (Not worth pursuing — AGPL-SaaS territory, wrong
   audience).

## Recommendation: Position C (primary)

**"Programmable publishing infrastructure for applications, automations and AI
agents."** — with self-hosted operator-safety kept as a property, not the identity.
Position A (Buffer alternative) is an unwinnable demo race against a 41k-star
incumbent; B (self-hosted for developers) is a segment, not a differentiator, and
Postiz satisfies it too.

One-sentence pitch: *"Open Dispatch is an MIT-licensed, Python-native publishing
engine with duplicate-safe queues: embed it in your app, script it, or hand it to
an agent — it runs in one process on your own machine."*

## Roadmap spine (details + per-item complexity/dependencies in ROADMAP file)

- **v0.6.0 "The Contract"**: API keys, idempotency keys, pinned OpenAPI artifact
  (CI drift-gated), `/metrics`, signed webhooks.
- **v0.7.0 "Platform Defense"**: distributed per-account rate-limit cooldown
  registry (community feature — evaluated, not rubber-stamped: it lands here
  because it depends on v0.6 keys/metrics and is unclaimed territory in the
  entire category), async-acceptance verify hooks, 2-3 developer-automatable
  adapters (Mastodon, Reddit, +1).
- **v0.8.0 "Proof"**: post timeline/error ledger, light read-your-stats API,
  multi-worker recipe (SKIP LOCKED), docs site.
- **v0.9.0 "Ecosystem"**: PyPI client SDK (the Python-native advantage made
  real), MCP expansion with dry-run/quarantine tools ("safe agent publishing"),
  npm-published n8n node, inbound triggers.
- **v1.0.0 "Trust"**: stability contract (semver API + queue schema, upgrade
  tooling), SEC-2 fixed, 24h soak evidence, explicit non-goals (no teams/billing).

## Growth (90 days)

Installability-first: PyPI/npm artifact claiming + reliability write-up launch →
`open-dispatch-recipes` public repo with 5 copy-paste integrations → agent skill +
honest "vs Postiz — which do you need?" comparison page. Track installs, returning
users, external PRs, repro-quality issues. No telemetry, no star-chasing, no agency
targeting before teams exist.

## The final answer

**Why should a developer choose Open Dispatch over Postiz?**

Because they need publishing their *code* controls, not a scheduling website they
configure: MIT lets them embed it anywhere including proprietary systems; it runs
in one process with no Postgres/Redis/Temporal obligation; the queue semantics
(fail-closed, atomic claims, quarantine-never-requeue, idempotency) are specified,
tested, and evidenced rather than implied; and it is Python — the language their
stack, scripts, and agents already speak. Postiz is the better choice when they
want a team calendar today — the analysis says so plainly — and the comparison page
should say so, because the developer who *doesn't* need a calendar is the one this
project wins.

**What must we build to make that choice increasingly compelling?**

In order: (1) the contract — versioned OpenAPI, API keys, idempotency keys, so
code can rely on it; (2) the defense — distributed per-account rate-limit cooldown
and async-acceptance verification, so multi-account automation is safe in a way no
competitor offers; (3) the proof — post timeline, metrics, soak numbers; (4) the
ecosystem — Python SDK, agent skills with dry-run safety, published n8n node; then
(5) the 1.0 stability contract. Each item strengthens the identity; anything else
(e.g., a calendar) would spend the only non-renewable resource — maintainer time —
racing Postiz on Postiz's home ground.
