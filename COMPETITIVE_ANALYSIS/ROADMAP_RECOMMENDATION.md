# Roadmap Recommendation — v0.6.0 → v1.0.0

Filter for every item (primary positioning = C, programmable publishing
infrastructure): *does it make Open Dispatch better to call from code, agents, or
pipelines?* Complexity is estimated against the current codebase (single
maintainer). Items are sequenced by dependency, not by feature- envy.

## Standing evaluation rule

The community-suggested **distributed rate-limit cooldown** is evaluated on the
same axis as everything else (see v0.7). It is genuinely unclaimed territory —
neither project has it [VERIFIED searches of both codebases] — but it depends on
infrastructure items (Redis semantics, per-account keys) that must land first, so
it does not jump the queue.

---

## v0.6.0 — "The Contract" (make the API safe to integrate against)

| # | Feature | User problem | Competitive importance | Complexity | Dependencies | Expected value | Why here |
|---|---|---|---|---|---|---|---|
| 1 | **API keys** (optional, generate/revoke via CLI + dashboard; bearer-token compatible) | Scripts share one admin token; can't scope or rotate a key an agent uses | High — Postiz has per-org keys [VERIFIED]; without this, "infrastructure" is not credible | Low-Med | — | Converts integration risk into a supported workflow | Cheapest high-value item; unblocks agent/dogfooding adoption |
| 2 | **Idempotency keys** on `/dispatch` (`Idempotency-Key` header → dedupe window) | A retried webhook/pipeline double-enqueues → double-posts | **Critical** — duplicate prevention is Open Dispatch's brand promise; Postiz offers no idempotency either | Med (needs a dedupe store keyed per backend) | queue backends | Removes the #1 integration fear | Core identity item; small surface, big trust |
| 3 | **Published OpenAPI 3.1 spec artifact** (versioned `openapi.json` in-repo, generated and asserted in CI so it can't drift) | Integrators guess request shapes; agents need schemas | High — Postiz publishes openapi.json [VERIFIED] | Low (FastAPI already emits a schema; needs pinning + CI drift test) | — | Enables SDKs + agent skills | Foundation for v0.7-0.9 items |
| 4 | **`/metrics` (Prometheus text)** — queue depth, rows by status, publish latency histogram, attempts, worker heartbeat age | Operators can't see queue health without scraping the dashboard | Med | Low | healthz context | Differentiates operator story | Fills observability gap cheaply |
| 5 | **Webhook signing hardened + documented** (`X-Open-Dispatch-Signature`, HMAC, timestamp, replay window; docs) | Automations can't trust unsigned callbacks | Med (v0.4.1 egress pinning exists; signing story incomplete [VERIFIED gap]) | Low | — | Makes the event path pipeline-grade | Small, completes the automation story |

Explicitly NOT in v0.6: analytics, calendar, new platforms, teams.

## v0.7.0 — "Platform Defense" (rate-limit coordination + adapter depth)

| # | Feature | User problem | Competitive importance | Complexity | Dependencies | Expected value | Why here |
|---|---|---|---|---|---|---|---|
| 1 | **Distributed rate-limit cooldown registry** (community feature) — per-`platform:account` cooldown state in Redis (or JSONL best-effort local); adapters *write* observed 429/`retry_after`; the worker *reads* it before claiming; campaign-level throttling per platform; documented semantics | Ten accounts of one platform across N workers jointly trip platform limits; each retries blindly and amplifies the block | High — **unclaimed in the entire category** [VERIFIED: neither codebase has it]; directly serves multi-account automation (positioning C) | Med-High: needs shared-state semantics per backend, atomic decrement/claim of the cooldown slot, tests across backends | Redis backend (exists); per-account keys (exist) | First-to-market reliability feature; strong "why Open Dispatch" story vs Postiz | After v0.6 because it needs the contract layer (per-account keys, metrics to observe it); before platform growth because 10 platforms × N accounts is where users actually hit it |
| 2 | **Async-acceptance verify hook** (optional adapter `verify(pending) → published-id`), worker polls with error budget like Postiz's pending-polling [pattern VERIFIED in their workflow] | TikTok/Instagram-style "container accepted, post pending" rows end as publish-unconfirmed | High for correctness on existing platforms | Med | — | Cuts the unconfirmed/quarantine rate on 3-4 platforms | Uses the quarantine semantics already built; deepens trust |
| 3 | **2-3 new adapters** chosen for the C audience (candidates: Mastodon — zero-OAuth app key story, Reddit — developer-heavy, Pinterest or LinkedIn Pages) | Channel breadth is the top visible gap vs 37 providers | Med (breadth matters, but breadth+UI is Postiz's race; choose developer-automatable ones) | Med each (~80 LOC + tests by design) | verify hook (for async ones) | Broadens the addressable integrations | After the cooldown registry: new adapters inherit coordinated limits from day one |

## v0.8.0 — "Proof" (observability + history + light analytics)

| # | Feature | User problem | Competitive importance | Complexity | Dependencies | Expected value | Why here |
|---|---|---|---|---|---|---|---|
| 1 | **Post timeline / error ledger** (per-row immutable events: enqueued, claimed, retried, published, quarantined) | When something misbehaves, `last_error` is the only memory | Med — no direct Postiz equivalent surfaced to API users; complements quarantine | Med (append-only store per backend) | backends | Turns "we tested it" into "I can see it" | Natural after cooldown/verify (more moving parts to observe) |
| 2 | **Read-your-stats pass** (fetch post URL/status from platforms where cheap — e.g. public metrics APIs; store in the ledger) — *light* analytics, explicitly not a dashboard | Developers want "did it land, what's the URL, is it up" not charts | Med (Postiz has analytics [VERIFIED]; we can't out-chart them — we can *expose* data) | Med-High (per-platform variance) | ledger | API-returns-data beats UI-shows-charts for C | Depends on the ledger |
| 3 | **Multi-worker deployment recipe** (PG `SKIP LOCKED` claim upgrade + docs + 3-process test in CI) | Operators scale past one worker by guesswork | Med | Med | PG backend | Makes "infrastructure" scale story honest | Rounds out reliability |
| 4 | **Docs site** (mkdocs-material, versioned, from repo docs) | Evaluators judge docs; CONTRIBUTING verified but no site | Med | Low | — | Conversion asset | By now there is enough surface to document |

## v0.9.0 — "Ecosystem" (SDKs, agents, integrations)

| # | Feature | User problem | Competitive importance | Complexity | Dependencies | Expected value | Why here |
|---|---|---|---|---|---|---|---|
| 1 | **Python client SDK** (`open-dispatch` PyPI package, typed, generated-or-thin over OpenAPI) | Python shops embed it via HTTP today | High for C (this IS the Python-native advantage made real) | Low-Med once OpenAPI is pinned (v0.6) | OpenAPI artifact | Key differentiator Postiz can't match (their SDK is Node) | Depends on v0.6 OpenAPI |
| 2 | **MCP expansion + publish dry-run tool** (list queue, verify quarantine, dry-run a post without sending, cooldown status) | Agents must be able to *see* consequences before acting | High — differentiator: Postiz's 13 tools act on their cloud; ours can expose the queue itself | Med | metrics/ledger | First-mover "safe agent publishing" | Needs v0.6 metrics + v0.8 ledger |
| 3 | **n8n node published to npm** + verified walkthrough | Node exists in-repo but unpublished [VERIFIED]; Postiz's is on npm | Med (parity, not advantage) | Low | — | Hygiene that removes an objection | Bundle with ecosystem release |
| 4 | **Idempotent webhook ingestion + inbound triggers** (accept events from other systems to create posts) | Automations need triggers, not just calls | Med | Med | idempotency (v0.6) | Completes the automation loop | After idempotency exists |

## v1.0.0 — "Trust" (stability contract, not features)

| # | Feature | Why | Complexity | Notes |
|---|---|---|---|---|
| 1 | **Stability contract**: semantic-versioned API + queue schema, deprecation policy, documented upgrade/rollback per release (already practiced in v0.5.0) | 1.0 signals "you can build on this" | Low-Med (mostly discipline + tests that pin the contract) | The 1.0 gate |
| 2 | **SEC-2 fixed properly** (streaming upload limits) + any remaining HIGH security findings closed | Security debt blocks trust | Med | Long-standing audit P2 |
| 3 | **Upgrade tooling**: `dispatch doctor --check-upgrade`, queue-file migration safety, Homebrew/DMG verification documented | Operators fear upgrades | Low-Med | Builds on install matrix |
| 4 | **Load & soak evidence** (soak test over 24h on all backends, published numbers) | v1.0 should carry measured, not aspirational, reliability claims | Med | Reuses benchmark harness |
| 5 | **Explicit non-goals in README** (no teams/billing; UI stays operator console) | 1.0 must state what it is | Low | Prevents positioning drift |

Deliberately NOT in any release through 1.0: multi-tenancy/teams, billing, calendar
UX, mobile app. These are Postiz's product; our identity is infrastructure.

## Dependency chain (why this order)

OpenAPI (v0.6) → SDK (v0.9); idempotency (v0.6) → inbound triggers (v0.9);
metrics (v0.6) → cooldown observability (v0.7) → ledger (v0.8) → agent dry-run
(v0.9); verify hook (v0.7) → light analytics (v0.8). Each release is shippable and
valuable on its own; nothing waits for another big rock.
