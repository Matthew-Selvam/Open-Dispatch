"""Pluggable queue. JSONL for zero-infra; Redis or Postgres for production.

Each queue row:
    {
      "id": "uuid",
      "unit": {...ContentUnit dict...},
      "platform": "twitter:pol",
      "scheduled_for": "ISO",
      "status": "queued|publishing|published|failed|dead|canceled",
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
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Protocol

log = logging.getLogger("open-dispatch.queue")


class QueueBackendError(RuntimeError):
    """An explicitly configured queue backend is unavailable or unusable.

    Raised instead of silently falling back to JSONL: when an operator
    configures DATABASE_URL or REDIS_URL they are choosing a durable store,
    and a fallback to a *different* store would split the queue — jobs
    enqueued during the outage would land in JSONL while older jobs sat in
    the unreachable backend, and they could never be reconciled.

    Callers should surface this to the operator (API: 503 with the message;
    worker: log and retry the next poll). A backend that is unavailable
    must be loud, not silent.
    """

    def __init__(self, backend: str, detail: str) -> None:
        self.backend = backend
        self.detail = detail
        super().__init__(
            f"queue backend {backend!r} is configured but unusable: {detail}. "
            "Refusing to fall back to another store — fix the configuration "
            "or unset the backend variable to use the JSONL queue."
        )

try:
    import fcntl as _fcntl  # noqa: F401  (POSIX)
except ImportError:  # pragma: no cover — Windows has no flock
    _fcntl = None

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("OPEN_DISPATCH_DATA", REPO_ROOT / "data"))
JSONL_PATH = DATA_DIR / "queue.jsonl"

_LOCK = threading.RLock()


def _ensure_data_dir() -> None:
    """Create the data dir on first use, not at import time.

    Import-time mkdir meant a pip install created `site-packages/data` merely
    by importing the module — which fails outright when site-packages is
    root-owned — and left a stray directory on unrelated imports.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def _exclusive() -> Iterator[None]:
    """Hold the in-process lock AND an exclusive cross-process flock.

    The JSONL backend is documented single-process, but the default
    docker-compose runs api + worker as two processes sharing one volume.
    Without the flock, the worker's whole-file rewrite (tmp + replace) can
    land between the API's read and its replace, silently dropping rows the
    API appended in that window. All mutating entry points go through here;
    read-only paths accept the (already repaired) torn-line risk.
    """
    with _LOCK:
        if _fcntl is None:  # pragma: no cover
            yield
            return
        _ensure_data_dir()
        lock_path = JSONL_PATH.with_suffix(".jsonl.lock")
        with lock_path.open("w") as lf:
            _fcntl.flock(lf.fileno(), _fcntl.LOCK_EX)
            try:
                yield
            finally:
                _fcntl.flock(lf.fileno(), _fcntl.LOCK_UN)


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# Shared by every backend's reap_stale_publishing: the reaper cannot know
# whether the platform accepted the post before the worker died, so the row
# must be quarantined ("failed") rather than auto-re-queued (a duplicate).
_STALE_CLAIM_ERROR = (
    "stale publishing claim reaped: publish outcome unknown — "
    "verify on the platform before retrying to avoid a duplicate post"
)


def _iso_to_epoch(iso: str) -> float:
    """ISO-8601 to Unix epoch float. Handles trailing Z."""
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def _row_due(row: dict, due_epoch: float) -> bool:
    """Is this row's scheduled_for at or before `due_epoch`?

    Compares real instants, not ISO strings: '21:00+05:30' is an hour *before*
    '16:00+00:00' but lexicographically after it. A row whose scheduled_for we
    can't parse is treated as due — same as a plain 'now' — so the worker
    surfaces it instead of the queue silently dead-ending it.
    """
    try:
        return _iso_to_epoch(row["scheduled_for"]) <= due_epoch
    except (ValueError, TypeError, KeyError):
        log.warning("row %s has unparseable scheduled_for %r; treating as due",
                    row.get("id", "?"), row.get("scheduled_for"))
        return True


# ─── Shared protocol (so worker code can target either backend) ───────────

class QueueProtocol(Protocol):
    def enqueue(self, unit_dict: dict, platform_key: str, scheduled_for: str) -> str: ...
    def list_all(self, status: str | None = None) -> list[dict]: ...
    def get(self, row_id: str) -> dict | None: ...
    def list_due(self, now_iso: str) -> list[dict]: ...
    def mark_publishing(self, row_id: str) -> bool: ...
    def mark_published(self, row_id: str, post_id: str) -> bool: ...
    def mark_failed(self, row_id: str, err: str, dead: bool = False,
                    retry_at: str | None = None) -> bool: ...
    def retry(self, row_id: str) -> bool: ...
    def delete(self, row_id: str) -> bool: ...
    def cancel_campaign(self, unit_id: str) -> list[dict]: ...

    def reap_stale_publishing(self, lease_seconds: int) -> list[str]:
        """Quarantine rows stuck in "publishing" older than the lease.

        A hard crash mid-publish (SIGKILL, OOM, power loss) cannot be caught
        by the worker's try/except, so the row would sit in "publishing"
        forever — and retry() only accepts queued/failed/dead, so it could not
        even be re-queued by hand.

        The reaper cannot know whether the platform already accepted the
        post, so the row is moved to "failed" (never straight back to
        "queued"): an automatic retry could double-post. The operator sees
        the "verify before retrying" error and re-queues explicitly with
        retry() once they have confirmed the outcome on the platform.
        Returns the quarantined row ids.
        """
        ...

    def _update(self, row_id: str, patch: dict[str, Any]) -> None: ...


# ─── JSONL backend (zero-infra MVP) ───────────────────────────────────────

def _read_all() -> list[dict]:
    if not JSONL_PATH.exists():
        return []
    rows = []
    with JSONL_PATH.open() as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    # A single torn write (crash mid-append, disk issue) must
                    # not take the whole queue down — skip the bad line but
                    # keep serving everything else. The raw line is preserved
                    # in a sidecar so the job is never silently lost: an
                    # operator (or the enqueue path) can recover it.
                    log.warning("skipping corrupt queue line %d in %s; "
                                "preserved in %s", lineno, JSONL_PATH,
                                JSONL_PATH.with_suffix(".jsonl.corrupt"))
                    try:
                        with JSONL_PATH.with_suffix(".jsonl.corrupt").open("a") as c:
                            c.write(line + "\n")
                    except OSError:
                        pass  # the sidecar is best-effort; never block reads
    return rows


def _write_all(rows: Iterable[dict]) -> None:
    _ensure_data_dir()
    tmp = JSONL_PATH.with_suffix(".jsonl.tmp")
    with tmp.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(JSONL_PATH)


class JsonlQueue:
    """JSONL queue on disk — zero infrastructure.

    Safe for the common self-host shape (one api + one worker sharing a
    data dir): every mutating operation holds a cross-process flock, so the
    worker's whole-file rewrite can no longer drop rows the api appended
    concurrently. For many workers or multi-host, use Redis or Postgres.
    """

    def enqueue(self, unit_dict: dict, platform_key: str, scheduled_for: str) -> str:
        row = _new_row(unit_dict, platform_key, scheduled_for)
        _ensure_data_dir()
        with _exclusive():
            # If the file doesn't end with a newline (torn write from a crash),
            # start a fresh line — otherwise this row concatenates onto the
            # corrupt one and BOTH become unreadable.
            needs_nl = False
            if JSONL_PATH.exists() and JSONL_PATH.stat().st_size > 0:
                with JSONL_PATH.open("rb") as f:
                    f.seek(-1, 2)
                    needs_nl = f.read(1) != b"\n"
            with JSONL_PATH.open("a") as f:
                if needs_nl:
                    f.write("\n")
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row["id"]

    def list_all(self, status: str | None = None) -> list[dict]:
        with _exclusive():
            rows = _read_all()
        if status:
            rows = [r for r in rows if r["status"] == status]
        return rows

    def get(self, row_id: str) -> dict | None:
        with _exclusive():
            for r in _read_all():
                if r["id"] == row_id:
                    return r
        return None

    def list_due(self, now_iso: str) -> list[dict]:
        due_epoch = _iso_to_epoch(now_iso)
        with _exclusive():
            return [
                r for r in _read_all()
                if r["status"] == "queued" and _row_due(r, due_epoch)
            ]

    def _update(self, row_id: str, patch: dict[str, Any]) -> None:
        with _exclusive():
            rows = _read_all()
            for r in rows:
                if r["id"] == row_id:
                    r.update(patch)
                    r["updated_at"] = _now()
                    break
            _write_all(rows)

    def mark_publishing(self, row_id: str) -> bool:
        """Claim a row for publishing.

        Requires status == "queued" AND the row being due. Without the due
        check, a worker holding an id from an earlier list_due() can claim a
        row that another worker has since backed off to a future time.
        """
        with _exclusive():
            rows = _read_all()
            due_epoch = _iso_to_epoch(_now())
            for r in rows:
                if r["id"] == row_id and r.get("status") == "queued" and _row_due(r, due_epoch):
                    r["status"] = "publishing"
                    r["updated_at"] = _now()
                    _write_all(rows)
                    return True
        return False

    def mark_published(self, row_id: str, post_id: str) -> bool:
        with _exclusive():
            rows = _read_all()
            for r in rows:
                if r["id"] == row_id and r.get("status") in {"queued", "publishing"}:
                    r.update({"status": "published", "post_id": post_id, "last_error": None, "updated_at": _now()})
                    _write_all(rows)
                    return True
        return False

    def mark_failed(self, row_id: str, err: str, dead: bool = False,
                    retry_at: str | None = None) -> bool:
        with _exclusive():
            rows = _read_all()
            for r in rows:
                if r["id"] == row_id and r.get("status") in {"queued", "publishing"}:
                    patch = {"status": "dead" if dead else "queued",
                             "attempts": int(r.get("attempts", 0)) + 1,
                             "last_error": err[:500], "updated_at": _now()}
                    # Apply the backoff in the SAME write as the status flip,
                    # otherwise the row is briefly "queued" with a past
                    # scheduled_for and another worker claims it immediately.
                    if retry_at and not dead:
                        patch["scheduled_for"] = retry_at
                    r.update(patch)
                    _write_all(rows)
                    return True
        return False

    def retry(self, row_id: str) -> bool:
        with _exclusive():
            rows = _read_all()
            for r in rows:
                if r["id"] == row_id and r.get("status") in {"queued", "failed", "dead"}:
                    r.update({"status": "queued", "last_error": None, "updated_at": _now()})
                    _write_all(rows)
                    return True
        return False

    def delete(self, row_id: str) -> bool:
        with _exclusive():
            rows = _read_all()
            new = [r for r in rows if r["id"] != row_id]
            if len(new) == len(rows):
                return False
            _write_all(new)
        return True

    def cancel_campaign(self, unit_id: str) -> list[dict]:
        """Flip every still-queued row of a campaign to 'canceled'.

        Returns the canceled rows. Rows already publishing/published/dead are
        left alone — cancel is best-effort before the post goes live.
        """
        canceled: list[dict] = []
        with _exclusive():
            rows = _read_all()
            for r in rows:
                if (r.get("unit") or {}).get("id") == unit_id and r["status"] == "queued":
                    r["status"] = "canceled"
                    r["updated_at"] = _now()
                    canceled.append(r)
            if canceled:
                _write_all(rows)
        return canceled


    def reap_stale_publishing(self, lease_seconds: int) -> list[str]:
        now_epoch = _iso_to_epoch(_now())
        reaped: list[str] = []
        with _exclusive():
            rows = _read_all()
            for r in rows:
                if r.get("status") != "publishing":
                    continue
                try:
                    age = now_epoch - _iso_to_epoch(r.get("updated_at", ""))
                except (ValueError, TypeError):
                    age = lease_seconds + 1  # unparseable timestamp: reap
                if age > lease_seconds:
                    r["status"] = "failed"
                    r["last_error"] = _STALE_CLAIM_ERROR
                    r["updated_at"] = _now()
                    reaped.append(r["id"])
            if reaped:
                _write_all(rows)
        return reaped


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

    # WatchError (redis-py) is raised when the watched key changed between
    # WATCH and EXEC — a benign contention signal, not a backend failure.
    # The redis package is an optional extra, so the import is lazy: the
    # fallback is a sentinel class that never matches, so the
    # `except WatchError` branch is dead code only when redis is absent.
    try:
        from redis.exceptions import WatchError as _WatchError  # noqa: WPS433
    except ImportError:  # pragma: no cover
        class _WatchError(Exception):  # type: ignore[no-redef]
            pass

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

    def mark_publishing(self, row_id: str) -> bool:
        """Claim a due row. A row backed off to a future time cannot be claimed."""
        # Optimistic transaction makes the queued check and state transition atomic.
        pipe = self._r.pipeline()
        key = self._row_key(row_id)
        if not hasattr(pipe, "watch"):
            row = self._read(row_id)
            if row and row.get("status") == "queued" and _row_due(row, _iso_to_epoch(_now())):
                self._update(row_id, {"status": "publishing"})
                return True
            return False
        try:
            pipe.watch(key)
            row = self._read(row_id)
            if not row or row.get("status") != "queued" or not _row_due(row, _iso_to_epoch(_now())):
                pipe.unwatch()
                return False
            row["status"] = "publishing"
            row["updated_at"] = _now()
            pipe.multi()
            pipe.set(key, json.dumps(row, ensure_ascii=False))
            pipe.zrem(self._due_key(), row_id)
            pipe.execute()
            return True
        except self._WatchError:
            # A concurrent cancellation/claim loses this attempt; the worker's
            # next poll will observe the current state.
            try:
                pipe.reset()
            except Exception:
                pass
            return False
        except Exception as e:
            # QUEUE-2 fail-closed: an outage here is NOT a lost claim. Returning
            # False on a connection error would make the worker skip the row
            # ("claim lost") while never reporting the backend is down — the
            # operator would only see a queue that never moves. Let connection
            # errors propagate so the worker logs them and the next poll
            # retries the connection.
            try:
                pipe.reset()
            except Exception:
                pass
            raise

    def _conditional_update(self, row_id: str, allowed: set[str], patch: dict[str, Any]) -> bool:
        pipe = self._r.pipeline()
        if not hasattr(pipe, "watch"):
            row = self._read(row_id)
            if not row or row.get("status") not in allowed:
                return False
            row.update(patch)
            self._write(row)
            status = row.get("status")
            if status == "queued":
                self._r.zadd(self._due_key(), {row_id: _iso_to_epoch(row["scheduled_for"])})
            else:
                self._r.zrem(self._due_key(), row_id)
            return True
        try:
            key = self._row_key(row_id)
            pipe.watch(key)
            row = self._read(row_id)
            if not row or row.get("status") not in allowed:
                pipe.unwatch()
                return False
            row.update(patch)
            row["updated_at"] = _now()
            pipe.multi()
            pipe.set(key, json.dumps(row, ensure_ascii=False))
            if row.get("status") == "queued":
                pipe.zadd(self._due_key(), {row_id: _iso_to_epoch(row["scheduled_for"])})
            else:
                pipe.zrem(self._due_key(), row_id)
            pipe.execute()
            return True
        except self._WatchError:
            # Only a concurrent write is contention — a retryable, benign
            # False. Every other error (connection, timeout, auth) must
            # propagate: swallowing it in mark_published would make the
            # worker believe the row was not marked published when the write
            # never happened, silently masking the outage.
            try:
                pipe.reset()
            except Exception:
                pass
            return False
        except Exception as exc:
            try:
                pipe.reset()
            except Exception:
                pass
            raise

    def mark_published(self, row_id: str, post_id: str) -> bool:
        return self._conditional_update(row_id, {"publishing"},
                                        {"status": "published", "post_id": post_id, "last_error": None})

    def mark_failed(self, row_id: str, err: str, dead: bool = False,
                    retry_at: str | None = None) -> bool:
        row = self._read(row_id) or {}
        patch = {"status": "dead" if dead else "queued",
                 "attempts": int(row.get("attempts", 0)) + 1,
                 "last_error": err[:500]}
        # Same-write backoff: see JsonlQueue.mark_failed for why.
        if retry_at and not dead:
            patch["scheduled_for"] = retry_at
        return self._conditional_update(row_id, {"publishing"}, patch)

    def retry(self, row_id: str) -> bool:
        return self._conditional_update(row_id, {"queued", "failed", "dead"},
                                        {"status": "queued", "last_error": None})

    def delete(self, row_id: str) -> bool:
        pipe = self._r.pipeline()
        pipe.delete(self._row_key(row_id))
        pipe.srem(self._all_key(), row_id)
        pipe.zrem(self._due_key(), row_id)
        results = pipe.execute()
        return bool(results[0])  # 1 if key existed and was deleted

    def cancel_campaign(self, unit_id: str) -> list[dict]:
        """Flip every still-queued row of a campaign to 'canceled'.

        Status-guarded like mark_publishing: a row a worker already grabbed
        (publishing/published/dead) is never canceled mid-publish. The same
        read-then-write window the rest of this backend has is accepted here.
        """
        canceled: list[dict] = []
        for rid in self._r.smembers(self._all_key()):
            row_id = rid.decode() if isinstance(rid, bytes) else rid
            row = self._read(row_id)
            if not row or (row.get("unit") or {}).get("id") != unit_id:
                continue
            pipe = self._r.pipeline()
            if not hasattr(pipe, "watch"):
                if row.get("status") != "queued":
                    continue
                row["status"] = "canceled"
                self._write(row)
                self._r.zrem(self._due_key(), row_id)
                canceled.append(row)
                continue
            try:
                pipe.watch(self._row_key(row_id))
                current = self._read(row_id)
                if not current or current.get("status") != "queued":
                    pipe.unwatch()
                    continue
                current["status"] = "canceled"
                current["updated_at"] = _now()
                pipe.multi()
                pipe.set(self._row_key(row_id), json.dumps(current, ensure_ascii=False))
                pipe.zrem(self._due_key(), row_id)
                pipe.execute()
                canceled.append(current)
            except Exception:
                try:
                    pipe.reset()
                except Exception:
                    pass
        return canceled

    def reap_stale_publishing(self, lease_seconds: int) -> list[str]:
        now_epoch = _iso_to_epoch(_now())
        reaped: list[str] = []
        for rid in self._r.smembers(self._all_key()):
            row_id = rid.decode() if isinstance(rid, bytes) else rid
            row = self._read(row_id)
            if not row or row.get("status") != "publishing":
                continue
            try:
                age = now_epoch - _iso_to_epoch(row.get("updated_at", ""))
            except (ValueError, TypeError):
                age = lease_seconds + 1
            if age > lease_seconds and self._conditional_update(
                row_id, {"publishing"},
                {"status": "failed", "last_error": _STALE_CLAIM_ERROR},
            ):
                reaped.append(row_id)
        return reaped



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

    @contextmanager
    def _conn(self):
        # The connection context commits on success and rolls back on error;
        # closing() then releases the socket. Closing alone silently rolled
        # back the schema DDL and every write with psycopg2.
        with closing(self._conn_factory()) as conn:
            with conn:
                yield conn

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

    def mark_publishing(self, row_id: str) -> bool:
        """Atomically flip queued to publishing; return whether claimed.

        A row already publishing or completed is a no-op.
        """
        # The scheduled_for guard matters as much as the status guard: a worker
        # holding a stale id must not claim a row another worker backed off.
        sql = f"""
            UPDATE {self.TABLE}
            SET status = 'publishing', updated_at = now()
            WHERE id = %s AND status = 'queued' AND scheduled_for <= now()
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (row_id,))
            return getattr(cur, "rowcount", 1) > 0

    def mark_published(self, row_id: str, post_id: str) -> bool:
        sql = f"UPDATE {self.TABLE} SET status = 'published', post_id = %s, last_error = NULL, updated_at = now() WHERE id = %s AND status = 'publishing'"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (post_id, row_id))
            return getattr(cur, "rowcount", 1) > 0

    def mark_failed(self, row_id: str, err: str, dead: bool = False,
                    retry_at: str | None = None) -> bool:
        # scheduled_for moves in the SAME statement as the status flip, so no
        # other worker can observe a 'queued' row that is already past due.
        sql = (f"UPDATE {self.TABLE} SET status = %s, attempts = attempts + 1, "
               f"last_error = %s, scheduled_for = COALESCE(%s, scheduled_for), "
               f"updated_at = now() WHERE id = %s AND status = 'publishing'")
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, ("dead" if dead else "queued", err[:500],
                              None if dead else retry_at, row_id))
            return getattr(cur, "rowcount", 1) > 0

    def retry(self, row_id: str) -> bool:
        sql = f"UPDATE {self.TABLE} SET status = 'queued', last_error = NULL, updated_at = now() WHERE id = %s AND status IN ('queued', 'failed', 'dead')"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (row_id,))
            return getattr(cur, "rowcount", 1) > 0

    def delete(self, row_id: str) -> bool:
        sql = f"DELETE FROM {self.TABLE} WHERE id = %s"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (row_id,))
            return getattr(cur, "rowcount", 1) > 0

    def cancel_campaign(self, unit_id: str) -> list[dict]:
        """Flip every still-queued row of a campaign to 'canceled'.

        One atomic UPDATE ... RETURNING — the status guard lives in SQL, so
        concurrent workers and this cancel can never interleave half-states.
        """
        sql = f"""
            UPDATE {self.TABLE}
            SET status = 'canceled', updated_at = now()
            WHERE (unit->>'id') = %s AND status = 'queued'
            RETURNING *
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (unit_id,))
            return [self._row_to_dict(r) for r in cur.fetchall()]

    def reap_stale_publishing(self, lease_seconds: int) -> list[str]:
        # Quarantine, don't requeue: the platform may have accepted the post
        # before the worker died, and an automatic retry would double-post.
        sql = f"""
            UPDATE {self.TABLE}
            SET status = 'failed', last_error = %s
            WHERE status = 'publishing'
              AND updated_at < now() - make_interval(secs => %s)
            RETURNING id
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, (_STALE_CLAIM_ERROR, lease_seconds))
            return [str(r[0]) for r in cur.fetchall()]


# ─── Factory ──────────────────────────────────────────────────────────────

_QUEUE_SINGLETON: QueueProtocol | None = None


def get_queue() -> QueueProtocol:
    """Return the active queue backend. Caches a single instance.

    Selection order: DATABASE_URL → REDIS_URL → JSONL.

    FAIL-CLOSED (QUEUE-2): when DATABASE_URL or REDIS_URL is explicitly set
    but that backend cannot be reached (or its driver is missing), this
    raises QueueBackendError instead of silently falling back to JSONL.
    A silent fallback would split the queue across two stores — jobs
    enqueued during the outage would live in JSONL while the configured
    backend held the rest, and they could never be reconciled. Callers
    (API, worker) must surface the failure; a backend that becomes
    available again is picked up on the next get_queue() call because the
    singleton is only cached after a successful construction.
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
        except ImportError as e:
            raise QueueBackendError(
                "postgres",
                "DATABASE_URL is set but the psycopg2 driver is not installed "
                "(pip install psycopg2-binary or the 'open-dispatch[postgres]' extra)",
            ) from e
        try:
            def _conn_factory():
                return psycopg2.connect(db_url)
            _QUEUE_SINGLETON = PostgresQueue(_conn_factory)
            log.info("queue backend: Postgres")
            return _QUEUE_SINGLETON
        except Exception as e:  # noqa: BLE001
            raise QueueBackendError(
                "postgres",
                f"cannot connect to the database (check DATABASE_URL, host "
                f"reachability, and credentials): {type(e).__name__}: {e}",
            ) from e

    # Then Redis
    if redis_url:
        if _QUEUE_SINGLETON is not None and isinstance(_QUEUE_SINGLETON, RedisQueue):
            return _QUEUE_SINGLETON
        try:
            import redis  # noqa: WPS433
        except ImportError as e:
            raise QueueBackendError(
                "redis",
                "REDIS_URL is set but the redis package is not installed "
                "(pip install redis or the 'open-dispatch[redis]' extra)",
            ) from e
        try:
            client = redis.Redis.from_url(redis_url, decode_responses=False)
            client.ping()
            _QUEUE_SINGLETON = RedisQueue(client)
            log.info("queue backend: Redis (%s)", redis_url)
            return _QUEUE_SINGLETON
        except Exception as e:  # noqa: BLE001
            raise QueueBackendError(
                "redis",
                f"cannot connect to the Redis server (check REDIS_URL and "
                f"that the server is reachable): {type(e).__name__}: {e}",
            ) from e

    # JSONL is the default only when no durable backend is configured.
    return JsonlQueue()


def _reset_singleton_for_tests() -> None:
    """Test-only — clear the cached client so the next get_queue() re-evaluates."""
    global _QUEUE_SINGLETON
    _QUEUE_SINGLETON = None
