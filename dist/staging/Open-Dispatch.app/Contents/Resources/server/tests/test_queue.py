"""Queue unit tests — uses tmp_path; no network."""

from __future__ import annotations

import importlib
import os
from datetime import datetime, timezone


def _fresh_queue(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    import api.queue as q
    importlib.reload(q)
    return q


def test_enqueue_and_list(tmp_path, monkeypatch):
    q = _fresh_queue(tmp_path, monkeypatch)
    queue = q.get_queue()
    rid = queue.enqueue({"id": "u1", "targets": ["telegram"], "formats": {"telegram_message": {"text": "hi"}}},
                        "telegram:default",
                        datetime.now(tz=timezone.utc).isoformat())
    rows = queue.list_all()
    assert len(rows) == 1
    assert rows[0]["id"] == rid
    assert rows[0]["status"] == "queued"
    assert rows[0]["platform"] == "telegram:default"


def test_due(tmp_path, monkeypatch):
    q = _fresh_queue(tmp_path, monkeypatch)
    queue = q.get_queue()
    past = "2020-01-01T00:00:00+00:00"
    future = "2099-01-01T00:00:00+00:00"
    queue.enqueue({"x": 1}, "telegram:default", past)
    queue.enqueue({"x": 2}, "telegram:default", future)
    due = queue.list_due(datetime.now(tz=timezone.utc).isoformat())
    assert len(due) == 1
    assert due[0]["scheduled_for"] == past


def test_status_transitions(tmp_path, monkeypatch):
    q = _fresh_queue(tmp_path, monkeypatch)
    queue = q.get_queue()
    rid = queue.enqueue({"x": 1}, "telegram:default",
                        datetime.now(tz=timezone.utc).isoformat())
    queue.mark_publishing(rid)
    assert queue.get(rid)["status"] == "publishing"
    queue.mark_published(rid, "post-99")
    row = queue.get(rid)
    assert row["status"] == "published"
    assert row["post_id"] == "post-99"


def test_mark_failed_then_dead(tmp_path, monkeypatch):
    q = _fresh_queue(tmp_path, monkeypatch)
    queue = q.get_queue()
    rid = queue.enqueue({"x": 1}, "telegram:default",
                        datetime.now(tz=timezone.utc).isoformat())
    queue.mark_failed(rid, "boom")
    assert queue.get(rid)["status"] == "queued"
    assert queue.get(rid)["attempts"] == 1
    queue.mark_failed(rid, "boom-2", dead=True)
    assert queue.get(rid)["status"] == "dead"
    assert queue.get(rid)["attempts"] == 2
