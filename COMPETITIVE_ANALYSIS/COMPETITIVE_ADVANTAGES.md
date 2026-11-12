# Competitive Advantages — what Open Dispatch genuinely has

Classification for each: **REAL** (differentiating today, evidenced),
**POTENTIAL** (advantage if executed), **NOT DIFFERENTIATING** (nice, but doesn't
move a developer's choice).

## 1. MIT vs AGPL-3.0 — REAL

Postiz is AGPL-3.0 [VERIFIED: LICENSE + package.json]. Practical consequences:
- A company cannot embed Postiz inside a non-open SaaS/network product without
  negotiating with the vendor (AGPL §13 network copyleft).
- Forks that operate Postiz as a service must release their source.
Open Dispatch's MIT allows embedding in proprietary products, CI pipelines, agent
frameworks, appliances. For the recommended positioning (publishing infrastructure
other software calls), licensing is a *selection criterion*, not a checkbox. This is
the strongest structural advantage and it compounds with the Python-native story
("drop it next to your Python stack").

Honest caveat: licensing alone never wins — it only removes a blocker. It converts
Postiz-wary integrators into evaluators; the product must then hold them.

## 2. Python-native developer experience — POTENTIAL (high value, must be executed)

- For a Python shop, Open Dispatch is `pip install` + `import`-able modules, the
  worker is a class you can call from tests, adapters are plain functions with
  mocked-HTTP tests [VERIFIED].
- Postiz requires TypeScript/NestJS literacy to extend, Node 22, pnpm, Temporal
  concepts [VERIFIED].
This becomes REAL only if the Python-native surface is made excellent: a published
`open-dispatch` client library, typed schemas, example recipes, and adapters that are
trivially unit-testable. Today the packaging is right; the *library* experience
(programmatic embedding) is barely started.

## 3. Multiple queue backends incl. zero-infra JSONL — REAL (for the niche)

[VERIFIED] JSONL default runs with no Postgres/Redis; Redis/Postgres are opt-in with
fail-closed semantics. Postiz *requires* Postgres + Redis + Temporal stack [DOC].
For the "my $5 VPS / my laptop / my homelab" audience this is decisive — the
difference between a 60-second install and an afternoon. Verified install matrix
v0.5.0: curl|bash, pip, Homebrew, self-contained DMG, Docker.

Caveat: JSONL's growth without compaction (QUEUE-3, P2 open) will erode this if the
queue file becomes the bottleneck; bounded concurrency already plateaus at ~4 slots
on JSONL (flock contention) [MEASURED].

## 4. Self-hosting flexibility — REAL

The DMG that bundles its own Python runtime (runs on a Mac with zero Python
installed, verified by relocation test), Homebrew tap, single-binary-ish pip install,
and Docker compose that *doesn't* publish anything by default — this combination has
no Postiz equivalent. Postiz's own docs warn Windows/WSL is unsupported and limit
community help [DOC].

## 5. CLI — POTENTIAL

`dispatch` CLI is shipped, tested, and does send/queue/campaign/doctor [VERIFIED].
Postiz now has an npm CLI too [VERIFIED docs]. So CLI alone is NOT DIFFERENTIATING —
it's table stakes Postiz has matched. It becomes an advantage only as the *primary*
interface for agent/automation workflows (see positioning C), where Open Dispatch's
`quick-test` and `doctor` (install diagnostics) are nicer than Postiz's key-reveal
flow.

## 6. MCP server — POTENTIAL (parity today, differentiation possible)

Both have MCP. Postiz: 13 tools, hosted+local, agent skill repo [VERIFIED docs].
Open Dispatch: 10 tools (verified: 10 `@mcp.tool` functions — health, queue list, send/dispatch, retry, profiles, adapt, media, campaign, dry-run-adjacent) over the local API, CI-tested, token propagation [VERIFIED].
Open Dispatch is behind on tool count, ahead on "runs where the data lives"
(localhost, no cloud account). To differentiate: tools must expose what Postiz's
cannot *in a self-hosted zero-trust context* — e.g. dry-run publishing, quarantine
verification, per-account cooldown status. Postiz's MCP talks to their cloud-shaped
API; ours could talk to the queue itself.

## 7. n8n — NOT DIFFERENTIATING (today)

Both ship n8n nodes [VERIFIED Open Dispatch repo / Postiz npm]. Postiz's is published
to npm with a video walkthrough [ADVERTISED]. Open Dispatch's is in-repo, unpublished
to npm. Publishing it is hygiene, not advantage.

## 8. API-first publishing — POTENTIAL (the core bet, currently under-built)

The API exists (dispatch/bulk, campaigns, profiles, media, AI adapt) [VERIFIED] but
lacks the contract layer that makes "infrastructure" credible: versioned OpenAPI,
API keys, idempotency keys, rate limits, published client SDK. Postiz has all five
[VERIFIED]. This is the most important potential advantage: it is what the whole
positioning C (see PRODUCT_POSITIONING) stands on.

## 9. Reliability engineering — REAL (as evidence, growing into advantage)

No competitor in this niche publishes their defect backlog, fault-injection tests,
and live-outage scenarios [VERIFIED: AUDIT/, 385 tests, quarantine + fail-closed +
zero duplicate claims benchmarks]. For an audience of automation engineers who have
been burned by "it posted twice" bugs, *demonstrated* duplicate-prevention and
failure semantics are a real marketing asset — no one else in the category shows
their work. It is REAL as evidence today; it becomes a product advantage when the
semantics (idempotency, cooldown registry, verify hooks) are built.

## 10. Single binary/process operation — REAL

One process, no orchestrator, no message-broker infra. `python -m uvicorn` +
`python -m scheduler.worker` on one box [VERIFIED]. For homelab/small-VPS
self-hosters this beats Postiz's four-service minimum on every axis that matters to
them (memory, backups, upgrade risk).

## Deliberate non-advantages (don't market these)

- 385 tests / audit trail: proves quality to evaluators, but is not a *product*
  capability — use it as trust-building collateral, not as a headline feature.
- Health dashboard: Postiz has in-app notifications and admin stats; ours is
  operator-grade but not comparable as UX.
