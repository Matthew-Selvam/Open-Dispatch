# Product Positioning — evaluation and recommendation

Three candidate identities evaluated against evidence, then one recommendation with
a single primary identity.

## Position A — "Open-source alternative to Buffer and Hootsuite"

- Postiz has already claimed this mindshare: 41.4k stars, "open-source social media
  scheduling tool", calendar UI, 28-37 channels, analytics, team features, a paid
  cloud [VERIFIED]. Matching this means building the calendar, drafts/approvals,
  analytics, and ~25 more platform adapters — a multi-year UI-heavy race against a
  project with ~10× the contributor base.
- Open Dispatch has no calendar UI, no analytics, 10 platforms [VERIFIED]. As a
  "Buffer alternative" it loses the demo on sight.
- Verdict: **REJECT as primary.** Unwinnable race, wrong differentiator, and every
  hour spent on it is an hour not spent on the identity where Open Dispatch can be
  first.

## Position B — "Self-hosted social media publishing platform for developers"

- Partially true today: five install methods, loopback defaults, operator-grade
  health, minimal UI [VERIFIED].
- But Postiz is *also* self-hosted and developer-friendly enough (docker-compose,
  helm, public API). When both are self-hosted, the developer compares channel
  counts and UI polish — Postiz's ground.
- Verdict: **REJECT as primary; keep as property, not identity.** Self-hosting
  flexibility is a distribution advantage (see COMPETITIVE_ADVANTAGES §3-4), not a
  positioning. "Platform for developers" is a segment, not a reason to choose.

## Position C — "Programmable publishing infrastructure for applications, automations and AI agents" ✅

- What it means concretely: Open Dispatch is the thing your *code* talks to — a
  library/process you embed, script, or agent-drive — rather than a website you
  configure. The queue is the product; the UI is an operator console.
- Evidence this is already directionally true: the deepest features are all
  programmatic (fail-closed backends, atomic claims, quarantine semantics, campaign
  API, webhook events, MCP); the weakest are all human-facing (no calendar, no
  analytics) [VERIFIED].
- Evidence the market is moving this way: Postiz just built an agent skill, MCP
  server, CLI, and "Agent Media" promo — they are *adjacent* to C via their cloud
  API, but their core remains a UI product and their AGPL + cloud-account shape
  conflicts with pure infrastructure use [VERIFIED].
- No credible competitor currently owns "MIT-licensed, Python-native, zero-infra,
  duplicate-safe publishing engine you embed in your own stack".
- Verdict: **ADOPT as primary.**

## Recommendation

**Primary identity: C — programmable publishing infrastructure.**
**Shadow identity (inherited, not marketed as the identity): B — the most
operator-safe way to self-host it.**

Every roadmap item must be judged by one question: *does it make Open Dispatch
better to call from code, agents, or pipelines?* UI work is permitted only as
operator console for C.

## The one-sentence pitch

> "Open Dispatch is an MIT-licensed, Python-native publishing engine with
> duplicate-safe queues: embed it in your app, script it, or hand it to an agent —
> it runs in one process on your own machine."

## What this positioning explicitly gives up

- Non-technical users who want a Buffer-like calendar (Postiz serves them better).
- Teams/agencies needing multi-tenant approval flows (Postiz serves them).
- Anyone requiring per-post analytics on day one (gap — roadmap v0.8, see below).

## What it refuses to do (and why)

- Do not rebrand the README as a "Buffer alternative" — it forfeits the licensing
  and infra argument and enters the demo race.
- Do not add teams/billing — that is AGPL-SaaS territory; MIT infrastructure
  should stay single-tenant until someone *pays* for tenancy.
