# v0.5.0 Release Readiness

Date: 2026-06-10. Branch: `release/v0.5.0-hardening` (pushed).
Verdict: **READY FOR RELEASE-CANDIDATE APPROVAL** — nothing is published; the
artifacts below exist locally and the release sequence requires explicit approval.

## Version consistency

| Surface | Version | Note |
|---|---|---|
| `pyproject.toml` | 0.5.0 | package metadata; wheel built and verified |
| `api/app.py` fallback | 0.5.0 | used by source/bundle installs (verified in relocated DMG app) |
| `install.sh` default | v0.5.0 | effective after merge to main + tag |
| `scripts/make-dmg.sh` default | 0.5.0 | `--source-ref` allows RC builds pre-tag |
| README / INSTALL_METHODS DMG refs | 0.5.0 | |
| `Formula/open-dispatch.rb` | **still 0.4.1 — intentionally** | sha256 must be computed from the real v0.5.0 tag tarball; impossible before the tag exists. Post-approval step (see runbook). |
| Local RC DMG | `dist/Open-Dispatch-0.5.0.dmg` (92 MB) | built from the release branch; **not published** |
| Healthz in relocated RC DMG app | reports `0.5.0` | verified after the staging-contamination fix |

## Build reproducibility

- Wheel: built in a clean venv (`python -m build --wheel`); metadata verified
  (`Provides-Extra: mcp`, core modules present).
- DMG: built twice from the branch; second build's relocated app verified
  serving `0.5.0` (first build exposed the staging-contamination defect, now
  fixed and regression-prone step cleaned).
- Docker: image built from this branch and booted twice (smoke + persistence).

## Installation verification matrix (executed this session)

| Method | Verification | Result |
|---|---|---|
| curl \| bash (release branch) | fresh install into temp prefix; server boots; `/healthz` 200; `dispatch doctor` | PASS |
| Docker (fresh build) | compose build + boot + enqueue + restart persistence | PASS |
| Docker compose defaults | loopback-only binding verified at host level; redis unpublished | PASS |
| macOS DMG (RC, unsigned) | relocated app serves `/healthz` 0.5.0 | PASS |
| Homebrew | tap intentionally at 0.4.1; upgrade path verified for 0.4.1 in the v0.4.1 session; v0.5.0 formula sha is a post-approval step | PENDING approval |
| pip base (no extras) | clean venv: core imports, `mcp_server` exit-1 hint, wheel metadata | PASS |
| pip `[mcp,test]` | clean venv: 14/14 client-auth tests, 0 skips | PASS |

## CI status

- Workflow updated: base job (matrix 3.11/3.12) + new MCP job (clean env, zero
  security-test skips) + n8n + landing + docker smoke. YAML validated locally.
- **A CI run against the pushed branch has not been observed yet** — the workflow
  triggers on push to `main` / PRs to `main`. This is expected pre-merge; the
  first CI observation will happen on the release PR. Marked as the one
  open verification item for release approval.

## Dependency pinning

- `requirements.txt` uses lower-bound pins (unchanged from v0.4.1); no new
  runtime dependencies were added by the P1 remediations. `functools` (stdlib)
  only. The `mcp` extra (`mcp>=1.0`) and `redis`/`postgres` extras unchanged.

## Rollback instructions

- **Tag/artifacts**: do not delete the published v0.4.1 release; if v0.5.0 must
  be withdrawn, mark the GitHub release "pre-release" and revert `main` to
  `9e24ca2` (the last pre-hardening docs commit). `install.sh` default reverts
  with it.
- **Homebrew**: keep the previous formula revision in the tap history; a
  `brew install open-dispatch@0.4.1`-style pin is not supported by the tap
  layout, so rollback = re-point the formula file at the v0.4.1 URL/sha and
  commit to the tap.
- **Docker users**: pin image digests (none are published yet for v0.5.0 —
  nothing to roll back until an image is pushed post-approval).
- **Data**: no schema or queue-format changes in v0.5.0; queue data from
  v0.4.1 (JSONL/Redis/PG) is read as-is. Rollback of the *code* is safe with
  data in place (the new `queue.jsonl.corrupt` sidecar file is ignored by
  v0.4.1 readers).

## Known limitations (documented, accepted)

1. API remains unauthenticated when `OPEN_DISPATCH_API_TOKEN` is unset —
   mitigated by the loopback default; remote exposure requires token + proxy.
2. SEC-2 (buffered request bodies before size checks) — P2, open; proxy body
   limits are the interim mitigation.
3. API rate limiting — none; reverse-proxy rate limits recommended.
4. JSONL compaction (QUEUE-3, P2) — queue file grows with history.
5. Redis durability — without AOF/RDB persistence a Redis restart loses
   queued rows (documented; compose ships `--appendonly yes`).
6. Worker concurrency within one batch does not guarantee completion order.
7. Benchmark numbers are local + synthetic; not production-API predictions.

## Release runbook (requires explicit approval; NOT executed)

1. Merge `release/v0.5.0-hardening` → `main` (PR; observe CI incl. the new MCP job).
2. Tag `v0.5.0` on the merge commit; push the tag.
3. Compute the tag tarball sha256 → update `Formula/open-dispatch.rb`
   (url, sha256, version) → commit + push to `main` and the tap repo.
4. Build the final DMG from the tag (`make-dmg.sh --version 0.5.0`); verify the
   relocated app reports 0.5.0; upload to the GitHub release with
   `AUDIT/V050/RELEASE_NOTES_DRAFT.md` as the body.
5. Optionally rebuild the DMG in CI (CI-3, P2, open — still manual).
6. Do NOT overwrite v0.4.1 or any existing tag (rule 13).
