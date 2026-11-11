"""Adapter/worker duplicate-post + classification regressions.

From the adapters/worker review round: the "post went out, never retry"
convention (PUBLISHED class) was not applied consistently to Threads, TikTok
and Instagram publish steps, Facebook/TikTok auth errors were retried, the
worker aborted its whole poll cycle on a webhook URL with a malformed port,
and a hard crash mid-publish stranded rows in "publishing" with no way back.
"""
from __future__ import annotations

import importlib
import sys
import time
import types
from datetime import datetime, timedelta, timezone

import httpx
import pytest


@pytest.fixture
def env_data(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    import api.queue as q
    importlib.reload(q)
    return tmp_path


# ── threads: publish-step ambiguity is `published`, never retried ────────────

def test_threads_publish_network_error_is_published_not_retried(monkeypatch):
    from adapters import threads

    # create succeeds; the PUBLISH call dies with a network error — that is
    # the ambiguity that must be classified `published`.
    def handler(url):
        if "threads_publish" in url:
            raise httpx.ConnectError("connection reset")
        class R:
            status_code = 200
            text = ""
            def json(self): return {"id": "cont-1"}
        return R()

    class FakeClient:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, **kw): return handler(url)

    monkeypatch.setattr(threads.httpx, "Client", lambda **kw: FakeClient())
    monkeypatch.setenv("THREADS_USER_ID", "u")
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "t")
    monkeypatch.setenv("THREADS_SETTLE_SECONDS", "0")
    unit = _unit({"threads_post": {"text": "hi"}})
    ok, _, err = threads.publish(unit)
    assert not ok
    assert err.startswith("published:"), err


def test_threads_publish_5xx_and_missing_id_are_published(monkeypatch):
    from adapters import threads

    monkeypatch.setenv("THREADS_USER_ID", "u")
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "t")
    monkeypatch.setenv("THREADS_SETTLE_SECONDS", "0")

    def make_client(handler):
        class FakeClient:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def post(self, url, **kw):
                return handler(url)
        return FakeClient()

    # create succeeds (with a container id); publish 500s
    calls = {"n": 0}
    def handler_500(url):
        calls["n"] += 1
        class R:
            status_code = 200 if "threads_publish" not in url else 500
            text = "boom"
            def json(self):
                if "threads_publish" not in url:
                    return {"id": "cont-1"}
                raise ValueError("no body")
        return R()
    monkeypatch.setattr(threads.httpx, "Client", lambda **kw: make_client(handler_500))
    unit = _unit({"threads_post": {"text": "hi"}})
    ok, _, err = threads.publish(unit)
    assert not ok
    assert err.startswith("published:"), err

    # create succeeds; publish returns 200 with no id
    def handler_no_id(url):
        class R:
            status_code = 200
            text = "{}"
            def json(self):
                if "threads_publish" not in url:
                    return {"id": "cont-1"}
                return {}
        return R()
    monkeypatch.setattr(threads.httpx, "Client", lambda **kw: make_client(handler_no_id))
    ok, _, err = threads.publish(unit)
    assert not ok
    assert err.startswith("published:"), err


# ── tiktok: post-init failures never re-init ────────────────────────────────

def test_tiktok_poll_failure_after_init_is_published(monkeypatch):
    from adapters import tiktok

    calls: list[str] = []

    def fake_post(url, **kw):
        calls.append(url)
        if "init" in url:
            class InitR:
                status_code = 200
                text = ""
                def raise_for_status(self): pass
                def json(self):
                    return {"error": {"code": "ok"},
                            "data": {"publish_id": "pid-1"}}
            return InitR()

        class StatusR:
            status_code = 500
            text = "boom"
            def raise_for_status(self):
                raise httpx.HTTPStatusError("500", request=None, response=None)
            def json(self):
                return {}
        return StatusR()

    monkeypatch.setattr(tiktok.httpx, "post", fake_post)
    monkeypatch.setattr(tiktok.time, "sleep", lambda s: None)
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "t")
    unit = _unit({"tiktok_post": {"video_url": "https://cdn.example/v.mp4"}})
    ok, _, err = tiktok.publish(unit)
    assert not ok
    assert err.startswith("published:"), err
    # Only ONE init call: the poll failure must not re-init a second video.
    assert sum("init" in c for c in calls) == 1


def test_tiktok_init_auth_error_is_auth(monkeypatch):
    from adapters import tiktok

    def fake_post(url, **kw):
        class InitR:
            status_code = 200
            text = ""
            def raise_for_status(self): pass
            def json(self):
                return {"error": {"code": "access_token_invalid",
                                  "message": "bad token"}}
        return InitR()

    monkeypatch.setattr(tiktok.httpx, "post", fake_post)
    monkeypatch.setattr(tiktok.time, "sleep", lambda s: None)
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "t")
    unit = _unit({"tiktok_post": {"video_url": "https://cdn.example/v.mp4"}})
    ok, _, err = tiktok.publish(unit)
    assert not ok
    assert err.startswith("auth:"), err


# ── instagram: media_publish failures after container creation ──────────────

def test_instagram_media_publish_5xx_is_published(monkeypatch):
    from adapters import instagram

    def fake_post(url, **kw):
        if "media_publish" in url:
            class PubR:
                status_code = 500
                text = "boom"
                def json(self): return {}
            return PubR()
        class CR:
            status_code = 200
            text = ""
            def json(self): return {"id": "cont-1"}
        return CR()

    monkeypatch.setattr(instagram.httpx, "post", fake_post)
    monkeypatch.setattr(instagram, "_wait_for_container", lambda cid, tok: (True, ""))
    monkeypatch.setenv("IG_USER_ID", "u")
    monkeypatch.setenv("IG_TOKEN", "t")
    unit = _unit({"instagram_post": {"image_url": "https://cdn.example/i.jpg"}})
    ok, _, err = instagram.publish(unit)
    assert not ok
    assert err.startswith("published:"), err


def test_instagram_media_publish_200_no_id_is_published(monkeypatch):
    from adapters import instagram

    def fake_post(url, **kw):
        if "media_publish" in url:
            class PubR:
                status_code = 200
                text = "{}"
                def json(self): return {}
            return PubR()
        class CR:
            status_code = 200
            text = ""
            def json(self): return {"id": "cont-1"}
        return CR()

    monkeypatch.setattr(instagram.httpx, "post", fake_post)
    monkeypatch.setattr(instagram, "_wait_for_container", lambda cid, tok: (True, ""))
    monkeypatch.setenv("IG_USER_ID", "u")
    monkeypatch.setenv("IG_TOKEN", "t")
    unit = _unit({"instagram_post": {"image_url": "https://cdn.example/i.jpg"}})
    ok, _, err = instagram.publish(unit)
    assert not ok
    assert err.startswith("published:"), err


# ── facebook / twitter / bluesky classification ──────────────────────────────

def test_facebook_401_is_auth(monkeypatch):
    from adapters import facebook

    req = httpx.Request("POST", "https://graph.facebook.com/x")
    resp = httpx.Response(401, request=req, text='{"error":{"message":"bad token"}}')

    def fake_post(*a, **kw):
        raise httpx.HTTPStatusError("401", request=req, response=resp)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "p")
    monkeypatch.setenv("FACEBOOK_ACCESS_TOKEN", "t")
    unit = _unit({"facebook_post": {"text": "hi"}})
    ok, _, err = facebook.publish(unit)
    assert not ok
    assert err.startswith("auth:"), err


def test_twitter_unauthorized_is_auth(monkeypatch):
    import tweepy
    from adapters import twitter

    resp = types.SimpleNamespace(
        status=401, status_code=401, headers={}, text="401 Unauthorized",
        json=lambda: {"errors": [{"code": 32, "message": "Could not authenticate"}]},
        content=b'{"errors":[]}', url="https://api.x.com/2/tweets",
        reason="Unauthorized", elapsed=0.0)
    class FakeClient:
        def __init__(self, **kw): pass
        def create_tweet(self, **kw):
            raise tweepy.Unauthorized(resp)

    shim = _FakeTweepy(tweepy, FakeClient)
    monkeypatch.setitem(sys.modules, "tweepy", shim)
    for var in ("TWITTER_API_KEY", "TWITTER_API_SECRET",
                "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"):
        monkeypatch.setenv(var, "x")
    unit = _unit({"twitter_thread": {"tweets": ["hi"]}})
    ok, _, err = twitter.publish(unit)
    assert not ok
    assert err.startswith("auth:"), err


def test_bluesky_login_failure_is_auth(monkeypatch):
    from atproto_client.exceptions import UnauthorizedError
    from adapters import bluesky

    resp = types.SimpleNamespace(status_code=401, headers={"x": "y"},
                                 url="https://bsky", reason="unauthorized",
                                 content={"error": "invalid_grant",
                                          "message": "bad app password"})
    class FakeClient:
        def login(self, *a, **kw):
            raise UnauthorizedError(resp)

    import sys
    fake_atproto = type(sys)("fake_atproto")
    fake_atproto.Client = FakeClient
    fake_atproto.client_utils = type(sys)("fake_atproto.client_utils")
    monkeypatch.setitem(sys.modules, "atproto", fake_atproto)
    monkeypatch.setenv("BLUESKY_HANDLE", "h")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "p")
    unit = _unit({"bluesky_post": {"text": "hi"}})
    ok, _, err = bluesky.publish(unit)
    assert not ok
    assert err.startswith("auth:"), err


class _FakeTweepy:
    """Module shim so the adapter's `import tweepy` sees the real classes."""
    def __init__(self, real, client_cls):
        self.Unauthorized = real.Unauthorized
        self.Forbidden = real.Forbidden
        self.TooManyRequests = real.TooManyRequests
        self.Client = client_cls
        self.API = real.API
        self.OAuth1UserHandler = real.OAuth1UserHandler


def _unit(formats: dict):
    from api.schema import ContentUnit
    return ContentUnit(targets=["bluesky"], formats=formats)


# ── telegram: chunks never split a tag or entity ─────────────────────────────

def test_telegram_chunk_never_splits_tags_or_entities():
    from adapters.telegram import _chunk
    text = "a" * 100 + "<b>bold</b>" + "b" * 100 + "&#8205;" + "c" * 100
    for piece in _chunk(text, 120):
        # no piece ends inside a tag or entity
        assert piece.count("<") == piece.count(">"), piece[-30:]
        assert not piece.endswith("&"), piece[-10:]
        if "&" in piece:
            after = piece[piece.rfind("&"):]
            assert ";" in after or len(after) < 12, piece[-30:]
    assert "".join(_chunk(text, 120)) == text


# ── worker: webhook edge cases + stale-claim reaper ──────────────────────────

def test_webhook_invalid_port_does_not_abort_poll(monkeypatch):
    from scheduler import worker as w

    # Malformed port must resolve to "rejected", not raise out of run_once.
    assert w._validated_webhook_target("https://example.com:abc/hook") is None


def test_webhook_ipv6_target_is_bracketed(monkeypatch):
    from scheduler import worker as w
    monkeypatch.setattr(w.socket, "getaddrinfo",
                        lambda h, p, type=None: [(10, 1, 6, "", ("2606:4700:4700::1111", p))])
    captured: dict = {}

    def fake_post(url, **kw):
        captured.update(url=url, kw=kw)
        return object()

    monkeypatch.setattr(w.httpx, "post", fake_post)
    w._fire_webhook("https://example.com:8443/hook", {"event": "published"})
    assert captured["url"].startswith("https://[2606:4700:4700::1111]:8443/hook")
    assert captured["kw"]["headers"] == {"Host": "example.com:8443"}


def test_reaper_quarantines_stale_publishing_claims(env_data, monkeypatch):
    from api.queue import JsonlQueue
    from scheduler.worker import run_once

    q = JsonlQueue()
    stale = q.enqueue({"id": "u-stale", "targets": ["x"], "formats": {}},
                      "x:default", "2026-01-01T00:00:00+00:00")
    fresh = q.enqueue({"id": "u-fresh", "targets": ["x"], "formats": {}},
                      "x:default", "2027-01-01T00:00:00+00:00")
    assert q.mark_publishing(stale)
    # fresh is scheduled 2027 — not due, so it can't be claimed (by design)
    assert not q.mark_publishing(fresh)
    # Backdate the stale row beyond the lease — but _update() stamps
    # updated_at with now(), so rewrite the JSONL directly.
    import json as _json
    old = (datetime.now(tz=timezone.utc) - timedelta(seconds=3600)).isoformat()
    jsonl = env_data / "queue.jsonl"
    rows = [_json.loads(line) for line in jsonl.read_text().splitlines() if line.strip()]
    for r in rows:
        if r["id"] == stale:
            r["updated_at"] = old
    jsonl.write_text("".join(_json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

    monkeypatch.setenv("WORKER_PUBLISHING_LEASE", "900")
    import scheduler.worker as w
    import api.queue as qmod
    # run_once binds get_queue at import; point it at the reloaded module so
    # it reads the same tmp data dir this test set up.
    monkeypatch.setattr(w, "get_queue", qmod.get_queue)
    monkeypatch.setattr(w, "PUBLISHING_LEASE", 900)

    # Quarantine semantics: the reaped row must land in "failed" with the
    # verify-before-retry error, and run_once() must NOT re-publish it —
    # the platform may have accepted the post before the worker died.
    reaped = q.reap_stale_publishing(900)
    assert reaped == [stale]
    quarantined = q.get(stale)
    assert quarantined["status"] == "failed"
    assert "verify on the platform before retrying" in quarantined["last_error"]
    assert quarantined["attempts"] == 0, "quarantine must not burn an attempt"

    run_once()  # must skip the quarantined row entirely
    rows = {r["id"]: r for r in q.list_all()}
    assert rows[stale]["status"] == "failed", "quarantined row was re-published"
    assert rows[stale]["attempts"] == 0

    # Explicit retry() after operator verification re-queues it normally.
    assert q.retry(stale)
    assert q.get(stale)["status"] == "queued"

    # The fresh claim (2027, far future) must never have been picked up.
    assert rows[fresh]["status"] == "queued"
    assert rows[fresh]["attempts"] == 0


def test_reaper_leaves_fresh_claims_alone(env_data):
    from api.queue import JsonlQueue

    q = JsonlQueue()
    rid = q.enqueue({"id": "u", "targets": ["x"], "formats": {}},
                    "x:default", "2026-01-01T00:00:00+00:00")
    assert q.mark_publishing(rid)
    reaped = q.reap_stale_publishing(900)
    assert reaped == []
    assert q.get(rid)["status"] == "publishing"
