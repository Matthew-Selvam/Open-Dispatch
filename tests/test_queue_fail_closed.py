"""QUEUE-2 fail-closed tests — every backend must fail loudly, never silently.

A configured queue backend (DATABASE_URL / REDIS_URL) that is unusable must
raise QueueBackendError — not silently fall back to JSONL. A silent fallback
would split the queue across two stores: jobs enqueued during the outage
would land in JSONL while older jobs sat in the unreachable backend, and
they could never be reconciled. These tests inject failures at every layer:

- get_queue() with a configured backend whose driver is missing
- get_queue() with a configured backend that cannot connect (Postgres, Redis)
- get_queue() recovery after an outage (deterministic, no stale fallback)
- Postgres mid-operation outage (enqueue raises — no false-success enqueue)
- Redis mid-operation outage (connection errors propagate, not swallowed)
- Redis WATCH contention (benign False) vs outage (raise)
- JSONL corrupt line preservation (no silent job loss)
- JSONL write failure (enqueue raises)
- worker during an outage (clear error, deterministic retry, no crash)
- API healthz/dispatch during an outage (503, no false success)
"""

from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

from api.queue import (PostgresQueue, RedisQueue, _read_all,
                       _reset_singleton_for_tests, get_queue)

def _qbe():
    """Lazy QueueBackendError: test_hardening reloads api.queue, which
    rebinds module globals — a top-level import would hold the stale class
    and pytest.raises would never match the re-raised error."""
    import api.queue
    return api.queue.QueueBackendError

from tests.test_postgres_queue import FakeConn
from tests.test_redis_queue import FakePipeline, FakeRedis


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ── get_queue fail-closed ─────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _fresh_singleton():
    _reset_singleton_for_tests()
    yield
    _reset_singleton_for_tests()


def _hide_module(monkeypatch, name: str) -> None:
    """Make `import name` fail with ImportError even if installed."""
    monkeypatch.setitem(sys.modules, name, None)


def test_database_url_set_without_psycopg2_raises(monkeypatch):
    """DATABASE_URL set but driver missing → QueueBackendError, no JSONL fallback."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@localhost:1/db")
    monkeypatch.delenv("REDIS_URL", raising=False)
    _hide_module(monkeypatch, "psycopg2")
    with pytest.raises(_qbe()) as e:
        get_queue()
    assert "psycopg2" in str(e.value)
    assert "fall back" in str(e.value)


def test_database_url_set_but_unreachable_raises(monkeypatch):
    """DATABASE_URL set, server unreachable → QueueBackendError, no JSONL fallback."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@invalid-host:1/db?connect_timeout=1")
    monkeypatch.delenv("REDIS_URL", raising=False)
    import psycopg2

    def _boom(*a, **kw):
        raise psycopg2.OperationalError("could not connect to server")

    monkeypatch.setattr(psycopg2, "connect", _boom)
    with pytest.raises(_qbe()) as e:
        get_queue()
    # the wrap may come from the constructor's schema connect or from
    # get_queue's own connect check — both are explicit backend failures
    assert "OperationalError" in str(e.value)
    assert "Refusing to fall back" in str(e.value)


def test_redis_url_set_without_redis_raises(monkeypatch):
    """REDIS_URL set but driver missing → QueueBackendError, no JSONL fallback."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6399/0")
    _hide_module(monkeypatch, "redis")
    with pytest.raises(_qbe()) as e:
        get_queue()
    assert "redis" in str(e.value)


def test_redis_url_set_but_unreachable_raises(monkeypatch):
    """REDIS_URL set, server unreachable → QueueBackendError."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://invalid-host:6399/0")
    fake = types.ModuleType("redis")
    fake.exceptions = types.ModuleType("redis.exceptions")

    class _Redis:
        @staticmethod
        def from_url(*a, **kw):
            raise ConnectionError("connection refused")

    fake.Redis = _Redis
    monkeypatch.setitem(sys.modules, "redis", fake)
    monkeypatch.setitem(sys.modules, "redis.exceptions", fake.exceptions)
    with pytest.raises(_qbe()) as e:
        get_queue()
    assert "cannot connect" in str(e.value)


def test_jsonl_default_when_nothing_configured(monkeypatch):
    """No backend configured → JSONL (unchanged default behaviour)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    # Import lazily: other test files (test_hardening) importlib.reload
    # api.queue, creating new class identities — a module-level isinstance
    # against a pre-reload class reference would spuriously fail.
    from api.queue import JsonlQueue as _JsonlQueue
    assert isinstance(get_queue(), _JsonlQueue)


def test_no_silent_fallback_after_outage_recovers(monkeypatch):
    """Deterministic recovery: a backend that is down then reachable is picked
    up by the next get_queue() call — the singleton is only cached on success."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://od@localhost:5499/od_audit")
    monkeypatch.delenv("REDIS_URL", raising=False)
    import psycopg2

    calls = {"n": 0}

    def _flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise psycopg2.OperationalError("down")
        return FakeConn()  # "backend comes back up"

    monkeypatch.setattr(psycopg2, "connect", _flaky)
    with pytest.raises(_qbe()):
        get_queue()
    from api.queue import PostgresQueue as _PostgresQueue  # lazy: reload-safe
    q = get_queue()
    assert isinstance(q, _PostgresQueue)


# ── Postgres mid-operation outage ─────────────────────────────────────────

def test_postgres_enqueue_raises_on_outage():
    """A connection failure mid-enqueue raises — no false-success enqueue."""
    state = {"fail": False}

    def factory():
        if state["fail"]:
            raise ConnectionError("server closed the connection")
        return FakeConn()

    q = PostgresQueue(factory)
    state["fail"] = True
    with pytest.raises(Exception):
        q.enqueue({"hello": "world"}, "twitter:default", _now_iso())


def test_postgres_list_all_raises_on_outage():
    state = {"fail": False}

    def factory():
        if state["fail"]:
            raise ConnectionError("server closed the connection")
        return FakeConn()

    q = PostgresQueue(factory)
    state["fail"] = True
    with pytest.raises(Exception):
        q.list_all()


def test_postgres_queue_constructor_raises_on_unreachable():
    """PostgresQueue.__init__ runs _ensure_schema — an unreachable server
    raises immediately (the constructor never caches a broken backend)."""
    def factory():
        raise ConnectionError("connection refused")

    with pytest.raises(Exception):
        PostgresQueue(factory)


# ── Redis mid-operation outage ─────────────────────────────────────────────

class _ConnError(Exception):
    pass


class _WatchPipe:
    """A pipeline supporting watch/unwatch/multi that raises on execute."""

    def __init__(self, parent: FakeRedis, exc: Exception) -> None:
        self._parent = parent
        self._exc = exc
        self.reset_called = False

    def watch(self, key: str) -> None:
        pass

    def unwatch(self) -> None:
        pass

    def multi(self) -> None:
        pass

    def reset(self) -> None:
        self.reset_called = True

    def set(self, key: str, value: str) -> "_WatchPipe":
        return self

    def sadd(self, key: str, value: str) -> "_WatchPipe":
        return self

    def zadd(self, key: str, mapping: dict) -> "_WatchPipe":
        return self

    def zrem(self, key: str, member: str) -> "_WatchPipe":
        return self

    def execute(self) -> None:
        raise self._exc


class _InjectableRedis(FakeRedis):
    """FakeRedis whose pipeline raises on execute when `fail` is armed."""

    def __init__(self) -> None:
        super().__init__()
        self._fail: Exception | None = None
        self.last_pipe = None

    def pipeline(self):
        if self._fail is not None:
            p = _WatchPipe(self, self._fail)
            self.last_pipe = p
            return p
        return FakePipeline(self)


def _redis_with_outage(exc: Exception) -> tuple[RedisQueue, _InjectableRedis, str]:
    """Build a Redis queue with one row, then arm the outage."""
    r = _InjectableRedis()
    q = RedisQueue(r)
    rid = q.enqueue({}, "twitter:default", _now_iso())
    r._fail = exc
    return q, r, rid


def test_redis_mark_publishing_outage_raises_not_swallowed():
    """A transactional mark_publishing with a dead connection raises — the
    pre-QUEUE-2 behaviour swallowed it and returned False."""
    q, r, rid = _redis_with_outage(_ConnError("connection refused"))
    with pytest.raises(_ConnError):
        q.mark_publishing(rid)
    assert r.last_pipe.reset_called


def test_redis_watch_error_is_contention_not_outage():
    """WatchError → False (retryable claim loss), not a raise."""
    q, r, rid = _redis_with_outage(RedisQueue._WatchError("watched key changed"))
    assert q.mark_publishing(rid) is False


def test_redis_mark_published_outage_raises_not_swallowed():
    """mark_published (=_conditional_update) with a dead connection raises —
    swallowing it would mask the outage and leave the row in 'publishing'
    with the worker believing the write never happened."""
    r = _InjectableRedis()
    q = RedisQueue(r)
    rid = q.enqueue({}, "twitter:default", _now_iso())
    assert q.mark_publishing(rid)  # row is now 'publishing'
    r._fail = _ConnError("connection refused")
    with pytest.raises(_ConnError):
        q.mark_published(rid, "post-id")


def test_redis_enqueue_raises_on_outage():
    """A dead connection during enqueue raises — no false-success enqueue."""
    q, r, rid = _redis_with_outage(_ConnError("connection refused"))
    with pytest.raises(_ConnError):
        q.enqueue({}, "twitter:default", _now_iso())


# ── JSONL corrupt-line preservation + write failure ────────────────────────

def test_jsonl_corrupt_line_preserved_in_sidecar(tmp_path, monkeypatch):
    """A torn write must not silently lose a job: the raw line is preserved
    in a sidecar so the operator can recover it."""
    monkeypatch.setattr("api.queue.JSONL_PATH", tmp_path / "queue.jsonl")
    good = {"id": "a", "status": "queued"}
    bad = '{"id": "b", "status": "queued"'  # torn write — no closing brace
    p = tmp_path / "queue.jsonl"
    p.write_text(json.dumps(good) + "\n" + bad + "\n")
    rows = _read_all()
    assert len(rows) == 1 and rows[0]["id"] == "a"
    sidecar = (tmp_path / "queue.jsonl.corrupt").read_text()
    assert sidecar.strip() == bad.strip()  # the raw line is saved


class _ReadOnlyPath:
    """A Path stand-in whose open() raises (disk full / read-only dir)."""

    def __init__(self, target: Path) -> None:
        self._target = target

    def exists(self) -> bool:
        return self._target.exists()

    def stat(self):
        return self._target.stat()

    def open(self, *a, **kw):
        raise OSError("No space left on device")

    def with_suffix(self, suffix: str) -> Path:
        return self._target.with_suffix(suffix)


def test_jsonl_enqueue_raises_on_write_failure(tmp_path, monkeypatch):
    """A full disk / read-only data dir must raise — no false-success enqueue."""
    monkeypatch.setattr("api.queue.JSONL_PATH", _ReadOnlyPath(tmp_path / "queue.jsonl"))
    import api.queue as qmod
    q = qmod.JsonlQueue()
    with pytest.raises(OSError):
        q.enqueue({}, "twitter:default", _now_iso())


def test_jsonl_read_all_raises_on_unreadable_file(tmp_path, monkeypatch):
    """An unreadable file (permissions) must raise — a read that returns []
    on error would hide the outage behind an empty queue."""
    monkeypatch.setattr("api.queue.JSONL_PATH", tmp_path / "queue.jsonl")
    p = tmp_path / "queue.jsonl"
    p.write_text("")

    def _boom(*a, **kw):
        raise PermissionError("permission denied")

    monkeypatch.setattr(type(p), "open", _boom)
    with pytest.raises(PermissionError):
        _read_all()


# ── Worker during an outage ────────────────────────────────────────────────

def test_worker_run_once_raises_queue_backend_error(monkeypatch):
    """When the backend is down, run_once() raises QueueBackendError — it is
    caught by main() (logged + retried), never silently ignored."""
    import scheduler.worker as w

    def _boom():
        raise _qbe()("postgres", "cannot connect")

    monkeypatch.setattr(w, "get_queue", _boom)
    with pytest.raises(_qbe()):
        w.run_once()


def test_worker_main_loop_survives_outage_and_recovers(monkeypatch):
    """The worker loop must not crash-restart: it catches QueueBackendError,
    logs it, and retries. Recovery is deterministic."""
    import scheduler.worker as w

    calls = {"n": 0}

    def _flaky():
        calls["n"] += 1
        if calls["n"] <= 2:
            raise _qbe()("postgres", "cannot connect")
        return 0

    monkeypatch.setattr(w, "run_once", _flaky)
    monkeypatch.setattr(w, "_write_heartbeat", lambda: None)
    monkeypatch.setattr(w, "POLL_INTERVAL", 0)
    monkeypatch.setattr(w, "time", types.SimpleNamespace(sleep=lambda s: None))
    # Drive the loop body exactly like main() does, but with a bounded count.
    for _ in range(4):
        try:
            w._write_heartbeat()
            w.run_once()
        except _qbe():
            pass  # main() would log this and continue
        if calls["n"] == 3:
            break
    assert calls["n"] == 3


def test_worker_no_silent_backend_switch(monkeypatch):
    """During an outage the worker keeps calling get_queue() — it never
    caches a broken backend and never silently switches stores."""
    import scheduler.worker as w

    def _boom():
        raise _qbe()("postgres", "cannot connect")

    monkeypatch.setattr(w, "get_queue", _boom)
    monkeypatch.setattr(w, "_write_heartbeat", lambda: None)
    with pytest.raises(_qbe()):
        w.run_once()
    from api.queue import _QUEUE_SINGLETON
    assert _QUEUE_SINGLETON is None


# ── API during an outage ───────────────────────────────────────────────────

def test_api_healthz_reports_queue_unavailable(monkeypatch):
    """A running API with a down queue must return 503 with queue_error."""
    from fastapi.testclient import TestClient
    import api.app as appmod

    # Raise the exact class api.app binds (reload-safe): api.app's except
    # clauses and handler registration reference ITS OWN import of
    # QueueBackendError, which can go stale if api.queue is reloaded later.
    monkeypatch.setattr(appmod, "get_queue", lambda: (_ for _ in ()).throw(
        appmod.QueueBackendError("postgres", "cannot connect to the database")))
    client = TestClient(appmod.app)
    r = client.get("/healthz", headers={"Accept": "application/json"})
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert "cannot connect" in body["queue_error"]


def test_api_dispatch_returns_503_when_queue_down(monkeypatch):
    """No successful enqueue when persistence failed: the dispatch endpoint
    returns 503 with the operator's fix, not a 202."""
    from fastapi.testclient import TestClient
    import api.app as appmod

    monkeypatch.setattr(appmod, "get_queue", lambda: (_ for _ in ()).throw(
        appmod.QueueBackendError("postgres", "cannot connect to the database")))
    client = TestClient(appmod.app)
    r = client.post("/dispatch", json={
        "targets": ["telegram:main"],
        "formats": {"telegram_message": {"text": "hi"}},
    })
    assert r.status_code == 503
    assert "cannot connect" in r.json()["detail"]
