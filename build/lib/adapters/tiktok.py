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

from adapters.errors import AUTH, PERMANENT, PUBLISHED, RETRYABLE, classify, clip, prefix_error
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
            code = str(init_data["error"].get("code", "?"))
            msg = clip(init_data["error"].get("message", "unknown error"))
            # The init envelope used to be returned unclassified, so an auth
            # failure was retried twice before dead-lettering. Classify by
            # known codes: revoked/invalid token, rate limit, everything else
            # is a bad request.
            if code in ("access_token_invalid",):
                cls = AUTH
            elif code in ("rate_limit_exceeded", "22000"):
                cls = RETRYABLE
            else:
                cls = PERMANENT
            return False, "", prefix_error(cls, f"TikTok init error {code}: {msg}")

        publish_id = init_data.get("data", {}).get("publish_id", "")
        if not publish_id:
            # Init returned an ok envelope, so PULL_FROM_URL ingestion is
            # probably already running even though we cannot poll it.
            return False, "", prefix_error(
                PUBLISHED, "TikTok init ok but no publish_id; video may still publish")

        # Step 2 — poll for publish status (TikTok processes async).
        # From here on the video WILL go out: PULL_FROM_URL is already
        # ingesting. Any poll failure must never trigger a re-init, which
        # would post a second copy of the video.
        for _ in range(12):
            time.sleep(5)
            try:
                status_r = httpx.post(
                    f"{_BASE}/post/publish/status/fetch/",
                    headers=headers,
                    json={"publish_id": publish_id},
                    timeout=15,
                )
                status_r.raise_for_status()
                status_data = status_r.json()
            except Exception as e:  # noqa: BLE001
                return False, "", prefix_error(
                    PUBLISHED,
                    f"TikTok status poll failed after init (publish_id={publish_id}), "
                    f"video may publish, NOT retried: {clip(e)}")
            # A status response can carry an error envelope with HTTP 200.
            err_env = status_data.get("error")
            if err_env:
                code = err_env.get("code", "?")
                msg = err_env.get("message", "unknown")
                cls = classify(429 if str(code) == "22000" else None)
                return False, "", prefix_error(
                    cls, f"TikTok status error {code}: {msg} (publish_id={publish_id})")
            status = (status_data.get("data") or {}).get("status", "")
            if status == "PUBLISH_COMPLETE":
                # The field is a list in the API, but be defensive: a bare
                # string would index to its first CHARACTER and be returned as
                # the post id, and an empty list raised IndexError.
                ids = (status_data.get("data") or {}).get("publicaly_available_post_id") or []
                if isinstance(ids, str):
                    ids = [ids]
                if not ids:
                    return False, "", prefix_error(
                        PUBLISHED,
                        f"TikTok reports complete but no post id (publish_id={publish_id})")
                return True, str(ids[0]), ""
            if status in ("FAILED", "PUBLISH_FAILED"):
                reason = (status_data.get("data") or {}).get("fail_reason", "unknown")
                return False, "", prefix_error(
                    "retryable", f"TikTok publish failed: {reason} (publish_id={publish_id})")

        # Polls exhausted. The old code returned ok=True with publish_id, so a
        # video that never published was marked published and a published
        # webhook fired for it. publish_id is NOT a post id. Report it as
        # published-but-unconfirmed so the worker never retries into a double.
        return False, "", prefix_error(
            PUBLISHED,
            f"TikTok still processing after 12 polls; publish_id={publish_id} (not a post id)",
        )

    except httpx.HTTPStatusError as e:
        return False, "", prefix_error(
            classify(e.response.status_code),
            f"HTTP {e.response.status_code}: {clip(e.response.text)}",
        )
    except Exception as e:  # noqa: BLE001
        return False, "", prefix_error("retryable", f"tiktok error: {clip(e)}")
