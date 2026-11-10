#!/usr/bin/env python3
"""dispatch — CLI client for Open-Dispatch.

Usage:
  dispatch send --platforms twitter,bluesky --text "hello"
  dispatch send --file unit.json
  dispatch campaign <unit-id> [--cancel] [--local]
  dispatch queue [--status queued|published|failed|dead|canceled]
  dispatch worker             # run scheduler in-process
  dispatch quick-test         # send a Telegram ping
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

from api.queue import get_queue
from api.schema import ContentUnit, validate
from datetime import datetime, timezone

DEFAULT_URL = "http://127.0.0.1:8000"


def _auth_headers(token: str | None = None) -> dict[str, str]:
    """Authorization header for a server running with OPEN_DISPATCH_API_TOKEN.

    Returns {} when no token is configured, so an unauthenticated server is
    left alone. A blank/whitespace token is treated as absent rather than
    sending an empty credential.
    """
    value = (token if token is not None else os.environ.get("OPEN_DISPATCH_API_TOKEN", "")).strip()
    return {"Authorization": f"Bearer {value}"} if value else {}


def _post(url: str, body: dict, token: str | None = None) -> dict:
    r = httpx.post(url, json=body, headers=_auth_headers(token), timeout=30)
    if r.status_code in (401, 403):
        raise SystemExit(
            f"HTTP {r.status_code}: the server requires authentication. Set\n"
            "  OPEN_DISPATCH_API_TOKEN in your environment, or pass --token.\n"
            f"  (server said: {r.text[:200]})"
        )
    if r.status_code >= 400:
        raise SystemExit(f"HTTP {r.status_code}: {r.text}")
    return r.json()


def cmd_send(args: argparse.Namespace) -> int:
    if args.file:
        unit = ContentUnit.load(Path(args.file))
    else:
        targets = [p.strip() for p in (args.platforms or "").split(",") if p.strip()]
        if not targets:
            raise SystemExit("--platforms required when not using --file")
        formats: dict = {}
        if args.text:
            # Build a sensible default format per platform.
            for t in targets:
                plat = t.split(":")[0]
                if plat == "telegram":
                    formats["telegram_message"] = {"text": args.text}
                elif plat == "twitter":
                    formats["twitter_thread"] = {"tweets": [args.text]}
                elif plat == "bluesky":
                    formats["bluesky_post"] = {"text": args.text}
                elif plat == "linkedin":
                    formats["linkedin_post"] = {"text": args.text}
                elif plat == "instagram":
                    formats["instagram_post"] = {"caption": args.text}
                elif plat == "threads":
                    formats["threads_post"] = {"text": args.text}
                elif plat == "facebook":
                    formats["facebook_post"] = {"text": args.text}
                elif plat == "discord":
                    formats["discord_message"] = {"content": args.text}
                elif plat == "youtube":
                    raise SystemExit("YouTube requires --file with a video_path; text-only mode is unsupported")
        unit = ContentUnit(targets=targets, formats=formats,
                           scheduled_for=args.at,
                           webhook_url=args.webhook)
    errs = validate(unit)
    if errs:
        for e in errs:
            print(f"✘ {e}", file=sys.stderr)
        return 1

    if args.local:
        # Bypass HTTP, enqueue directly
        q = get_queue()
        sf = unit.scheduled_for or datetime.now(tz=timezone.utc).isoformat()
        for target in unit.targets:
            plat, _, acct = target.partition(":")
            key = f"{plat}:{acct or 'default'}"
            rid = q.enqueue(unit.to_dict(), key, sf)
            print(f"✓ enqueued {rid} target={target} sched={sf}")
        return 0

    resp = _post(f"{args.url}/dispatch", unit.to_dict(), args.token)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    rows = get_queue().list_all(status=args.status)
    if not rows:
        print("(empty)")
        return 0
    for r in rows:
        print(f"{r['id']}  {r['platform']:24}  {r['status']:10}  {r['scheduled_for']}  "
              f"attempts={r['attempts']}  err={(r.get('last_error') or '')[:80]}")
    return 0


def cmd_campaign(args: argparse.Namespace) -> int:
    if args.local:
        q = get_queue()
        rows = [r for r in q.list_all() if (r.get("unit") or {}).get("id") == args.unit_id]
        if not rows:
            raise SystemExit(f"campaign not found: {args.unit_id}")
        if args.cancel:
            rows = q.cancel_campaign(args.unit_id)
            print(json.dumps({"unit_id": args.unit_id, "canceled": len(rows), "rows": rows}, indent=2))
        else:
            print(json.dumps({"unit_id": args.unit_id, "count": len(rows), "rows": rows}, indent=2))
        return 0

    if args.cancel:
        resp = _post(f"{args.url}/campaign/{args.unit_id}/cancel", {}, args.token)
    else:
        r = httpx.get(f"{args.url}/campaign/{args.unit_id}",
                      headers=_auth_headers(args.token), timeout=30)
        if r.status_code in (401, 403):
            raise SystemExit(
                f"HTTP {r.status_code}: the server requires authentication. Set\n"
                "  OPEN_DISPATCH_API_TOKEN in your environment, or pass --token.\n"
                f"  (server said: {r.text[:200]})"
            )
        if r.status_code >= 400:
            raise SystemExit(f"HTTP {r.status_code}: {r.text}")
        resp = r.json()
    print(json.dumps(resp, indent=2))
    return 0


def cmd_worker(args: argparse.Namespace) -> int:
    from scheduler.worker import main as worker_main
    return worker_main()


def cmd_quick_test(args: argparse.Namespace) -> int:
    from adapters import telegram
    from datetime import datetime as dt
    unit = ContentUnit(
        targets=["telegram:default"],
        formats={"telegram_message": {"text": f"✅ open-dispatch ping {dt.now():%Y-%m-%d %H:%M:%S}"}},
    )
    ok, post_id, err = telegram.publish(unit)
    if ok:
        print(f"✓ Telegram msg id={post_id}")
        return 0
    print(f"✘ {err}", file=sys.stderr)
    return 1


# ── doctor ────────────────────────────────────────────────────────────────────

def _doctor_env(data_dir: Path) -> dict[str, str]:
    """Effective env: process environment overlaid on the data-dir .env file.

    Precedence mirrors the server (load_dotenv does not override existing
    env vars): a var set in the shell wins over one in .env. Never returns
    values — callers print var names only, never secrets.
    """
    from dotenv import dotenv_values

    env_path = data_dir / ".env"
    file_vals = dotenv_values(env_path) if env_path.exists() else {}
    merged = {k: (v or "") for k, v in file_vals.items()}
    for key, value in os.environ.items():
        if value:
            merged[key] = value
    return merged


def cmd_doctor(args: argparse.Namespace) -> int:
    """Diagnose this install: data dir, credentials, profiles, server, worker."""
    from profiles import PLATFORM_CRED_MAP, REQUIRED_ENV_VARS

    data_dir = Path(os.environ.get("OPEN_DISPATCH_DATA") or (Path.home() / ".open-dispatch")).expanduser()
    env = _doctor_env(data_dir)
    env_path = data_dir / ".env"

    print("Environment")
    if env_path.exists():
        print(f"  ✓ data dir   {data_dir}")
        print(f"  ✓ .env found {env_path}")
    else:
        print(f"  ⚠ data dir   {data_dir}")
        print(f"  ⚠ no .env    expected at {env_path} (env vars may still be set)")

    # Queue backend, same precedence as api.queue.get_queue
    if env.get("DATABASE_URL"):
        backend = "postgres"
    elif env.get("REDIS_URL"):
        backend = "redis"
    else:
        backend = "jsonl"
    print(f"  ✓ queue      {backend}")

    media_dir = Path(env.get("OPEN_DISPATCH_MEDIA_DIR") or (data_dir / "media")).expanduser()
    if media_dir.exists() and os.access(media_dir, os.W_OK):
        print(f"  ✓ media dir  {media_dir}")
    else:
        print(f"  ⚠ media dir  {media_dir} (missing or not writable)")
    print()

    print("Platforms (default account; per-account overrides use _<ACCT> suffixes)")
    configured_any = False
    for platform, required in REQUIRED_ENV_VARS.items():
        missing = [name for name in required if not env.get(name, "").strip()]
        if missing:
            print(f"  ✗ {platform:<10} missing: {', '.join(missing)}")
        else:
            configured_any = True
            print(f"  ✓ {platform:<10} {', '.join(required)}")
    print()

    profiles_path = data_dir / "profiles.json"
    if profiles_path.exists():
        print("Profiles")
        try:
            raw = json.loads(profiles_path.read_text())
            profiles = raw.get("profiles", [])
            if not profiles:
                print("  (empty)")
            for p in profiles:
                creds = p.get("platforms") or {}
                active = [
                    plat for plat, fields in creds.items()
                    if any(str(v).strip() for v in (fields or {}).values())
                    and plat in PLATFORM_CRED_MAP
                ]
                label = f"{p.get('emoji', '🎭')} {p.get('name') or p.get('id', '?')}"
                print(f"  {label:<14} {', '.join(sorted(active)) or 'no credentials'}")
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ⚠ unreadable profiles.json: {e}")
        print()

    print(f"Server ({args.url})")
    try:
        r = httpx.get(f"{args.url}/healthz", headers=_auth_headers(args.token), timeout=5)
        if r.status_code in (401, 403):
            print("  ⚠ reachable but requires auth — pass --token or set OPEN_DISPATCH_API_TOKEN")
        else:
            r.raise_for_status()
            h = r.json()
            worker = h.get("worker") or {}
            counts = h.get("counts") or {}
            print(f"  ✓ API v{h.get('version', '?')} backend={h.get('backend', '?')} "
                  f"rows={h.get('total', 0)} failed={h.get('failed_count', 0)}")
            print(f"  {'✓' if worker.get('running') else '⚠'} worker     {worker.get('label', '?')}")
            if counts:
                summary = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
                print(f"  queue       {summary or 'empty'}")
    except (httpx.HTTPError, ValueError):
        print("  ⚠ not reachable — start it with `open-dispatch` (or check --url)")
    print()

    if not configured_any:
        print("✘ No platform is fully configured.")
        print(f"  Edit {env_path} (copy from .env.example) or export the env vars above.")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dispatch", description="Open-Dispatch CLI")
    p.add_argument("--url", default=DEFAULT_URL, help="Open-Dispatch API base URL")
    p.add_argument("--token", default=os.environ.get("OPEN_DISPATCH_API_TOKEN") or None,
                   help="API token; defaults to $OPEN_DISPATCH_API_TOKEN")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("send", help="Enqueue a post")
    s.add_argument("--platforms", help="comma-separated targets, e.g. twitter:pol,bluesky")
    s.add_argument("--text", help="post text (used for every platform)")
    s.add_argument("--file", help="ContentUnit JSON file (full control)")
    s.add_argument("--at", help="ISO-8601 timestamp to schedule for; default = now")
    s.add_argument("--webhook", help="callback URL fired on publish/fail")
    s.add_argument("--local", action="store_true", help="bypass HTTP; enqueue directly")
    s.set_defaults(func=cmd_send)

    q = sub.add_parser("queue", help="List rows in the queue")
    q.add_argument("--status", help="filter (queued|publishing|published|failed|dead|canceled)")
    q.set_defaults(func=cmd_queue)

    c = sub.add_parser("campaign", help="Inspect or cancel a dispatched campaign")
    c.add_argument("unit_id", help="content unit ID returned by dispatch")
    c.add_argument("--cancel", action="store_true", help="cancel queued rows")
    c.add_argument("--local", action="store_true", help="bypass HTTP; use the local queue")
    c.set_defaults(func=cmd_campaign)

    w = sub.add_parser("worker", help="Run the scheduler worker in-process")
    w.set_defaults(func=cmd_worker)

    t = sub.add_parser("quick-test", help="Send a Telegram ping")
    t.set_defaults(func=cmd_quick_test)

    d = sub.add_parser("doctor", help="Diagnose this install: credentials, data dir, server, worker")
    d.set_defaults(func=cmd_doctor)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


def server() -> None:
    """Entry point for `open-dispatch` — start the API + web UI server."""
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("api.app:app", host=host, port=port)


def worker() -> None:
    """Entry point for `open-dispatch-worker` — run the scheduler worker."""
    from scheduler.worker import main as worker_main
    raise SystemExit(worker_main())


if __name__ == "__main__":
    sys.exit(main())
