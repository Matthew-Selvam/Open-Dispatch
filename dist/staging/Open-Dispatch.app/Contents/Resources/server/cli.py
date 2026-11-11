#!/usr/bin/env python3
"""dispatch — CLI client for Open-Dispatch.

Usage:
  dispatch send --platforms twitter,bluesky --text "hello"
  dispatch send --file unit.json
  dispatch queue [--status queued|published|failed]
  dispatch worker             # run scheduler in-process
  dispatch quick-test         # send a Telegram ping
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

from api.queue import get_queue
from api.schema import ContentUnit, validate
from datetime import datetime, timezone

DEFAULT_URL = "http://127.0.0.1:8000"


def _post(url: str, body: dict) -> dict:
    r = httpx.post(url, json=body, timeout=30)
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
                elif plat == "youtube":
                    # YouTube needs a video_path — text-only CLI mode can't
                    # supply one. Use `dispatch send --file unit.json` for
                    # real YouTube uploads.
                    formats["youtube_short"] = {"caption": args.text}
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

    resp = _post(f"{args.url}/dispatch", unit.to_dict())
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dispatch", description="Open-Dispatch CLI")
    p.add_argument("--url", default=DEFAULT_URL, help="Open-Dispatch API base URL")
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
    q.add_argument("--status", help="filter (queued|publishing|published|failed|dead)")
    q.set_defaults(func=cmd_queue)

    w = sub.add_parser("worker", help="Run the scheduler worker in-process")
    w.set_defaults(func=cmd_worker)

    t = sub.add_parser("quick-test", help="Send a Telegram ping")
    t.set_defaults(func=cmd_quick_test)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
