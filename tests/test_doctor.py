"""`dispatch doctor` + worker-heartbeat data-dir tests.

The doctor must read credentials from $OPEN_DISPATCH_DATA/.env the same way
the server does (file first, shell env wins), and the server's worker-status
probe must look for the heartbeat in the same directory the worker writes it
to — a repo-relative lookup reported live workers as "not running" whenever
the data dir moved (Docker /data, install.sh ~/.open-dispatch).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


# ── doctor: credentials ───────────────────────────────────────────────────────

def test_doctor_exits_1_when_nothing_configured(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    import cli
    args = cli.build_parser().parse_args(["--url", "http://localhost:1", "doctor"])
    assert cli.cmd_doctor(args) == 1
    out = capsys.readouterr().out
    assert "missing: BLUESKY_HANDLE" in out
    assert "No platform is fully configured" in out


def test_doctor_reads_env_file_and_reports_configured_platform(tmp_path, monkeypatch, capsys):
    (tmp_path / ".env").write_text(
        "BLUESKY_HANDLE=me.bsky.social\nBLUESKY_APP_PASSWORD=app-pass\n")
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    import cli
    args = cli.build_parser().parse_args(["--url", "http://localhost:1", "doctor"])
    assert cli.cmd_doctor(args) == 0
    out = capsys.readouterr().out
    assert "✓ bluesky" in out
    # Values must never be printed — only var names.
    assert "app-pass" not in out and "me.bsky.social" not in out


def test_doctor_shell_env_overrides_env_file(tmp_path, monkeypatch, capsys):
    (tmp_path / ".env").write_text("BLUESKY_HANDLE=file.bsky.social\n")
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    monkeypatch.setenv("BLUESKY_HANDLE", "shell.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "pw")
    import cli
    args = cli.build_parser().parse_args(["--url", "http://localhost:1", "doctor"])
    assert cli.cmd_doctor(args) == 0
    out = capsys.readouterr().out
    assert "✓ bluesky" in out
    assert "shell.bsky.social" not in out


def test_doctor_blank_env_file_value_falls_back_to_shell(tmp_path, monkeypatch, capsys):
    # A line like TELEGRAM_CHAT_ID= in .env must not mask a shell-provided value.
    (tmp_path / ".env").write_text("TELEGRAM_CHAT_ID=\n")
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    import cli
    args = cli.build_parser().parse_args(["--url", "http://localhost:1", "doctor"])
    assert cli.cmd_doctor(args) == 0
    out = capsys.readouterr().out
    assert "✓ telegram" in out


# ── doctor: server section ────────────────────────────────────────────────────

def test_doctor_reports_unreachable_server_as_warning(tmp_path, monkeypatch, capsys):
    (tmp_path / ".env").write_text("DISCORD_WEBHOOK_URL=https://example.com/hook\n")
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    import cli
    args = cli.build_parser().parse_args(["--url", "http://localhost:1", "doctor"])
    assert cli.cmd_doctor(args) == 0
    out = capsys.readouterr().out
    assert "not reachable" in out


def test_doctor_summarizes_healthz_json(tmp_path, monkeypatch, capsys):
    (tmp_path / ".env").write_text("TIKTOK_ACCESS_TOKEN=tok\n")
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    monkeypatch.delenv("OPEN_DISPATCH_API_TOKEN", raising=False)

    class FakeResponse:
        status_code = 200
        def raise_for_status(self) -> None: ...
        def json(self) -> dict:
            return {
                "status": "ok", "version": "0.4.0",
                "backend": "JSONL on disk",
                "worker": {"running": True, "label": "running"},
                "total": 3, "counts": {"published": 2, "queued": 1},
                "failed_count": 0, "configured_platforms": ["tiktok"],
            }

    import cli
    args = cli.build_parser().parse_args(["--url", "http://x", "doctor"])
    monkeypatch.setattr(cli.httpx, "get", lambda *a, **k: FakeResponse())
    assert cli.cmd_doctor(args) == 0
    out = capsys.readouterr().out
    assert "API v0.4.0" in out
    assert "worker" in out and "running" in out
    assert "published=2" in out


# ── doctor: profiles ─────────────────────────────────────────────────────────

def test_doctor_lists_profiles_with_configured_platforms(tmp_path, monkeypatch, capsys):
    (tmp_path / ".env").write_text("DISCORD_WEBHOOK_URL=https://example.com/hook\n")
    (tmp_path / "profiles.json").write_text(json.dumps({"profiles": [
        {"id": "p1", "name": "main", "emoji": "🦋",
         "platforms": {"bluesky": {"handle": "x", "app_password": "y"},
                       "telegram": {"bot_token": "", "chat_id": "123"}}},
    ]}))
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    import cli
    args = cli.build_parser().parse_args(["--url", "http://localhost:1", "doctor"])
    assert cli.cmd_doctor(args) == 0
    out = capsys.readouterr().out
    assert "🦋 main" in out
    assert "bluesky" in out


# ── worker heartbeat lives in the configured data dir ────────────────────────

def test_worker_status_reads_heartbeat_from_open_dispatch_data(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    from api import app as appmod
    fresh = datetime.now(tz=timezone.utc).isoformat()
    (tmp_path / ".worker_heartbeat").write_text(fresh)
    status = appmod._worker_status()
    assert status["running"] is True

    stale = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
    (tmp_path / ".worker_heartbeat").write_text(stale)
    assert appmod._worker_status()["label"] == "stale"

    (tmp_path / ".worker_heartbeat").unlink()
    assert appmod._worker_status()["running"] is False
