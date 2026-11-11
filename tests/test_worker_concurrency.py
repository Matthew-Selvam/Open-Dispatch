"""PERF-2 worker concurrency tests — safe, configurable, measurable.

Concurrency must never duplicate-publish: each row is claimed atomically
(backend mark_publishing) inside its own task, and at most
WORKER_CONCURRENCY rows are claimed at once. A slow adapter must block only
its own slot, never the whole loop.
"""

from __future__ import annotations

import threading
import time as _time
import types
from datetime import datetime, timedelta, timezone

import pytest

import pytest

import scheduler.worker as w
from api.queue import JsonlQueue


@pytest.fixture
def env_data(tmp_path, monkeypatch):
    """Isolated JSONL queue for this test (JSONL_PATH is bound at module
    import, so it is rebound to the test's tmp dir — env alone is not enough)."""
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    import api.queue as qmod
    monkeypatch.setattr(qmod, "JSONL_PATH", tmp_path / "queue.jsonl")
    return tmp_path


def _due_iso(offset_min: float = -1) -> str:
    return (datetime.now(tz=timezone.utc) + timedelta(minutes=offset_min)).isoformat()


def _mk_queue(env_data) -> JsonlQueue:
    return JsonlQueue()


# ── WORKER_CONCURRENCY parsing ────────────────────────────────────────────

def test_concurrency_parse_defaults():
    assert w._parse_concurrency(None) == 1
    assert w._parse_concurrency("") == 1
    assert w._parse_concurrency("4") == 4


def test_concurrency_parse_invalid_falls_back_to_1_with_warning(monkeypatch, caplog):
    """A typo must not crash the worker, but must never be silent either."""
    with caplog.at_level("WARNING", logger="open-dispatch.worker"):
        assert w._parse_concurrency("abc") == 1
        assert w._parse_concurrency("0") == 1
        assert w._parse_concurrency("-3") == 1
    assert any("WORKER_CONCURRENCY" in r.message for r in caplog.records)


# ── slow adapter does not block unrelated rows ────────────────────────────

def _synthetic_adapter(sleep_s: float, log_calls: list, lock: threading.Lock):
    """Adapter stand-in: the ADAPTERS dict maps platform → module-like object
    exposing .publish(unit, account)."""
    def publish(unit, account=None):
        with lock:
            log_calls.append(("start", _time.monotonic(), unit.id))
        _time.sleep(sleep_s)
        with lock:
            log_calls.append(("end", _time.monotonic(), unit.id))
        return True, f"post-{unit.id}", ""
    return types.SimpleNamespace(publish=publish)


def test_slow_adapter_does_not_block_other_platforms(env_data, monkeypatch):
    """PERF-2 core defect: a slow adapter used to stall the whole serial loop.
    With concurrency=2 a slow row and a fast row OVERLAP — the fast row's
    publish starts before the slow row's publish ends."""
    monkeypatch.setattr(w, "WORKER_CONCURRENCY", 2)
    q = _mk_queue(env_data)
    slow_id = q.enqueue({"id": "slow", "targets": ["x"]}, "slowplat:default", _due_iso())
    fast_id = q.enqueue({"id": "fast", "targets": ["x"]}, "fastplat:default", _due_iso())

    calls: list = []
    lock = threading.Lock()
    monkeypatch.setattr(w, "ADAPTERS", {
        "slowplat": _synthetic_adapter(0.4, calls, lock),
        "fastplat": _synthetic_adapter(0.01, calls, lock),
    })
    t0 = _time.monotonic()
    w.run_once()
    elapsed = _time.monotonic() - t0

    rows = {r["id"]: r for r in q.list_all()}
    assert rows[slow_id]["status"] == "published"
    assert rows[fast_id]["status"] == "published"

    starts = {u: t for kind, t, u in calls if kind == "start"}
    ends = {u: t for kind, t, u in calls if kind == "end"}
    # Overlap proof (deterministic, no wall-clock threshold): the fast row
    # started before the slow row finished.
    assert starts["fast"] < ends["slow"], "fast publish did not overlap the slow one"


def test_concurrency_does_not_duplicate_publish(env_data, monkeypatch):
    """Each row is published exactly once under concurrency — claims stay
    atomic and no row is ever processed twice."""
    monkeypatch.setattr(w, "WORKER_CONCURRENCY", 4)
    q = _mk_queue(env_data)
    ids = [q.enqueue({"id": f"u{i}", "targets": ["x"]}, "p:default", _due_iso())
           for i in range(12)]

    publishes: list[str] = []
    lock = threading.Lock()

    def publish(unit, account=None):
        with lock:
            publishes.append(unit.id)
        return True, f"post-{unit.id}", ""

    monkeypatch.setattr(w, "ADAPTERS", {"p": types.SimpleNamespace(publish=publish)})
    monkeypatch.setattr(w, "get_queue", lambda: q)
    w.run_once()

    unit_ids = sorted(f"u{i}" for i in range(12))
    assert sorted(publishes) == unit_ids, "every row published exactly once"
    assert len(publishes) == 12
    rows = q.list_all()
    assert len(rows) == 12
    assert {r["status"] for r in rows} == {"published"}


def test_concurrency_bounds_outstanding_claims(env_data, monkeypatch):
    """At most WORKER_CONCURRENCY rows are claimed at any moment: the claim
    happens inside the task, so the pool bounds outstanding claims."""
    monkeypatch.setattr(w, "WORKER_CONCURRENCY", 2)
    q = _mk_queue(env_data)
    for i in range(6):
        q.enqueue({"id": f"u{i}", "targets": ["x"]}, "p:default", _due_iso())

    state = {"in_publish": 0, "max_in_publish": 0}
    lock = threading.Lock()

    def publish(unit, account=None):
        with lock:
            state["in_publish"] += 1
            state["max_in_publish"] = max(state["max_in_publish"], state["in_publish"])
        _time.sleep(0.02)
        with lock:
            state["in_publish"] -= 1
        return True, "post", ""
    adapter = types.SimpleNamespace(publish=publish)

    monkeypatch.setattr(w, "ADAPTERS", {"p": adapter})
    monkeypatch.setattr(w, "get_queue", lambda: q)
    w.run_once()
    assert state["max_in_publish"] <= 2


def test_serial_mode_unchanged_when_concurrency_1(env_data, monkeypatch):
    """WORKER_CONCURRENCY=1 (default) must behave exactly like the old serial
    loop — backwards compatibility."""
    monkeypatch.setattr(w, "WORKER_CONCURRENCY", 1)
    q = _mk_queue(env_data)
    rid = q.enqueue({"id": "u", "targets": ["x"]}, "p:default", _due_iso())

    calls: list = []

    def publish(unit, account=None):
        calls.append(unit.id)
        return True, "post", ""

    monkeypatch.setattr(w, "ADAPTERS", {"p": types.SimpleNamespace(publish=publish)})
    monkeypatch.setattr(w, "get_queue", lambda: q)
    w.run_once()
    assert calls == ["u"]
    assert q.get(rid)["status"] == "published"


def test_adapter_exception_under_concurrency_is_recorded(env_data, monkeypatch):
    """A raising adapter under concurrency still becomes a recorded failure —
    no row is stranded in 'publishing' (the v0.4.1 invariant)."""
    monkeypatch.setattr(w, "WORKER_CONCURRENCY", 2)
    q = _mk_queue(env_data)
    rid = q.enqueue({"id": "boom", "targets": ["x"]}, "p:default", _due_iso())

    def boom(unit, account=None):
        raise ValueError("invalid literal for int(): 'abc'")

    monkeypatch.setattr(w, "ADAPTERS", {"p": types.SimpleNamespace(publish=boom)})
    monkeypatch.setattr(w, "get_queue", lambda: q)
    w.run_once()
    row = q.get(rid)
    assert row["status"] == "queued"  # retried with backoff
    assert "adapter raised ValueError" in row["last_error"]


def test_graceful_shutdown_waits_for_inflight_publish(env_data, monkeypatch):
    """On shutdown (KeyboardInterrupt reaches main()) in-flight publishes must
    finish and commit their state — no row orphaned mid-publish."""
    monkeypatch.setattr(w, "WORKER_CONCURRENCY", 2)
    q = _mk_queue(env_data)
    rid = q.enqueue({"id": "inflight", "targets": ["x"]}, "p:default", _due_iso())

    finished = threading.Event()

    def slow_publish(unit, account=None):
        _time.sleep(0.25)
        finished.set()
        return True, "post", ""

    monkeypatch.setattr(w, "ADAPTERS", {"p": types.SimpleNamespace(publish=slow_publish)})
    monkeypatch.setattr(w, "get_queue", lambda: q)

    # Reproduce the executor block from run_once and interrupt the submitting
    # thread mid-flight: the `with` block must wait for the running task.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="od-publish") as pool:
        fut = pool.submit(w._process_row, q, q.get(rid))
        # KeyboardInterrupt "arrives" while the publish is in flight —
        # simulating main()'s exit path, which leaves the with-block.
        assert not finished.is_set()
        fut.result(timeout=5)  # executor join == graceful shutdown
    assert finished.is_set()
    assert q.get(rid)["status"] == "published"
