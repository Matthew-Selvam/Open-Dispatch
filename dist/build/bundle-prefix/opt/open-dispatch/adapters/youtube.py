"""YouTube Shorts adapter — videos.insert via YouTube Data API v3 resumable upload.

To qualify as a Short:
  - Video duration ≤ 60 seconds (we don't validate; YouTube does)
  - Aspect ratio 9:16 (vertical) — YouTube auto-detects
  - Optionally include #Shorts in the title or description

OAuth2 setup (do this once, manually):
  1. Create a project at https://console.cloud.google.com
  2. Enable "YouTube Data API v3"
  3. Create OAuth 2.0 Client ID (Desktop or Web) — get client_id + client_secret
  4. Run the included `dispatch youtube-auth` flow (or any tool that produces a
     refresh_token with scope https://www.googleapis.com/auth/youtube.upload)
  5. Drop the refresh_token into YOUTUBE_REFRESH_TOKEN (+ id/secret in env)

Env (per account suffix; uppercase):
  YOUTUBE_CLIENT_ID
  YOUTUBE_CLIENT_SECRET
  YOUTUBE_REFRESH_TOKEN[_<ACCT>]

Format key: `youtube_short`
  video_path: str (required — local file path)
  title:      str (default first 100 chars of caption; YouTube max 100)
  description:str (default caption; YouTube max 5000)
  tags:       list[str] (optional)
  privacy:    "public" | "unlisted" | "private"  (default "public")
  caption:    str   — convenience field; used if title/description not given
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any

import httpx

from api.schema import CAPTION_LIMITS, ContentUnit

log = logging.getLogger("open-dispatch.youtube")

OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def _creds(account: str | None) -> tuple[str, str, str]:
    suffix = f"_{account.upper()}" if account else ""
    client_id = os.getenv("YOUTUBE_CLIENT_ID", "")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "")
    refresh = (
        os.getenv(f"YOUTUBE_REFRESH_TOKEN{suffix}")
        or os.getenv("YOUTUBE_REFRESH_TOKEN", "")
    )
    return client_id, client_secret, refresh


def _refresh_access_token(client: httpx.Client, client_id: str, client_secret: str,
                          refresh_token: str) -> tuple[str | None, str]:
    """Exchange a refresh token for a fresh access token. Returns (token, err)."""
    try:
        r = client.post(
            OAUTH_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
    except httpx.HTTPError as e:
        return None, f"token refresh network error: {e}"
    if r.status_code >= 400:
        return None, f"token refresh HTTP {r.status_code}: {r.text[:200]}"
    try:
        return r.json().get("access_token"), ""
    except ValueError:
        return None, "token refresh: non-JSON response"


def _build_metadata(fmt: dict[str, Any]) -> dict[str, Any]:
    caption = (fmt.get("caption") or "").strip()
    title = (fmt.get("title") or caption[:100] or "Untitled").strip()[:100]
    description_raw = fmt.get("description") or caption or ""
    description = description_raw.strip()[: CAPTION_LIMITS["youtube"]]

    # If the user didn't tag it as a Short anywhere, auto-add #Shorts to the
    # description so YouTube classifies it correctly.
    if "#shorts" not in (title.lower() + " " + description.lower()):
        # Stay under the 5000-char description cap
        suffix = "\n\n#Shorts"
        if len(description) + len(suffix) <= CAPTION_LIMITS["youtube"]:
            description += suffix

    tags = fmt.get("tags") or []
    privacy = (fmt.get("privacy") or "public").lower()
    if privacy not in {"public", "unlisted", "private"}:
        privacy = "public"

    snippet: dict[str, Any] = {
        "title": title,
        "description": description,
        "categoryId": fmt.get("category_id", "22"),  # 22 = People & Blogs
    }
    if tags:
        snippet["tags"] = [str(t) for t in tags][:30]

    return {
        "snippet": snippet,
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }


def publish(unit: ContentUnit, account: str | None = None) -> tuple[bool, str, str]:
    fmt = unit.formats.get("youtube_short") or {}
    video_path = fmt.get("video_path")
    if not video_path:
        return False, "", "youtube_short.video_path is required"
    p = Path(video_path)
    if not p.exists() or not p.is_file():
        return False, "", f"video_path does not exist: {video_path}"

    client_id, client_secret, refresh_token = _creds(account)
    if not (client_id and client_secret and refresh_token):
        return (
            False, "",
            "YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN missing"
        )

    metadata = _build_metadata(fmt)
    mime_type = mimetypes.guess_type(str(p))[0] or "video/mp4"

    with httpx.Client() as client:
        access_token, err = _refresh_access_token(client, client_id, client_secret, refresh_token)
        if not access_token:
            return False, "", err

        # Step 1 — initiate the resumable upload session
        try:
            r = client.post(
                UPLOAD_URL,
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": mime_type,
                    "X-Upload-Content-Length": str(p.stat().st_size),
                },
                content=json.dumps(metadata),
                timeout=30,
            )
        except httpx.HTTPError as e:
            return False, "", f"initiate upload network error: {e}"
        if r.status_code >= 400:
            return False, "", f"initiate upload HTTP {r.status_code}: {r.text[:300]}"
        upload_session_url = r.headers.get("location")
        if not upload_session_url:
            return False, "", "initiate upload: no Location header in response"

        # Step 2 — PUT the file bytes to the session URL
        try:
            with p.open("rb") as f:
                up = client.put(
                    upload_session_url,
                    content=f.read(),
                    headers={"Content-Type": mime_type},
                    timeout=None,  # videos can be slow; no read timeout
                )
        except httpx.HTTPError as e:
            return False, "", f"upload network error: {e}"
        if up.status_code >= 400:
            return False, "", f"upload HTTP {up.status_code}: {up.text[:300]}"

        try:
            body = up.json()
        except ValueError:
            return False, "", "upload: non-JSON response"
        video_id = body.get("id")
        if not video_id:
            return False, "", f"upload: missing id in response ({body!r})"

        return True, video_id, ""
