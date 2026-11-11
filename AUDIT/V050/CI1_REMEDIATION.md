# CI-1 Remediation — MCP Optional Dependency and CI Coverage

Status: **RESOLVED** — branch `release/v0.5.0-hardening`.
Original finding (BASELINE_REPORT.md #21, REPOSITORY_INVENTORY.md #119): `ci.yml`
installs only `pytest pytest-asyncio`; the 5 MCP bearer-token auth tests in
`tests/test_client_auth.py` were silently skipped on **every** CI run. They pass
only if a developer happens to `pip install mcp` locally. This is an untested-in-CI
security-relevant surface (MCP client auth propagation).

## Changes

### `.github/workflows/ci.yml`

1. **New `mcp` job** — "MCP extra — clean env, zero security-test skips":
   - Clean pip environment: `pip install '.[mcp,test]'` only (the package plus its
     declared extras; no global/ambient packages).
   - `import mcp_server` smoke check (the server entry point actually imports).
   - Runs `pytest tests/test_client_auth.py` and **fails the job if any test in the
     file skips** — a skip means the security-relevant surface silently went
     untested again, which is exactly the defect being remediated.
2. **Base job hardened** ("Verify base install works without mcp"):
   - Core modules (`api.app`, `api.queue`, `cli`, `profiles`, `scheduler.worker`)
     must import without `mcp` present.
   - When `mcp` is absent, `mcp_server.py` must exit 1 with the actionable
     "open-dispatch[mcp]" install hint — not an ImportError traceback.
3. **Wheel metadata check added**: the built wheel must declare
   `Provides-Extra: mcp`.

## Local verification (clean environments, this machine)

| Check | Environment | Result |
|---|---|---|
| Base install (`pip install .`, no extras) | fresh venv, Python 3.13 | OK — `api.app`, `api.queue`, `cli`, `profiles` import; no `mcp` needed |
| `mcp_server.py` without `mcp` installed | same fresh venv | exit 1 with `Or: pip install 'open-dispatch[mcp]'` (the designed hint) |
| MCP tests on base install | same venv + pytest | `9 passed, 5 skipped` — the 5 MCP tests skip **by design** without the extra |
| MCP extra install (`.[mcp,test]`) | fresh venv, Python 3.13 | OK — `import mcp_server` works |
| MCP tests with extra installed | same venv | **`14 passed` — 0 skips** (the 5 previously-skipped tests run and pass) |
| Wheel build + metadata | fresh venv | `open_dispatch-0.4.1-py3-none-any.whl`; `Provides-Extra: mcp` present; `Requires-Dist: mcp>=1.0; extra == "mcp"`; core modules present |
| ci.yml validity | yaml.safe_load | parses |

## Requirements mapping

1. Base install without MCP — verified in a clean venv; **met**.
2. MCP install with the documented extra — verified `.[mcp]` (via `[mcp,test]`);
   **met**.
3. Core imports require no MCP packages — verified; **met**.
4. Missing optional deps → useful errors — `mcp_server.py` SystemExit hint verified;
   **met**.
5. MCP tested when the extra is installed — new CI job runs them with zero skips
   allowed; **met** (CI run pending push; the exact commands were executed locally).
6. Metadata declares extras — wheel METADATA verified + asserted in CI; **met**.
7. CI tests base AND MCP installs — base job + new `mcp` job; **met**.
8. No accidental global deps — the `mcp` job installs only `.[mcp,test]` in a fresh
   runner; **met**.
9. Clean environments — `pip install '.[mcp,test]'` on a bare `setup-python` runner
   is clean by construction; **met**.
10. Existing install methods unbroken — no runtime code changed for this finding;
    **met**.

## Notes / residual risk

- The zero-skip gate is scoped to `tests/test_client_auth.py` (the security
  surface from the finding). Other MCP-adjacent tests, if added later, must be
  added to that file or the gate widened.
- CI-2/CI-3 from the baseline report (lint/type-check/coverage, release
  automation) remain P2 items — deliberately not addressed here (scope: the four
  P1 findings).
