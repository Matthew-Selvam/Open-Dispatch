"""TikTok adapter — Content Posting API v2.

Env (per account suffix; uppercase):
  TIKTOK_ACCESS_TOKEN[_<ACCT>]   — OAuth 2.0 user token (scope: video.publish)
  TIKTOK_PRIVACY_LEVEL           — default privacy: PUBLIC_TO_EVERYONE | MUTUAL_FOLLOW_FRIENDS | SELF_ONLY
                                    (default: PUBLIC_TO_EVERYONE)

Format key: `tiktok_post`
  video_url  (required) — publicly accessible URL to the .mp4; TikTok pulls it directly
  caption    (optional) — up to 2200 chars
  privacy    (optional) — overrides TIKTOK_PRIVACY_LEVEL for this post

Requires the TikTok Content Posting API v2 (apply at developers.tiktok.com).
Access token must have scope: video.publish
"""

from __future__ import annotations

import logging
import os
import time

import httpx

from api.schema import ContentUnit

log = logging.getLogger("open-dispatch.tiktok")

_BASE = "https://open.tiktokapis.com/v2"


def _token(account: str | None) -> str:
    suffix = f"_{account.upper()}" if account else ""
    return os.getenv(f"TIKTOK_ACCESS_TOKEN{suffix}") or os.getenv("TIKTOK_ACCESS_TOKEN", "")


def publish(unit: ContentUnit, account: str | None = None) -> tuple[bool, str, str]:
    token = _token(account)
    if not token:
        return False, "", "TIKTOK_ACCESS_TOKEN missing"

    fmt = unit.formats.get("tiktok_post") or {}
    video_url = (fmt.get("video_url") or "").strip()
    if not video_url:
        return False, "", "tiktok_post.video_url is required"

    caption = (fmt.get("caption") or "")[:2200]
    privacy = (
        fmt.get("privacy")
        or os.getenv("TIKTOK_PRIVACY_LEVEL", "PUBLIC_TO_EVERYONE")
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    try:
        # Step 1 — initialise the post (PULL_FROM_URL = TikTok fetches video itself)
        init_r = httpx.post(
            f"{_BASE}/post/publish/video/init/",
            headers=headers,
            json={
                "post_info": {
                    "title": caption,
                    "privacy_level": privacy,
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                    "video_cover_timestamp_ms": 1000,
                },
                "source_info": {
                    "source": "PULL_FROM_URL",
                    "video_url": video_url,
                },
            },
            timeout=30,
        )
        init_r.raise_for_status()
        init_data = init_r.json()

        if init_data.get("error", {}).get("code", "ok") != "ok":
            msg = init_data["error"].get("message", "unknown error")
            return False, "", f"TikTok init error: {msg}"

        publish_id = init_data.get("data", {}).get("publish_id", "")
        if not publish_id:
            return False, "", "TikTok returned no publish_id"

        # Step 2 — poll for publish status (TikTok processes async)
        for _ in range(12):
            time.sleep(5)
            status_r = httpx.post(
                f"{_BASE}/post/publish/status/fetch/",
                headers=headers,
                json={"publish_id": publish_id},
                timeout=15,
            )
            status_r.raise_for_status()
            status_data = status_r.json()
            status = status_data.get("data", {}).get("status", "")
            if status == "PUBLISH_COMPLETE":
                post_id = str(status_data.get("data", {}).get("publicaly_available_post_id", [publish_id])[0])
                return True, post_id, ""
            if status in ("FAILED", "PUBLISH_FAILED"):
                reason = status_data.get("data", {}).get("fail_reason", "unknown")
                return False, "", f"TikTok publish failed: {reason}"

        # Timed out polling — post is likely still processing
        return True, publish_id, ""

    except httpx.HTTPStatusError as e:
        return False, "", f"HTTP {e.response.status_code}: {e.response.text[:300]}"
    except Exception as e:  # noqa: BLE001
        return False, "", f"tiktok error: {e}"
