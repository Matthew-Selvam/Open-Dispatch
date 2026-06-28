"""Open-Dispatch MCP Server.

Exposes the Open-Dispatch REST API as MCP tools so AI agents (Claude, Cursor, etc.)
can post content, check queues, and retry failed jobs via natural language.

Usage:
  pip install mcp
  python mcp_server.py                        # stdio transport (Claude Desktop / Cursor)
  python mcp_server.py --transport sse        # SSE transport (browser / remote)

Claude Desktop config (~/.claude/claude_desktop_config.json):
  {
    "mcpServers": {
      "open-dispatch": {
        "command": "python",
        "args": ["/path/to/open-dispatch/mcp_server.py"],
        "env": { "OPEN_DISPATCH_URL": "http://localhost:8000" }
      }
    }
  }

Env:
  OPEN_DISPATCH_URL  — base URL of the running API (default: http://localhost:8000)
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

import httpx

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise SystemExit(
        "mcp package not installed. Run: pip install mcp\n"
        "Or: pip install 'open-dispatch[mcp]'"
    )

BASE_URL = os.getenv("OPEN_DISPATCH_URL", "http://localhost:8000").rstrip("/")

mcp = FastMCP(
    "open-dispatch",
    instructions=(
        "Open-Dispatch is a self-hosted social media cross-poster. "
        "Use dispatch() to post content to one or many platforms in one call. "
        "Platforms: twitter, bluesky, instagram, telegram, threads, linkedin, youtube, tiktok, facebook. "
        "Target syntax: 'platform' or 'platform:account'. "
        "Use get_queue() to monitor post status, retry_row() to retry failures."
    ),
)


def _get(path: str, **params: Any) -> dict:
    r = httpx.get(f"{BASE_URL}{path}", params=params, headers={"Accept": "application/json"}, timeout=15)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict | None = None) -> dict:
    r = httpx.post(f"{BASE_URL}{path}", json=body, headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()


def _delete(path: str) -> dict:
    r = httpx.delete(f"{BASE_URL}{path}", headers={"Accept": "application/json"}, timeout=15)
    r.raise_for_status()
    return r.json()


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
def health() -> str:
    """Check that Open-Dispatch is running and healthy."""
    data = _get("/healthz")
    return f"Open-Dispatch {data.get('version', '')} is {data.get('status', 'unknown')}."


@mcp.tool()
def dispatch(
    targets: list[str],
    formats: dict[str, Any],
    scheduled_for: str | None = None,
    category: str = "general",
    webhook_url: str | None = None,
) -> str:
    """Post content to one or many social platforms.

    Args:
        targets: List of platform targets, e.g. ["twitter", "bluesky", "telegram:channel"].
                 Supported platforms: twitter, bluesky, instagram, telegram, threads,
                 linkedin, youtube, tiktok, facebook.
        formats: Dict of format keys → payloads. Each platform needs its own key:
                 - twitter_thread:   {"tweets": ["text1", "text2"]}
                 - bluesky_post:     {"text": "..."}
                 - telegram_message: {"text": "...", "parse_mode": "HTML"}
                 - instagram_post:   {"caption": "...", "image_url": "https://..."}
                 - threads_post:     {"text": "..."}
                 - linkedin_post:    {"text": "..."}
                 - tiktok_post:      {"video_url": "https://...", "caption": "..."}
                 - facebook_post:    {"text": "...", "image_url": "https://..."}
        scheduled_for: ISO-8601 datetime to schedule post (omit to post immediately).
        category: Optional label for grouping posts (default "general").
        webhook_url: Optional URL to notify when post succeeds or fails.

    Returns:
        Summary of enqueued rows with their IDs and targets.
    """
    body: dict[str, Any] = {"targets": targets, "formats": formats, "category": category}
    if scheduled_for:
        body["scheduled_for"] = scheduled_for
    if webhook_url:
        body["webhook_url"] = webhook_url

    data = _post("/dispatch", body)
    rows = data.get("enqueued", [])
    lines = [f"Enqueued {len(rows)} row(s) — unit {data.get('unit_id', '')}:"]
    for row in rows:
        sched = f", scheduled {row['scheduled_for']}" if row.get("scheduled_for") else ""
        lines.append(f"  • {row['target']}  id={row['id']}{sched}")
    return "\n".join(lines)


@mcp.tool()
def get_queue(status: str = "queued") -> str:
    """List queue rows filtered by status.

    Args:
        status: One of: queued, publishing, published, failed, dead.
                Use 'all' to see everything.

    Returns:
        A formatted list of queue rows.
    """
    params: dict[str, Any] = {} if status == "all" else {"status": status}
    data = _get("/queue", **params)
    rows = data.get("rows", [])
    if not rows:
        return f"No rows with status '{status}'."
    lines = [f"{len(rows)} row(s) — status: {status}"]
    for r in rows[:20]:
        err = f" ✘ {r['last_error'][:80]}" if r.get("last_error") else ""
        lines.append(f"  [{r['status']}] {r['platform']}  id={r['id']}{err}")
    if len(rows) > 20:
        lines.append(f"  … and {len(rows) - 20} more")
    return "\n".join(lines)


@mcp.tool()
def get_row(row_id: str) -> str:
    """Get detailed info about a single queue row.

    Args:
        row_id: The queue row ID returned by dispatch().
    """
    data = _get(f"/queue/{row_id}")
    lines = [
        f"Row {row_id}",
        f"  status:   {data.get('status')}",
        f"  platform: {data.get('platform')}",
        f"  attempts: {data.get('attempts', 0)}",
        f"  post_id:  {data.get('post_id') or '—'}",
    ]
    if data.get("last_error"):
        lines.append(f"  error:    {data['last_error']}")
    return "\n".join(lines)


@mcp.tool()
def retry_row(row_id: str) -> str:
    """Retry a failed or dead queue row.

    Args:
        row_id: The queue row ID to retry.
    """
    data = _post(f"/queue/{row_id}/retry")
    return f"Row {row_id} reset to status '{data.get('status', 'queued')}'."


@mcp.tool()
def delete_row(row_id: str) -> str:
    """Permanently delete a queue row.

    Args:
        row_id: The queue row ID to delete.
    """
    _delete(f"/queue/{row_id}")
    return f"Row {row_id} deleted."


@mcp.tool()
def adapt_caption(text: str, platforms: list[str]) -> str:
    """Rewrite a caption for each target platform using AI.

    Uses Ollama → OpenRouter → heuristic fallback (always returns something).

    Args:
        text: The source caption to adapt.
        platforms: List of platform names to generate versions for,
                   e.g. ["twitter", "linkedin", "instagram"].

    Returns:
        Per-platform captions as formatted text.
    """
    data = _post("/ai/adapt", {"text": text, "platforms": platforms})
    lines = ["Adapted captions:"]
    for platform, caption in data.items():
        lines.append(f"\n{platform.upper()}:\n{caption}")
    return "\n".join(lines)


@mcp.tool()
def list_platforms() -> str:
    """List all supported platforms and their format keys."""
    platforms = [
        ("twitter",   "twitter_thread",   "tweets: list[str], media_paths?: list[str]"),
        ("bluesky",   "bluesky_post",     "text: str, images?: [{path, alt}]"),
        ("instagram", "instagram_post",   "caption: str, image_url: str"),
        ("telegram",  "telegram_message", "text: str, photo_path?: str, video_path?: str"),
        ("threads",   "threads_post",     "text: str, image_url?: str, video_url?: str"),
        ("linkedin",  "linkedin_post",    "text: str, asset_urn?: str"),
        ("youtube",   "youtube_short",    "video_path: str, title: str, description?: str"),
        ("tiktok",    "tiktok_post",      "video_url: str, caption?: str, privacy?: str"),
        ("facebook",  "facebook_post",    "text: str, image_url?: str, video_url?: str, link?: str"),
    ]
    lines = ["Supported platforms:\n"]
    for platform, fmt_key, fields in platforms:
        lines.append(f"  {platform:<12} format key: {fmt_key}")
        lines.append(f"               fields: {fields}\n")
    lines.append("Target syntax: 'platform' or 'platform:account'")
    lines.append("Multi-account: set PLATFORM_FIELD_ACCOUNT env vars (e.g. TWITTER_ACCESS_TOKEN_WORK)")
    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Open-Dispatch MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--port", type=int, default=8001, help="SSE server port (default 8001)")
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run(transport="stdio")
