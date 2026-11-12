# Growth Strategy — 90 days, vanity metrics explicitly rejected

Primary metrics tracked (and nothing else promoted):
1. **Independent installs** (Homebrew installs, Docker pulls, pip downloads,
   install.sh hits) — installs, not stars.
2. **Returning users** — repeat `dispatch` usage / healthz uptime (self-reported
   via optional, privacy-preserving ping is NOT proposed; instead use
   install-source counts and GitHub issues as proxies).
3. **External contributions** — merged PRs from non-maintainers, first-time
   contributors.
4. **Meaningful feedback** — issues with reproduction steps, integrations built on
   the API (blog posts, repos that depend on the package).

Explicitly deprioritized: GitHub stars, social follower counts, launch-day spikes.

## Audience → channel → action

| Audience | What they need | Channel | 90-day action |
|---|---|---|---|
| Individual developers | "works in 10 min, no creds, no cloud" | Show HN, r/selfhosted, r/devops, PyPI | See 90-day plan §1-2 |
| Self-hosting enthusiasts | minimal footprint, backup/upgrade safety | r/selfhosted, awesome-selfhosted PR, Homelab Discord/Reddit | Compose/pip/Homebrew posts with the DMG story |
| Automation engineers | idempotency, webhooks, retry semantics | n8n community, Temporal-adjacent audiences, engineering blogs | Post the reliability engineering write-up (audit + zero-duplicate evidence) |
| Agencies and businesses | teams/approval (they have it elsewhere) | **Do not target yet** — positioning says no teams before 1.0 | Only indirect: MIT argument for agencies *embedding* it in their own tools |
| Open-source contributors | scoped issues, fast review, working setup | good-first-issues (5 live), CONTRIBUTING verified | See §4 |

## 90-day plan

### Days 1-30 — "Installability is the demo"
1. **Ship the artifact surface**: publish `open-dispatch` to PyPI (the package
   itself is pip-installable today but not under a clean name on PyPI — verify and
   claim), publish the n8n node to npm (issue #13-adjacent hygiene).
2. **One measurable launch asset**: the reliability write-up ("we SIGKILL our
   worker mid-publish and prove it can't double-post") — post to r/selfhosted +
   HN `Show HN`. Honest framing: 10 platforms, MIT, one process. Link the audit
   trail. Target: 100 Homebrew/pip installs in the first week (measurable via
   Homebrew analytics API and PyPI stats).
3. **Install-source instrumentation without privacy tradeoffs**: document how
   users self-report (a GitHub "I installed it" issue template + Homebrew/pip
   public stats). No telemetry in the product — that would contradict the
   no-telemetry positioning (README already markets "no telemetry" [VERIFIED]).
4. **Contributor funnel**: triage the 5 good-first-issues within 24h of any PR;
   add 2 more scoped issues from the P2 backlog (coverage #13, docs) so the queue
   never empties.

### Days 31-60 — "Make the first integrations visible"
1. **Dogfood campaign**: publish one public repo "open-dispatch-recipes" with 5
   copy-paste integrations (GitHub Actions cross-post on release; cron digest to
   Telegram; webhook → dispatch; AI-caption pipeline; MCP + Claude Desktop).
   Each recipe = one README GIF + one curl. This is the C-positioning proof.
2. **Second asset**: "Build your own Buffer in 100 lines" post — the recipes
   packaged as a story (HN cross-post; r/Python).
3. **Fastest-path fixes only**: take the top 2 install-breaking bugs from issues
   (install matrix means Docker/pip/Homebrew/DMG must all stay green).
4. **Contributor recognition**: a CONTRIBUTORS section + first external PR gets a
   named release-notes credit (release notes already template it).

### Days 61-90 — "Compounding surfaces"
1. **Ecosystem beats breadth**: after v0.6 lands (OpenAPI + keys + idempotency),
   publish the **skill/agent story**: an `open-dispatch` agent skill repo mirroring
   Postiz's SKILL.md play, framed as "safe agent publishing" (dry-run + quarantine
   visibility) — the differentiator Postiz's MCP does not have.
2. **One comparison page done right**: "Open Dispatch vs Postiz — which one do you
   need?" — an honest doc (this analysis, public-facing version) rather than
   FUD. It converts the AGPL question into a documented answer and is the single
   highest-conversion asset for developers already evaluating Postiz.
3. **Cross-pollination**: PR the node to n8n community nodes list; submit to
   awesome-selfhosted; offer the doctor/quick-test UX as a pattern for other
   tools (write-ups bring contributors).
4. **Review the metrics**: installs by source, external PR count, issue quality.
   Kill any channel with <10 qualified installs in 30 days; double down on
   whichever audience showed returning users (issue reopeners, recipe forks).

## What NOT to do (commitments)

- No paid ads; no star-begging; no fake launch numbers.
- No telemetry added to justify metrics (positioning: "no telemetry" is already
  marketing [VERIFIED in README feature list]).
- No "agencies" targeting before teams exist — dishonest and unsustainable.
- No platform-count arms race posts ("we support 37 platforms!") — every claim
  must survive the verified/advertising test this analysis applies.

## Leading indicators to watch weekly

- Homebrew analytics installs / PyPI downloads / Docker pulls (public sources).
- External PRs opened & merged; good-first-issue time-to-first-PR.
- Issues with repro steps (quality signal) vs drive-by bug reports.
- Forks of the recipes repo; mentions in other repos' package files
  (GitHub code search for `open-dispatch` in pyproject/requirements).
