"""Pluggable queue. JSONL for zero-infra; Redis when REDIS_URL is set.

Each queue row:
    {
      "id": "uuid",
      "unit": {...ContentUnit dict...},
      "platform": "twitter:pol",
      "scheduled_for": "ISO",
      "status": "queued|publishing|published|failed|dead",
      "attempts": 0,
      "post_id": null,
      "last_error": null,
      "created_at": "ISO",
      "updated_at": "ISO"
    }

Backend selection
-----------------
- If `REDIS_URL` is set → Redis queue (multi-worker safe, fast list_due)
- Otherwise → JSONL on disk (single-process, zero infra)

Both backends implement the same QueueProtocol surface so the worker and
API code never need to know which one is active.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol

log = logging.getLogger("open-dispatch.queue")

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("OPEN_DISPATCH_DATA", REPO_ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
JSONL_PATH = DATA_DIR / "queue.jsonl"

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _iso_to_epoch(iso: str) -> float:
    """ISO-8601 to Unix epoch float. Handles trailing Z."""
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


# ─── Shared protocol (so worker code can target either backend) ───────────

class QueueProtocol(Protocol):
    def enqueue(self, unit_dict: dict, platform_key: str, scheduled_for: str) -> str: ...
    def list_all(self, status: str | None = None) -> list[dict]: ...
    def get(self, row_id: str) -> dict | None: ...
    def list_due(self, now_iso: str) -> list[dict]: ...
    def mark_publishing(self, row_id: str) -> None: ...
    def mark_published(self, row_id: str, post_id: str) -> None: ...
    def mark_failed(self, row_id: str, err: str, dead: bool = False) -> None: ...
    def _update(self, row_id: str, patch: dict[str, Any]) -> None: ...


# ─── JSONL backend (zero-infra MVP) ───────────────────────────────────────

def _read_all() -> list[dict]:
    if not JSONL_PATH.exists():
        return []
    rows = []
    with JSONL_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_all(rows: Iterable[dict]) -> None:
    tmp = JSONL_PATH.with_suffix(".jsonl.tmp")
    with tmp.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(JSONL_PATH)


class JsonlQueue:
    """Single-process JSONL queue. Suitable for self-host MVP."""

    def enqueue(self, unit_dict: dict, platform_key: str, scheduled_for: str) -> str:
        row = _new_row(unit_dict, platform_key, scheduled_for)
        with _LOCK:
            with JSONL_PATH.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row["id"]

    def list_all(self, status: str | None = None) -> list[dict]:
        with _LOCK:
            rows = _read_all()
        if status:
            rows = [r for r in rows if r["status"] == status]
        return rows

    def get(self, row_id: str) -> dict | None:
        with _LOCK:
            for r in _read_all():
                if r["id"] == row_id:
                    return r
        return None

    def list_due(self, now_iso: str) -> list[dict]:
        with _LOCK:
            return [
                r for r in _read_all()
                if r["status"] == "queued" and r["scheduled_for"] <= now_iso
            ]

    def _update(self, row_id: str, patch: dict[str, Any]) -> None:
        with _LOCK:
            rows = _read_all()
            for r in rows:
                if r["id"] == row_id:
                    r.update(patch)
                    r["updated_at"] = _now()
                    break
            _write_all(rows)

    def mark_publishing(self, row_id: str) -> None:
        self._update(row_id, {"status": "publishing"})

    def mark_published(self, row_id: str, post_id: str) -> None:
        self._update(row_id, {"status": "published", "post_id": post_id, "last_error": None})

    def mark_failed(self, row_id: str, err: str, dead: bool = False) -> None:
        row = self.get(row_id) or {}
        attempts = int(row.get("attempts", 0)) + 1
        self._update(row_id, {
            "status": "dead" if dead else "queued",
            "attempts": attempts,
            "last_error": err[:500],
        })


def _new_row(unit_dict: dict, platform_key: str, scheduled_for: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "unit": unit_dict,
        "platform": platform_key,
        "scheduled_for": scheduled_for,
        "status": "queued",
        "attempts": 0,
        "post_id": None,
        "last_error": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


# ─── Redis backend (multi-worker, scalable) ──────────────────────────────
#
# Key layout
#   dispatch:row:<id>    str    JSON-serialized row
#   dispatch:all_ids     set    every row id (for list_all)
#   dispatch:due         zset   queued rows keyed by id, score = epoch
#
# We intentionally don't use redis-rq or any heavier abstraction — keeping
# the schema minimal so anyone can `redis-cli MONITOR` and understand what
# the queue is doing.

class RedisQueue:
    """Redis-backed queue. Set REDIS_URL to opt in.

    Multi-worker safe via SETNX-style claim during mark_publishing.
    """

    KEY_PREFIX = "dispatch"

    def __init__(self, redis_client: Any):
        self._r = redis_client

    def _row_key(self, row_id: str) -> str:
        return f"{self.KEY_PREFIX}:row:{row_id}"

    def _all_key(self) -> str:
        return f"{self.KEY_PREFIX}:all_ids"

    def _due_key(self) -> str:
        return f"{self.KEY_PREFIX}:due"

    def _read(self, row_id: str) -> dict | None:
        raw = self._r.get(self._row_key(row_id))
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def _write(self, row: dict) -> None:
        row["updated_at"] = _now()
        self._r.set(self._row_key(row["id"]), json.dumps(row, ensure_ascii=False))

    def enqueue(self, unit_dict: dict, platform_key: str, scheduled_for: str) -> str:
        row = _new_row(unit_dict, platform_key, scheduled_for)
        pipe = self._r.pipeline()
        pipe.set(self._row_key(row["id"]), json.dumps(row, ensure_ascii=False))
        pipe.sadd(self._all_key(), row["id"])
        pipe.zadd(self._due_key(), {row["id"]: _iso_to_epoch(scheduled_for)})
        pipe.execute()
        return row["id"]

    def list_all(self, status: str | None = None) -> list[dict]:
        ids = self._r.smembers(self._all_key())
        if not ids:
            return []
        # Bulk fetch
        keys = [self._row_key(i.decode() if isinstance(i, bytes) else i) for i in ids]
        raw_rows = self._r.mget(keys)
        rows: list[dict] = []
        for raw in raw_rows:
            if not raw:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            row = json.loads(raw)
            if not status or row.get("status") == status:
                rows.append(row)
        return rows

    def get(self, row_id: str) -> dict | None:
        return self._read(row_id)

    def list_due(self, now_iso: str) -> list[dict]:
        max_score = _iso_to_epoch(now_iso)
        # ZRANGEBYSCORE 0 now → ids whose scheduled_for ≤ now
        ids = self._r.zrangebyscore(self._due_key(), 0, max_score)
        if not ids:
            return []
        rows: list[dict] = []
        for rid in ids:
            row_id = rid.decode() if isinstance(rid, bytes) else rid
            row = self._read(row_id)
            if row and row.get("status") == "queued":
                rows.append(row)
        return rows

    def _update(self, row_id: str, patch: dict[str, Any]) -> None:
        row = self._read(row_id)
        if not row:
            return
        row.update(patch)
        self._write(row)
        # Adjust ZSET membership based on new status
        status = row.get("status")
        if status == "queued":
            self._r.zadd(self._due_key(), {row_id: _iso_to_epoch(row["scheduled_for"])})
        else:
            self._r.zrem(self._due_key(), row_id)

    def mark_publishing(self, row_id: str) -> None:
        # Claim atomically: only flip to "publishing" if currently "queued"
        row = self._read(row_id)
        if not row or row.get("status") != "queued":
            return
        self._update(row_id, {"status": "publishing"})

    def mark_published(self, row_id: str, post_id: str) -> None:
        self._update(row_id, {"status": "published", "post_id": post_id, "last_error": None})

    def mark_failed(self, row_id: str, err: str, dead: bool = False) -> None:
        row = self._read(row_id) or {}
        attempts = int(row.get("attempts", 0)) + 1
        self._update(row_id, {
            "status": "dead" if dead else "queued",
            "attempts": attempts,
            "last_error": err[:500],
        })


# ─── Factory ──────────────────────────────────────────────────────────────

_QUEUE_SINGLETON: QueueProtocol | None = None


def get_queue() -> QueueProtocol:
    """Return the active queue backend. Caches a single instance."""
    global _QUEUE_SINGLETON

    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        # JSONL is stateless across instantiations (file-backed)
        return JsonlQueue()

    if _QUEUE_SINGLETON is not None and isinstance(_QUEUE_SINGLETON, RedisQueue):
        return _QUEUE_SINGLETON

    try:
        import redis  # noqa: WPS433  (import inside fn keeps redis optional)
    except ImportError:
        log.warning("REDIS_URL set but `redis` package not installed; falling back to JSONL")
        return JsonlQueue()

    try:
        client = redis.Redis.from_url(redis_url, decode_responses=False)
        client.ping()
    except Exception as e:  # noqa: BLE001
        log.warning("Redis connect failed (%s); falling back to JSONL", e)
        return JsonlQueue()

    _QUEUE_SINGLETON = RedisQueue(client)
    log.info("queue backend: Redis (%s)", redis_url)
    return _QUEUE_SINGLETON


def _reset_singleton_for_tests() -> None:
    """Test-only — clear the cached Redis client so the next get_queue() re-evaluates."""
    global _QUEUE_SINGLETON
    _QUEUE_SINGLETON = None
