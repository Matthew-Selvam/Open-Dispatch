"""Security + packaging hardening regressions.

Covers the fixes from the subagent review round: reflected XSS in the
row-detail 404, the /healthz HTML auth bypass, webhook egress pinning
(DNS-rebinding window), decimal-IP webhook hosts, profile-create id
takeover, cross-process JSONL queue safety, and the pip-install .env
loading path.
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

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


# ── reflected XSS in the row-detail 404 ───────────────────────────────────────

def test_row_404_escapes_row_id(client):
    payload = "%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E"
    r = client.get(f"/queue/{payload}", headers={"Accept": "text/html"})
    assert r.status_code == 404
    assert "<img" not in r.text
    assert "&lt;img" in r.text


# ── /healthz: JSON stays open for probes, HTML dashboard requires auth ───────

@pytest.fixture
def token_client(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    monkeypatch.setenv("OPEN_DISPATCH_API_TOKEN", "s3cret")
    import api.queue as q
    importlib.reload(q)
    import api.app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient
    yield TestClient(appmod.app)


def test_healthz_json_open_but_html_dashboard_gated(token_client):
    # Monitors / curl / dispatch doctor keep working without a token.
    r = token_client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    # A browser Accept header pulls the full dashboard (per-row adapter
    # errors) — that must authenticate like every other page.
    r2 = token_client.get("/healthz", headers={"Accept": "text/html"})
    assert r2.status_code == 401
    r3 = token_client.get("/")
    assert r3.status_code == 401
    r4 = token_client.get("/queue")
    assert r4.status_code == 401
    # And a token-bearing browser still gets the dashboard.
    r5 = token_client.get("/healthz", headers={
        "Accept": "text/html", "Authorization": "Bearer s3cret"})
    assert r5.status_code == 200


# ── webhook egress: validated-IP pinning ─────────────────────────────────────

def test_webhook_target_rejects_private_and_allows_public(monkeypatch):
    from scheduler import worker as w

    def loopback(host, port, type=None):
        return [(2, 1, 6, "", ("127.0.0.1", port))]

    monkeypatch.setattr(w.socket, "getaddrinfo", loopback)
    assert w._validated_webhook_target("https://example.com/hook") is None

    def public(host, port, type=None):
        return [(2, 1, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(w.socket, "getaddrinfo", public)
    assert w._validated_webhook_target("https://example.com/hook") == \
        ("93.184.216.34", "443")


def test_fire_webhook_pins_validated_ip(monkeypatch):
    from scheduler import worker as w
    monkeypatch.setattr(w.socket, "getaddrinfo",
                        lambda h, p, type=None: [(2, 1, 6, "", ("93.184.216.34", p))])
    captured: dict = {}

    def fake_post(url, **kw):
        captured.update(url=url, kw=kw)
        return object()

    monkeypatch.setattr(w.httpx, "post", fake_post)
    w._fire_webhook("https://example.com/hook?x=1", {"event": "published"})
    assert captured["url"].startswith("https://93.184.216.34:443/hook")
    assert captured["kw"]["extensions"] == {"sni_hostname": "example.com"}
    assert captured["kw"]["headers"] == {"Host": "example.com"}
    assert captured["kw"]["follow_redirects"] is False


def test_fire_webhook_fails_closed_without_sni_support(monkeypatch):
    from scheduler import worker as w
    monkeypatch.setattr(w.socket, "getaddrinfo",
                        lambda h, p, type=None: [(2, 1, 6, "", ("93.184.216.34", p))])

    def boom(url, **kw):
        raise TypeError("unexpected keyword argument")

    calls: list = []
    monkeypatch.setattr(w.httpx, "post", boom)
    # must not raise, and must not retry unpinned
    w._fire_webhook("https://example.com/hook", {"event": "published"})
    assert calls == []


def test_schema_rejects_decimal_and_hex_webhook_hosts():
    from api.schema import ContentUnit, validate
    for host in ("2130706433", "0x7f000001", "169.254.169.254"):
        unit = ContentUnit(targets=["bluesky"],
                           formats={"bluesky_post": {"text": "x"}},
                           webhook_url=f"https://{host}/hook")
        errs = validate(unit)
        assert any("not allowed" in e for e in errs), host


# ── profile create cannot hijack an existing id ──────────────────────────────

def test_profile_create_ignores_client_id(client):
    r = client.post("/profiles", data={
        "name": "first", "emoji": "🦋", "color": "#4ade80",
        "bluesky__handle": "h1", "bluesky__app_password": "p1",
    }, headers={"Accept": "text/html"})
    assert r.status_code in (200, 303)
    profiles = client.get("/api/profiles").json()
    assert len(profiles) == 1
    real_id = profiles[0]["id"]

    # A crafted create request reusing the id must NOT overwrite credentials.
    r2 = client.post("/profiles", data={
        "id": real_id, "name": "hijack", "color": "#000000",
        "bluesky__handle": "evil", "bluesky__app_password": "evil",
    }, headers={"Accept": "text/html"})
    assert r2.status_code in (200, 303)
    profiles = client.get("/api/profiles").json()
    assert len(profiles) == 2
    first = next(p for p in profiles if p["id"] == real_id)
    assert first["name"] == "first"


# ── JSONL queue survives two processes sharing one data dir ──────────────────

def test_jsonl_queue_survives_two_writers(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    # api.queue binds JSONL_PATH at import; earlier tests reloaded it against
    # their own tmp dirs, so rebind to this test's dir before asserting.
    import api.queue as qmod
    importlib.reload(qmod)
    repo_root = Path(__file__).resolve().parents[1]
    script = tmp_path / "writer.py"
    script.write_text(
        "import os, sys\n"
        f"os.environ['OPEN_DISPATCH_DATA'] = {str(tmp_path)!r}\n"
        f"sys.path.insert(0, {str(repo_root)!r})\n"
        "from api.queue import JsonlQueue\n"
        "q = JsonlQueue()\n"
        "for i in range(30):\n"
        "    rid = q.enqueue({'id': f'{os.getpid()}-{i}', 'targets': ['x'],"
        " 'formats': {}}, 'x:default', '2026-01-01T00:00:00+00:00')\n"
        "    q.mark_publishing(rid)\n"
        "    q.mark_failed(rid, 'boom', dead=True)\n"
    )
    procs = [subprocess.Popen([sys.executable, str(script)]) for _ in range(2)]
    for p in procs:
        p.wait(timeout=120)
    assert all(p.returncode == 0 for p in procs)

    from api.queue import JsonlQueue
    rows = qmod.JsonlQueue().list_all()
    assert len(rows) == 60, "cross-process writes lost rows"
    assert {r["status"] for r in rows} == {"dead"}


# ── pip-install path: api.app loads $OPEN_DISPATCH_DATA/.env ─────────────────

def test_app_loads_env_from_configured_data_dir(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("OPEN_DISPATCH_DOTENV_MARKER=loaded\n")
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    monkeypatch.delenv("OPEN_DISPATCH_DOTENV_MARKER", raising=False)
    import api.queue as q
    importlib.reload(q)
    import api.app as appmod
    importlib.reload(appmod)
    assert os.environ.get("OPEN_DISPATCH_DOTENV_MARKER") == "loaded"
    monkeypatch.delenv("OPEN_DISPATCH_DOTENV_MARKER", raising=False)


def test_app_does_not_load_home_dotenv_implicitly(tmp_path, monkeypatch):
    """No OPEN_DISPATCH_DATA → api.app must not silently load ~/.open-dispatch/.env.

    That fallback is reserved for the pip entry points (`cli.server`/`worker`);
    an import-time home fallback would leak a developer's real credentials
    into every test run and checkout.
    """
    monkeypatch.delenv("OPEN_DISPATCH_DATA", raising=False)
    monkeypatch.delenv("OPEN_DISPATCH_DOTENV_MARKER2", raising=False)
    import api.queue as q
    importlib.reload(q)
    import api.app as appmod
    importlib.reload(appmod)
    assert os.environ.get("OPEN_DISPATCH_DOTENV_MARKER2") is None
