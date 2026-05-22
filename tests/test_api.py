"""API smoke tests via FastAPI TestClient."""

from __future__ import annotations

import importlib
import os

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    import api.queue as q
    importlib.reload(q)
    import api.app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient
    return TestClient(appmod.app)


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_dispatch_validation_error(client):
    r = client.post("/dispatch", json={"targets": [], "formats": {}})
    assert r.status_code == 400


def test_dispatch_enqueues(client):
    body = {
        "targets": ["telegram:main"],
        "formats": {"telegram_message": {"text": "hi"}},
    }
    r = client.post("/dispatch", json=body)
    assert r.status_code == 202
    j = r.json()
    assert "unit_id" in j
    assert len(j["enqueued"]) == 1
    assert j["enqueued"][0]["target"] == "telegram:main"


def test_queue_list(client):
    body = {"targets": ["telegram"], "formats": {"telegram_message": {"text": "x"}}}
    client.post("/dispatch", json=body)
    r = client.get("/queue")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_delete_row(client):
    body = {"targets": ["telegram"], "formats": {"telegram_message": {"text": "bye"}}}
    r = client.post("/dispatch", json=body)
    row_id = r.json()["enqueued"][0]["id"]
    # Row exists
    assert client.get(f"/queue/{row_id}/json").status_code == 200
    # Delete it
    dr = client.delete(f"/queue/{row_id}")
    assert dr.status_code == 200
    assert dr.json()["deleted"] == row_id
    # Gone
    assert client.get(f"/queue/{row_id}/json").status_code == 404


def test_delete_nonexistent(client):
    r = client.delete("/queue/no-such-id")
    assert r.status_code == 404


def test_purge_published(client):
    body = {"targets": ["telegram"], "formats": {"telegram_message": {"text": "x"}}}
    r = client.post("/dispatch", json=body)
    row_id = r.json()["enqueued"][0]["id"]
    # Mark it published via direct queue manipulation
    from api.queue import get_queue
    get_queue().mark_published(row_id, "post-123")
    # Purge published
    pr = client.post("/_purge?status=published")
    assert pr.status_code == 200
    assert pr.json()["purged"] == 1
    assert pr.json()["status"] == "published"
    # Verify gone
    assert client.get(f"/queue/{row_id}/json").status_code == 404


def test_purge_rejects_queued(client):
    """Can't purge active rows — only published or dead."""
    r = client.post("/_purge?status=queued")
    assert r.status_code == 400
