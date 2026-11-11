# Documentation and claim verification — Phase 10

Compared README, INSTALL_METHODS, environment template, source, git tags, local installation evidence and the public landing page on 2026-11-10. The landing page returned HTTP 200 and was read in a browser. Its linked v0.4.0 DMG download returned HTTP 200 to a HEAD request; the artifact itself was not downloaded in this phase. Local Markdown links in README, CHANGELOG and SECURITY were checked for file existence; no broken local Markdown targets were found in that set.

| Claim | Evidence | Status |
|---|---|---|
| "One request, ten platforms" | Ten Python adapters exist and have mocked tests, but no live platform verification or approval proof. | Qualified; add capability/approval matrix. |
| Default install.sh version v0.4.0 | `install.sh:26` sets `v0.4.0`; `git show v0.4.0:pyproject.toml` says `0.1.0`. Local install returned older CLI/API behavior. | **Incorrect release tag** (P0). |
| Homebrew open-dispatch 0.4.0 | Formula URL pins v0.4.0 tarball and calls it 0.4.0; that tarball has `0.1.0` package metadata. | **Incorrect artifact** (P0). |
| macOS app starts bundled Python server | Local `make-dmg.sh` bundle's wrapper has relative `dist/build/...` paths and fails after relocation (DIMG-1). Landing says install in 10 s and supports Apple Silicon/Intel; only arm64 was built/tested here. | **False for local build; Intel unverified**. |
| PostgreSQL queue is a working option | Real PostgreSQL 16 fails with `UndefinedTable` because schema transaction rolls back (PG-1). | **False**. |
| README test count | README says 318; baseline collected 355 (350 pass, 5 skip in documented environment). | Stale. |
| README install.sh example | Says `--version v0.4.0` while comment says `default: main`; source default is v0.4.0. | Contradiction. |
| PyPI install | README's install table can imply direct PyPI availability; package is not published (Phase 2). | Clarify Git URL only until publication. |
| MCP tool list | Actual server exposes 10 tools; README's explicit list omits campaign status/cancel (Phase 2). | Stale list. |
| n8n platform support | Node source supports six platforms; product supports ten. README names six in n8n description, but this limitation is easy to miss. | Clarify. |
| Docker exposure | Compose publishes all interfaces while auth is off by default. README/env template warn later in the instructions. | Put warning and loopback default in quick start. |
| LinkedIn `image_url` | Adapter docstring mentions it; code reads only pre-uploaded `asset_urn` (Phase 4). | Incorrect adapter docs. |
| Uninstall/upgrade | install.sh upgrade was tested; complete uninstall and migration guidance absent. | Missing. |

The README references `docs/demo.gif`, which does not exist in the repository (baseline finding). The public landing page's "Five ways in" section currently recommends the DMG first despite DIMG-1. It also says the app supports Intel, which this arm64-only local build did not establish. The landing page's download link is live but live availability alone does not verify its runtime behavior.

## Priority corrections

1. Repair PG-1, DIMG-1 and the release tag/artifact mismatch, then update installation instructions from verified artifacts. Do not relabel the stale v0.4.0 tag as working code.
2. Amend Docker quick start to bind loopback by default or require auth before public exposure.
3. Correct test counts, installer default comment, broken demo image and capability limitations.
4. Add explicit upgrade, rollback and uninstall instructions and platform approval prerequisites.

Documentation cannot truthfully describe a v1.0.0 release until the code and artifacts are repaired and verified again.
