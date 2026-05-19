"""Scheduler worker — loops, picks up due rows, calls adapters, retries on failure.

Run alongside the API:
    python -m scheduler.worker
or via docker-compose (worker service).
"""

from __future__ import annotations

import logging
import os
import random
import time
from datetime import datetime, timezone

import httpx

from adapters import ADAPTERS
from api.queue import get_queue
from api.schema import ContentUnit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("open-dispatch.worker")

POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
MAX_ATTEMPTS = int(os.getenv("WORKER_MAX_ATTEMPTS", "3"))
BACKOFF_BASE = int(os.getenv("WORKER_BACKOFF_BASE", "30"))  # seconds


def _backoff_seconds(attempts: int) -> int:
    return BACKOFF_BASE * (2 ** max(0, attempts - 1)) + random.randint(0, 10)


def _publish(row: dict) -> tuple[bool, str, str]:
    platform_key = row.get("platform", "")
    platform, _, account = platform_key.partition(":")
    if account == "default":
        account = None
    adapter = ADAPTERS.get(platform)
    if not adapter:
        return False, "", f"no adapter for platform '{platform}'"
    unit = ContentUnit.from_dict(row["unit"])
    return adapter.publish(unit, account)


def _fire_webhook(url: str, payload: dict) -> None:
    try:
        httpx.post(url, json=payload, timeout=10)
    except Exception as e:  # noqa: BLE001
        log.warning("webhook failed: %s", e)


def run_once() -> int:
    q = get_queue()
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    due = q.list_due(now_iso)
    if not due:
        return 0
    log.info("publishing %d due row(s)", len(due))
    for row in due:
        rid = row["id"]
        q.mark_publishing(rid)
        ok, post_id, err = _publish(row)
        webhook = (row.get("unit") or {}).get("webhook_url")
        if ok:
            log.info("✓ %s → %s", rid, post_id)
            q.mark_published(rid, post_id)
            if webhook:
                _fire_webhook(webhook, {"event": "published", "id": rid, "post_id": post_id,
                                        "platform": row["platform"]})
        else:
            attempts = int(row.get("attempts", 0)) + 1
            dead = attempts >= MAX_ATTEMPTS
            log.error("✘ %s (attempt %d): %s", rid, attempts, err)
            q.mark_failed(rid, err, dead=dead)
            if not dead:
                # Re-schedule with backoff
                backoff = _backoff_seconds(attempts)
                new_sf = datetime.now(tz=timezone.utc).timestamp() + backoff
                new_sf_iso = datetime.fromtimestamp(new_sf, tz=timezone.utc).isoformat()
                q._update(rid, {"scheduled_for": new_sf_iso})  # noqa: SLF001
                log.info("  retry in %ds", backoff)
            if webhook:
                _fire_webhook(webhook, {"event": "failed", "id": rid, "error": err,
                                        "platform": row["platform"], "dead": dead})
    return len(due)


def main() -> int:
    log.info("scheduler worker starting (poll=%ds, max_attempts=%d, backoff_base=%d)",
             POLL_INTERVAL, MAX_ATTEMPTS, BACKOFF_BASE)
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            log.info("interrupted; exiting")
            return 0
        except Exception as e:  # noqa: BLE001
            log.exception("worker loop error: %s", e)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
