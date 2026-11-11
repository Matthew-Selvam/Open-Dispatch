# CLI, AI, media and integrations audit — Phase 9

Environment: Python 3.12.13 audit venv; isolated data directories. `pytest -q tests/test_cli.py tests/test_ai_caption.py tests/test_media_transcode.py`: 48 passed. External AI services, n8n runtime and social accounts were not called.

## CLI

`dispatch --help` lists `send`, `queue`, `campaign`, `worker`, `quick-test`, `doctor`. Invalid command `dispatch bogus` exited 2 with argparse usage. `dispatch doctor --help` exited 0. Phase 2 verified local send, queue and doctor against installed artifacts. `quick-test` performs a **real Telegram post**, so it was intentionally not executed. Global `--url`/`--token` must precede the subcommand; the CLI reports a parser error if placed after it. Existing CLI tests cover text-only YouTube rejection and local campaign status/cancel, but not every network error/exit path.

## AI caption adaptation

Heuristic fallback, platform limits, JSON parsing, XSS escaping and API validation are covered by the 48-test targeted run. OpenRouter and Ollama are configurable with timeouts; live calls were unavailable without an account/local model. A malformed provider response was injected by patching `_call_openrouter` to return `{"twitter_thread":"not an object"}`. `adapt_caption_async(..., provider='openrouter')` raised `AttributeError: 'str' object has no attribute 'get'` instead of falling back. **AI-1 (P2):** validate model JSON value types before `_enforce_limits`, and include type errors in the fallback path. Test malformed objects, lists and nonstring fields. Provider selection with an unknown provider name currently chooses OpenRouter implicitly; reject invalid values explicitly.

## Media

The test suite covers resize, aspect crop, RGBA flattening, EXIF orientation, corrupt bytes, unsupported platform and raw API endpoint behavior. `/media/transcode` reads the whole request before its 10 MiB check (SEC-2). Video specs are informational; no video transcoder exists. File reads/writes use `media.paths`, whose root restrictions depend on `OPEN_DISPATCH_MEDIA_DIR`; the environment template warns about this. Large decompression-bomb and sustained memory tests were not run. The API returns a 400 `TranscodeError` for corrupt image data, but broad Pillow exception strings may vary by version.

## n8n, webhooks and desktop communication

The n8n package built in Phase 2. Source review confirms five operations: dispatch, adapt, get row, retry row and list queue. The selectable platform list contains six of the ten API platforms; default-format construction likewise handles six. HTTP helpers propagate errors unless n8n's `continueOnFail` is enabled. A live n8n installation and execution of each operation remain unverified.

**N8N-1 (P2):** the credential test calls unauthenticated `/healthz`, so it can report success with an invalid bearer token even though every operational endpoint returns 401. Test against a protected route such as `/api/profiles`.

**N8N-2 (P2):** the n8n node exposes only six platforms while the product advertises ten. Its six-platform description is accurate, but the integration docs should state that limitation prominently or add the four missing formats and platform choices.

Webhooks use public-HTTPS validation, DNS pinning and no redirects (security review); no real receiver was invoked. The macOS menu bar app launches, but its bundled server wrapper has a relative-path defect (DIMG-1 in the installation matrix), so full desktop-to-API communication cannot be verified until repair.
