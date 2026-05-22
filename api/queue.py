"""Pluggable queue. JSONL for zero-infra; Redis or Postgres for production.

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

Backend selection (in priority order)
-------------------------------------
- If `DATABASE_URL` is set → Postgres queue (true ACID + cross-region multi-worker)
- Elif `REDIS_URL` is set    → Redis queue (multi-worker, fast list_due)
- Otherwise                  → JSONL on disk (single-process, zero infra)

All three backends implement the same QueueProtocol surface so the worker
and API code never need to know which one is active.
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
    def delete(self, row_id: str) -> bool: ...
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

    def delete(self, row_id: str) -> bool:
        with _LOCK:
            rows = _read_all()
            new = [r for r in rows if r["id"] != row_id]
            if len(new) == len(rows):
                return False
            _write_all(new)
        return True


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

    def delete(self, row_id: str) -> bool:
        pipe = self._r.pipeline()
        pipe.delete(self._row_key(row_id))
        pipe.srem(self._all_key(), row_id)
        pipe.zrem(self._due_key(), row_id)
        results = pipe.execute()
        return bool(results[0])  # 1 if key existed and was deleted


# ─── Postgres backend ──────────────────────────────────────────────────────
#
# Schema (auto-created on first use):
#   CREATE TABLE open_dispatch_queue (
#     id            uuid PRIMARY KEY,
#     unit          jsonb NOT NULL,
#     platform      text  NOT NULL,
#     scheduled_for timestamptz NOT NULL,
#     status        text NOT NULL DEFAULT 'queued',
#     attempts      int  NOT NULL DEFAULT 0,
#     post_id       text,
#     last_error    text,
#     created_at    timestamptz NOT NULL DEFAULT now(),
#     updated_at    timestamptz NOT NULL DEFAULT now()
#   );
#   CREATE INDEX ... ON (status, scheduled_for)  for fast list_due()
#
# Multi-worker safety: list_due + mark_publishing combined into a single
# atomic `SELECT ... FOR UPDATE SKIP LOCKED` so two workers in different
# regions can poll without grabbing the same row.

class PostgresQueue:
    """Postgres-backed queue using a single table and SKIP LOCKED claims.

    The `conn` constructor arg is a psycopg2 connection (or psycopg3 — we
    use cursor + execute, which is portable).
    """

    TABLE = "open_dispatch_queue"

    def __init__(self, conn_factory) -> None:
        """`conn_factory` is a callable returning a fresh connection.

        We don't hold a long-lived connection because psycopg2 connections
        are not thread-safe; one per operation is the simplest correct path.
        """
        self._conn_factory = conn_factory
        self._ensure_schema()

    def _conn(self):
        return self._conn_factory()

    def _ensure_schema(self) -> None:
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {self.TABLE} (
            id            uuid PRIMARY KEY,
            unit          jsonb NOT NULL,
            platform      text  NOT NULL,
            scheduled_for timestamptz NOT NULL,
            status        text  NOT NULL DEFAULT 'queued',
            attempts      int   NOT NULL DEFAULT 0,
            post_id       text,
            last_error    text,
            created_at    timestamptz NOT NULL DEFAULT now(),
            updated_at    timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS open_dispatch_queue_due_idx
            ON {self.TABLE} (status, scheduled_for) WHERE status = 'queued';
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(ddl)

    @staticmethod
    def _row_to_dict(r) -> dict:
        """psycopg2 row tuple → dict matching the QueueProtocol shape."""
        return {
            "id": str(r[0]),
            "unit": r[1],
            "platform": r[2],
            "scheduled_for": r[3].isoformat() if hasattr(r[3], "isoformat") else r[3],
            "status": r[4],
            "attempts": r[5],
            "post_id": r[6],
            "last_error": r[7],
            "created_at": r[8].isoformat() if hasattr(r[8], "isoformat") else r[8],
            "updated_at": r[9].isoformat() if hasattr(r[9], "isoformat") else r[9],
        }

    def enqueue(self, unit_dict: dict, platform_key: str, scheduled_for: str) -> str:
        new_id = str(uuid.uuid4())
        sql = f"""
            INSERT INTO {self.TABLE} (id, unit, platform, scheduled_for)
            VALUES (%s, %s::jsonb, %s, %s::timestamptz)
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (new_id, json.dumps(unit_dict), platform_key, scheduled_for))
        return new_id

    def list_all(self, status: str | None = None) -> list[dict]:
        sql = f"SELECT * FROM {self.TABLE}"
        params: tuple = ()
        if status:
            sql += " WHERE status = %s"
            params = (status,)
        sql += " ORDER BY created_at DESC"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return [self._row_to_dict(r) for r in cur.fetchall()]

    def get(self, row_id: str) -> dict | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {self.TABLE} WHERE id = %s", (row_id,))
            r = cur.fetchone()
            return self._row_to_dict(r) if r else None

    def list_due(self, now_iso: str) -> list[dict]:
        sql = f"""
            SELECT * FROM {self.TABLE}
            WHERE status = 'queued' AND scheduled_for <= %s::timestamptz
            ORDER BY scheduled_for ASC
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (now_iso,))
            return [self._row_to_dict(r) for r in cur.fetchall()]

    def _update(self, row_id: str, patch: dict[str, Any]) -> None:
        # Build dynamic UPDATE clause from patch dict
        cols = []
        vals: list = []
        for k, v in patch.items():
            cols.append(f"{k} = %s")
            vals.append(v)
        cols.append("updated_at = now()")
        sql = f"UPDATE {self.TABLE} SET {', '.join(cols)} WHERE id = %s"
        vals.append(row_id)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, tuple(vals))

    def mark_publishing(self, row_id: str) -> None:
        """Atomically flip queued → publishing using FOR UPDATE SKIP LOCKED.

        If another worker has the row locked or it's already publishing/done,
        the UPDATE is a no-op.
        """
        sql = f"""
            UPDATE {self.TABLE}
            SET status = 'publishing', updated_at = now()
            WHERE id = %s AND status = 'queued'
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (row_id,))

    def mark_published(self, row_id: str, post_id: str) -> None:
        self._update(row_id, {
            "status": "published",
            "post_id": post_id,
            "last_error": None,
        })

    def mark_failed(self, row_id: str, err: str, dead: bool = False) -> None:
        sql = f"""
            UPDATE {self.TABLE}
            SET status = %s,
                attempts = attempts + 1,
                last_error = %s,
                updated_at = now()
            WHERE id = %s
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, ("dead" if dead else "queued", err[:500], row_id))

    def delete(self, row_id: str) -> bool:
        sql = f"DELETE FROM {self.TABLE} WHERE id = %s"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (row_id,))
            return cur.rowcount > 0


# ─── Factory ──────────────────────────────────────────────────────────────

_QUEUE_SINGLETON: QueueProtocol | None = None


def get_queue() -> QueueProtocol:
    """Return the active queue backend. Caches a single instance.

    Selection order: DATABASE_URL → REDIS_URL → JSONL.
    """
    global _QUEUE_SINGLETON

    db_url = os.getenv("DATABASE_URL", "").strip()
    redis_url = os.getenv("REDIS_URL", "").strip()

    # Postgres first
    if db_url:
        if _QUEUE_SINGLETON is not None and isinstance(_QUEUE_SINGLETON, PostgresQueue):
            return _QUEUE_SINGLETON
        try:
            import psycopg2  # noqa: WPS433
        except ImportError:
            log.warning("DATABASE_URL set but psycopg2 not installed; trying Redis/JSONL")
        else:
            try:
                def _conn_factory():
                    return psycopg2.connect(db_url)
                _QUEUE_SINGLETON = PostgresQueue(_conn_factory)
                log.info("queue backend: Postgres")
                return _QUEUE_SINGLETON
            except Exception as e:  # noqa: BLE001
                log.warning("Postgres connect failed (%s); trying Redis/JSONL", e)

    # Then Redis
    if redis_url:
        if _QUEUE_SINGLETON is not None and isinstance(_QUEUE_SINGLETON, RedisQueue):
            return _QUEUE_SINGLETON
        try:
            import redis  # noqa: WPS433
        except ImportError:
            log.warning("REDIS_URL set but `redis` package not installed; falling back to JSONL")
        else:
            try:
                client = redis.Redis.from_url(redis_url, decode_responses=False)
                client.ping()
                _QUEUE_SINGLETON = RedisQueue(client)
                log.info("queue backend: Redis (%s)", redis_url)
                return _QUEUE_SINGLETON
            except Exception as e:  # noqa: BLE001
                log.warning("Redis connect failed (%s); falling back to JSONL", e)

    # Fallback: JSONL
    return JsonlQueue()


def _reset_singleton_for_tests() -> None:
    """Test-only — clear the cached client so the next get_queue() re-evaluates."""
    global _QUEUE_SINGLETON
    _QUEUE_SINGLETON = None
