"""CLI campaign command tests."""

from __future__ import annotations

import cli


def test_campaign_local_status_and_cancel(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPEN_DISPATCH_DATA", str(tmp_path))
    import importlib
    import api.queue as queue
    importlib.reload(queue)
    monkeypatch.setattr(cli, "get_queue", queue.get_queue)

    unit = {"id": "cli-campaign", "targets": ["telegram"], "formats": {"telegram_message": {"text": "hi"}}}
    queue.get_queue().enqueue(unit, "telegram:default", "2026-01-01T00:00:00+00:00")
    args = cli.build_parser().parse_args(["campaign", "cli-campaign", "--local"])
    assert args.func(args) == 0
    assert "queued" in capsys.readouterr().out

    args = cli.build_parser().parse_args(["campaign", "cli-campaign", "--local", "--cancel"])
    assert args.func(args) == 0
    assert "canceled" in capsys.readouterr().out


def test_campaign_parser_accepts_cancel():
    args = cli.build_parser().parse_args(["campaign", "abc", "--cancel"])
    assert args.unit_id == "abc"
    assert args.cancel is True
