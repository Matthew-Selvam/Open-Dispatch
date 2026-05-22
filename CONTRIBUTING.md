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

Tests run in <1s and need zero credentials or network. If you broke a test, you'll know fast.

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

Implement the `QueueProtocol` in `api/queue.py` and wire backend selection into `get_queue()`. Existing implementations (`JsonlQueue`, `RedisQueue`) are good reference.

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

Don't open a public issue. Email security details to the maintainer
(handle from `pyproject.toml` author field).

## License

By contributing, you agree your work will be released under the project's MIT license.
