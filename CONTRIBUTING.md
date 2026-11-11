# Contributing to Open-Dispatch

Thanks for considering a contribution. This guide gets you from zero to a passing PR in ~10 minutes.

## Quick setup

```bash
git clone https://github.com/Matthew-Selvam/Open-Dispatch
cd Open-Dispatch
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-asyncio
cp .env.example .env   # leave creds blank — tests don't need them

# Run the test suite
pytest -q

# Boot the API + UI locally
uvicorn api.app:app --reload
# Open http://localhost:8000
```

Equivalent one-liner (what CI does): `pip install -e ".[test]"`.

Tests run in ~15 seconds (≈385 tests) and need zero credentials or network.
If you broke a test, you'll know fast.

### Optional: queue-backend development

The JSONL queue works out of the box. To touch the Redis or Postgres
backends:

```bash
pip install -e ".[redis,postgres,test]"

# The live-Postgres integration tests (tests/test_postgres_integration.py)
# run against a disposable database you point them at:
OPEN_DISPATCH_TEST_POSTGRES_DSN='host=127.0.0.1 port=5499 user=postgres dbname=od_audit' \
  pytest tests/test_postgres_integration.py
```

Without the DSN those tests skip — that's expected. Locally you can spin up a
disposable instance with `initdb`/`pg_ctl` or a throwaway container; never
point tests at a database you care about.

The skips you'll see on a fresh setup (9 total) are all by design and none
are hiding a failure:

- 5 × `test_client_auth.py` — MCP bearer-auth tests, need `pip install -e ".[mcp,test]"`
- 2 × `test_postgres_integration.py` — need `OPEN_DISPATCH_TEST_POSTGRES_DSN`
- 2 × `test_queue_fail_closed.py` — Postgres connect-failure injections, need
  the optional `psycopg2` driver installed

CI installs the `mcp` extra in a dedicated job and enforces **zero skips** on
the MCP auth tests, so the security-relevant surface is always exercised
there even though your laptop skips it.

### Two gotchas the test suite will catch for you

1. **Every env var the code reads must be documented in `.env.example`.**
   `tests/test_docs_integrity.py` enforces this — if you add an `os.getenv`, add
   the variable (with a comment) to `.env.example` in the same PR.
2. **Relative links in the docs must resolve.** The same test file checks
   every relative link in the `.md` files at repo root.

## Finding something to work on

Issues labelled [`good first issue`](https://github.com/Matthew-Selvam/Open-Dispatch/labels/good%20first%20issue)
are scoped, self-contained tasks with acceptance criteria in the issue body.
Comment on the issue before you start so we don't duplicate work, and mention
the issue number in your PR (`fixes #NN`).

## Project layout

```
adapters/        platform-specific publishers (1 file per platform)
ai/              caption adapter (OpenRouter / Ollama / heuristic)
api/             FastAPI app, ContentUnit schema, queue backends
media/           image transcoding (Pillow)
scheduler/       worker loop
tests/           pytest suite — mirrors the package layout
web/             Jinja templates + static assets for the UI
n8n-node/        community n8n node (TypeScript)
```

## Adding a new platform adapter

It's intentionally an ~80 LOC job:

1. **Create `adapters/<platform>.py`**:
   ```python
   from api.schema import ContentUnit

   def publish(unit: ContentUnit, account: str | None = None) -> tuple[bool, str, str]:
       """Returns (ok, post_id, error_message)."""
       fmt = unit.formats.get("<platform>_post") or {}
       # 1. Read creds from env (support account-suffix overrides)
       # 2. Call the platform API
       # 3. Return (True, post_id, "") on success or (False, "", err) on failure
   ```

2. **Register it** in `adapters/__init__.py`:
   ```python
   from . import <platform>
   ADAPTERS["<platform>"] = <platform>
   ```

3. **Document the format key** in `README.md`'s ContentUnit shape section.

4. **Add tests** in `tests/test_adapters.py` covering:
   - Missing-creds path
   - Empty-payload path
   - Happy path (mocked httpx / SDK)
   - HTTP error path

5. **Add an env block** to `.env.example` with setup instructions.

That's it. Open a PR.

## Adding a new queue backend

Implement the `QueueProtocol` in `api/queue.py` and wire backend selection into `get_queue()`. Two non-negotiables (see `AUDIT/V050/QUEUE2_REMEDIATION.md` for why): an explicitly configured backend that is unavailable must raise `QueueBackendError` rather than silently falling back, and stale `publishing` claims must be quarantined for operator verification, never auto-requeued. Existing implementations (`JsonlQueue`, `RedisQueue`, `PostgresQueue`) are good reference.

## Code style

- Python: type hints everywhere, `from __future__ import annotations` at the top
- Module docstrings — explain *why* the file exists, not just *what* it does
- `httpx` for HTTP (sync OR async), not `requests`
- Errors return `(False, "", "human-readable error")` from adapters; never raise
- Keep adapter files self-contained — they should run if you delete every other file

## Commit messages

Imperative mood, first line ≤72 chars. Body explains the "why" if non-obvious.

```
fix: telegram adapter handles 429 rate-limit with backoff

Bot API returns 429 with retry_after JSON. Previously we'd retry
immediately and burn attempts. Now we honor the hint.
```

## Reporting bugs

Open an issue with:
1. What you did (curl command, n8n workflow, CLI invocation)
2. What you expected
3. What happened (the error text from the queue row's `last_error` is gold)
4. Your `.env`-redacted to show which platforms you have configured

## Reporting security issues

Do **not** open a public issue. Follow [SECURITY.md](./SECURITY.md): report via
[GitHub private security advisories](https://github.com/Matthew-Selvam/Open-Dispatch/security/advisories/new).
The latest tagged release receives security patches; older releases do not.

## License

By contributing, you agree your work will be released under the project's MIT license.
