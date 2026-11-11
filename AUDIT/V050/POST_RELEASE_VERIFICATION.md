# v0.5.0 Post-Release Verification

Release executed 2026-11-11 per the approved runbook
(`AUDIT/V050/RELEASE_READINESS.md`). Every check below records the actual
command and result. No release-critical check failed; two CI-only test
environment issues were found during pre-publication CI (see §2) and fixed
before merge — neither was bypassed or concealed.

## 1. Pre-publication checks

| Check | Command / method | Result |
|---|---|---|
| Release commit + clean tree | `git branch --show-current` / `git status --short` (excluding pre-existing build artifacts: `build/lib`, `dist/`, `macos-app/.build`, `graphify-out/`) | branch `release/v0.5.0-hardening` @ `9b64cbe`; dirty-excluding-artifacts = **0** |
| Final CI results | PR #9 (`gh pr checks 9`) | First run: Docker/GitGuardian/Landing/**MCP job**/n8n pass; Python 3.11+3.12 **fail** (see §2). After fix: **all 7 checks pass** |
| Release DMG contains v0.5.0 server | extracted `.app` → `grep 'VERSION =' server/api/app.py` → `VERSION = "0.5.0"`; relocated app `/healthz` → `version: 0.5.0` | **PASS** |
| Homebrew formula SHA | `curl` tag tarball → `shasum -a 256` → `68edd8797ee49b365c9a9c2f5f47ce4784213bc508c91f71b18e6650bd5061b0`; tarball contents verified (`pyproject` 0.5.0, app fallback 0.5.0); formula updated; **independent verification** = Homebrew's own sha check during `brew upgrade` succeeded | **PASS** |
| Release notes / version consistency / upgrade / rollback | `AUDIT/V050/RELEASE_NOTES_DRAFT.md` reviewed; version surfaces (pyproject, app fallback, install.sh, make-dmg, README, INSTALL_METHODS) all 0.5.0; upgrade + rollback sections in `RELEASE_READINESS.md` | **PASS** |

## 2. CI failure found and fixed before merge (not bypassed)

First CI run on PR #9 failed the Python 3.11/3.12 jobs with two
CI-environment-only issues in the new tests:

1. `tests/test_compose_security.py` — `docker compose config` requires the
   compose-level `env_file: .env`, which a bare CI checkout does not have.
   Fix: module-scoped fixture creates an **empty** `.env` only when missing
   and removes it on teardown (a real operator `.env` is never touched).
2. `tests/test_queue_fail_closed.py` — the two DATABASE_URL
   connect-failure tests imported `psycopg2` directly and crashed with
   `ModuleNotFoundError` where the optional driver is absent. Fix:
   `pytest.importorskip("psycopg2")` (the driver-missing failure mode
   remains covered by `test_database_url_set_without_psycopg2_raises`).

Fixed in `6a95172`, pushed, CI re-run: **7/7 pass**. The MCP job (the CI-1
zero-skip gate) passed on both runs.

Runner deprecation warnings observed (Node 20 actions on Node 24; ubuntu-latest
→ Ubuntu 26 migration notice) — warnings only, not failures, recorded here.

## 3. Publication steps executed (in runbook order)

| Step | Evidence |
|---|---|
| Merge PR #9 → main (merge commit preserving history) | merge commit `c3ff2a8` "merge: v0.5.0 — P1 remediation hardening (QUEUE-2, SEC-1, PERF-2, CI-1)" |
| Tag v0.5.0 on the merge commit | `git ls-remote --tags origin` → `refs/tags/v0.5.0` → `c3ff2a8…` (annotated; no existing tag touched) |
| Formula sha → commit to main + tap repo | main: "chore(homebrew): formula points at v0.5.0 (sha 68edd87)"; tap `Matthew-Selvam/homebrew-open-dispatch`: "open-dispatch 0.5.0 …" |
| Final DMG built from the tag (`make-dmg.sh --version 0.5.0`, default source-ref `v0.5.0`) | `dist/Open-Dispatch-0.5.0.dmg`, 96 MB, sha256 `93934e7eeae486fc2fbf8fc619d2230a9b236079bc37c7ee53f0469d8df9f006` |
| GitHub release published | `gh release create v0.5.0 dist/Open-Dispatch-0.5.0.dmg` → https://github.com/Matthew-Selvam/Open-Dispatch/releases/tag/v0.5.0 |

## 4. Post-publication verification

| Check | Command | Result |
|---|---|---|
| Release + tag exist, not draft | `gh release view v0.5.0 --json tagName,isDraft,assets` | `v0.5.0 draft=false assets=Open-Dispatch-0.5.0.dmg` |
| Asset download integrity | `curl -fsSL -o /tmp/rel.dmg …/releases/download/v0.5.0/Open-Dispatch-0.5.0.dmg && shasum -a 256` | `93934e7e…f9f006` — **byte-identical to the local build** |
| Latest-release asset redirect | `curl -sI …/releases/latest/download/Open-Dispatch-0.5.0.dmg` | serves v0.5.0 asset (latest = v0.5.0) |
| Homebrew formula SHA + upgrade | `brew update && brew upgrade open-dispatch` — brew's own sha256 verification of the tag tarball succeeded (independent check) | `brew list --versions open-dispatch` → **0.5.0** |
| Homebrew install serves 0.5.0 | `/opt/homebrew/opt/open-dispatch/bin/open-dispatch` on a disposable data dir | `/healthz` → `version: 0.5.0, status: ok` |
| Fresh installation reports 0.5.0 | `curl -fsSL raw.githubusercontent.com/…/main/install.sh \| bash` (no args) → "Downloading Open-Dispatch v0.5.0" → installed | server `/healthz` → `version: 0.5.0, status: ok` |
| macOS DMG relocation + launch | mounted the **published** asset, copied `.app` to a fresh path, launched bundled server | `/healthz` → `version: 0.5.0, status: ok`; `dispatch doctor` runs |
| Documentation/version consistency on main | `CHANGELOG.md` heading rolled to `## [0.5.0] — 2026-11-11`; `AUDIT/DEFECT_BACKLOG.md` release status updated; docs-integrity suite | `tests/test_docs_integrity.py` 11/11 pass |
| Full regression on released main | `pytest` with live disposable PostgreSQL 16 (`OPEN_DISPATCH_TEST_POSTGRES_DSN`) | **385 passed, 5 skipped, 1 warning, 13.87 s** (5 skips = MCP tests without the extra in the local venv; the CI MCP job runs them with 0 skips) |

## 5. Asset checksums

| Asset | sha256 |
|---|---|
| `Open-Dispatch-0.5.0.dmg` (published) | `93934e7eeae486fc2fbf8fc619d2230a9b236079bc37c7ee53f0469d8df9f006` |
| tag tarball `v0.5.0.tar.gz` (formula-verified) | `68edd8797ee49b365c9a9c2f5f47ce4784213bc508c91f71b18e6650bd5061b0` |

## 6. Remaining issues / follow-ups (none release-blocking)

1. **Runner deprecation warnings** in CI (Node 20-targeted actions forced to
   Node 24; ubuntu-latest → Ubuntu 26 migration). Cosmetic; bump
   `actions/checkout@v4`/`setup-*` majors when forced.
2. **CHANGELOG backfill on main after tagging**: the `## [0.5.0]` date heading
   and backlog release-status commit landed on `main` *after* the tag (the
   tagged tree carries the correct v0.5.0 content; the post-tag commit only
   dates the changelog heading). This is the standard post-release docs
   follow-up; the released artifacts are unaffected.
3. **RC DMG superseded**: the pre-approval RC DMG built from the release
   branch was replaced by the final DMG built from the tag; only the final
   asset is published.
4. Open P2s unchanged (SEC-2, QUEUE-3, rate limiting, CI-2/CI-3, DOC/ADPT
   items) — per instructions, no P2 work was started during the release.
5. Platform live publishing remains blocked by external
   credentials/approvals (unchanged, documented).

## 7. Hygiene

All verification used disposable databases/containers/volumes and temp
directories; the operator's real `.env` was never read by any test or
verification process; no post was published to any social platform; no
pre-existing tag (v0.2.0–v0.4.1) was modified; `docker compose down -v` and
temp-dir cleanup performed after each scenario.
