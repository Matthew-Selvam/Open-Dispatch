"""The CLI and MCP server must send Authorization when the server requires it.

The API gained optional bearer-token auth (OPEN_DISPATCH_API_TOKEN). Without
this, `dispatch send` and every MCP tool fail with 401 the moment a user
secures their instance.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cli  # noqa: E402

# mcp_server raises SystemExit at import time when the optional `mcp` extra is
# absent, and CI installs requirements.txt only — so import it defensively and
# skip the MCP half of this module rather than aborting collection.
try:
    import mcp_server  # noqa: E402
    MCP_AVAILABLE = True
except SystemExit:
    mcp_server = None  # type: ignore[assignment]
    MCP_AVAILABLE = False

requires_mcp = pytest.mark.skipif(not MCP_AVAILABLE, reason="mcp extra not installed")


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPEN_DISPATCH_API_TOKEN", raising=False)


# ── CLI ──────────────────────────────────────────────────────────────────────

def test_cli_headers_empty_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    assert cli._auth_headers() == {}


def test_cli_headers_carry_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_DISPATCH_API_TOKEN", "s3cret")
    assert cli._auth_headers() == {"Authorization": "Bearer s3cret"}


def test_cli_headers_ignore_blank_token(monkeypatch: pytest.MonkeyPatch) -> None:
    # A stray newline in .env must not produce "Bearer " with an empty secret.
    monkeypatch.setenv("OPEN_DISPATCH_API_TOKEN", "   ")
    assert cli._auth_headers() == {}


def test_cli_post_sends_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_DISPATCH_API_TOKEN", "s3cret")
    seen: dict = {}

    class FakeResp:
        status_code = 200

        def json(self) -> dict:
            return {"ok": True}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(cli.httpx, "post", fake_post)
    cli._post("http://x/dispatch", {"a": 1})
    assert seen["headers"] == {"Authorization": "Bearer s3cret"}


def test_cli_campaign_get_sends_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_DISPATCH_API_TOKEN", "s3cret")
    seen: dict = {}

    class FakeResp:
        status_code = 200

        def json(self) -> dict:
            return {"unit_id": "u1"}

    def fake_get(url, timeout=None, headers=None):
        seen["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(cli.httpx, "get", fake_get)
    args = cli.build_parser().parse_args(["campaign", "u1"])
    assert cli.cmd_campaign(args) == 0
    assert seen["headers"] == {"Authorization": "Bearer s3cret"}


def test_cli_explicit_flag_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_DISPATCH_API_TOKEN", "from-env")
    args = cli.build_parser().parse_args(["--token", "from-flag", "queue"])
    assert args.token == "from-flag"


def test_cli_token_defaults_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_DISPATCH_API_TOKEN", "from-env")
    args = cli.build_parser().parse_args(["queue"])
    assert args.token == "from-env"


def test_cli_token_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    args = cli.build_parser().parse_args(["queue"])
    assert args.token is None


def test_cli_headers_use_flag_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    assert cli._auth_headers("flag-token") == {"Authorization": "Bearer flag-token"}


# ── MCP server ───────────────────────────────────────────────────────────────

@requires_mcp
def test_mcp_headers_empty_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    assert mcp_server._auth_headers() == {}


@requires_mcp
def test_mcp_headers_carry_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_DISPATCH_API_TOKEN", "s3cret")
    assert mcp_server._auth_headers() == {"Authorization": "Bearer s3cret"}


@requires_mcp
def test_mcp_get_sends_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_DISPATCH_API_TOKEN", "s3cret")
    seen: dict = {}

    class FakeResp:
        status_code = 200
        text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"version": "0.4.0", "status": "ok"}

    def fake_get(url, params=None, headers=None, timeout=None):
        seen["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(mcp_server.httpx, "get", fake_get)
    mcp_server.health()
    assert seen["headers"]["Authorization"] == "Bearer s3cret"
    assert seen["headers"]["Accept"] == "application/json"


@requires_mcp
def test_mcp_post_sends_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_DISPATCH_API_TOKEN", "s3cret")
    seen: dict = {}

    class FakeResp:
        status_code = 200
        text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(mcp_server.httpx, "post", fake_post)
    mcp_server._post("/dispatch", {})
    assert seen["headers"]["Authorization"] == "Bearer s3cret"


@requires_mcp
def test_mcp_delete_sends_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_DISPATCH_API_TOKEN", "s3cret")
    seen: dict = {}

    class FakeResp:
        status_code = 200
        text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

    def fake_delete(url, headers=None, timeout=None):
        seen["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(mcp_server.httpx, "delete", fake_delete)
    mcp_server._delete("/queue/r1")
    assert seen["headers"]["Authorization"] == "Bearer s3cret"
