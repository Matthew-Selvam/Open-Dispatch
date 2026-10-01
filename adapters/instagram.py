"""Instagram adapter — Graph API publishing of image / video / carousel posts.

Env (per account suffix; uppercase):
  IG_USER_ID[_<ACCT>], IG_TOKEN[_<ACCT>]

Format key: `instagram_post`
  caption: str
  image_url: str (public HTTPS URL)  — for single image
  video_url: str (public HTTPS URL)  — for reel
  carousel_image_urls: list[str]     — for carousel (2-10)

Note: Instagram Graph requires media to be at a public URL, not a local path.
"""

from __future__ import annotations

import logging
import os
import time

import httpx

from adapters.errors import PERMANENT, classify, clip, prefix_error
from api.schema import ContentUnit

log = logging.getLogger("open-dispatch.instagram")
GRAPH = "https://graph.facebook.com/v21.0"


def _creds(account: str | None) -> tuple[str, str]:
    suffix = f"_{account.upper()}" if account else ""
    uid = os.getenv(f"IG_USER_ID{suffix}") or os.getenv("IG_USER_ID", "")
    tok = os.getenv(f"IG_TOKEN{suffix}") or os.getenv("IG_TOKEN", "")
    return uid, tok


def _wait_for_container(creation_id: str, token: str, timeout: int = 90) -> tuple[bool, str]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = httpx.get(f"{GRAPH}/{creation_id}",
                      headers={"Authorization": f"Bearer {token}"},
                      timeout=15)
        if r.status_code >= 400:
            return False, prefix_error(classify(r.status_code), f"poll: {clip(r.text)}")
        status = r.json().get("status_code")
        if status == "FINISHED":
            return True, ""
        if status == "ERROR":
            return False, prefix_error("retryable", f"container ERROR: {clip(r.text)}")
        time.sleep(3)
    return False, "container poll timeout"


def publish(unit: ContentUnit, account: str | None = None) -> tuple[bool, str, str]:
    fmt = unit.formats.get("instagram_post") or {}
    caption = (fmt.get("caption") or "").strip()
    image_url = fmt.get("image_url")
    video_url = fmt.get("video_url")
    carousel = fmt.get("carousel_image_urls") or []

    ig_user_id, token = _creds(account)
    if not (ig_user_id and token):
        return False, "", "IG_USER_ID / IG_TOKEN missing"

    try:
        if carousel:
            children: list[str] = []
            for url in carousel[:10]:
                r = httpx.post(f"{GRAPH}/{ig_user_id}/media",
                               data={"image_url": url, "is_carousel_item": "true",
                                     "access_token": token},
                               timeout=30)
                if r.status_code >= 400:
                    return False, "", prefix_error(classify(r.status_code), f"carousel child: {clip(r.text)}")
                children.append(r.json()["id"])
            r = httpx.post(f"{GRAPH}/{ig_user_id}/media",
                           data={"media_type": "CAROUSEL",
                                 "children": ",".join(children),
                                 "caption": caption[:2200],
                                 "access_token": token},
                           timeout=30)
        elif video_url:
            r = httpx.post(f"{GRAPH}/{ig_user_id}/media",
                           data={"media_type": "REELS",
                                 "video_url": video_url,
                                 "caption": caption[:2200],
                                 "access_token": token},
                           timeout=60)
        elif image_url:
            r = httpx.post(f"{GRAPH}/{ig_user_id}/media",
                           data={"image_url": image_url,
                                 "caption": caption[:2200],
                                 "access_token": token},
                           timeout=30)
        else:
            return False, "", "instagram_post needs image_url, video_url, or carousel_image_urls"

        if r.status_code >= 400:
            return False, "", prefix_error(classify(r.status_code), f"container: {clip(r.text)}")
        creation_id = r.json()["id"]

        ok, err = _wait_for_container(creation_id, token)
        if not ok:
            return False, "", err

        r = httpx.post(f"{GRAPH}/{ig_user_id}/media_publish",
                       data={"creation_id": creation_id, "access_token": token},
                       timeout=30)
        if r.status_code >= 400:
            return False, "", prefix_error(
                classify(r.status_code), f"publish: {r.status_code} {clip(r.text)}")
        # A 200 with no id means the media never got published. Returning
        # ok=True here marked the row published with an empty post_id and
        # fired a published webhook for a post that does not exist.
        pid = r.json().get("id")
        if not pid:
            return False, "", prefix_error(
                PERMANENT, f"media_publish 200 but no id in response: {clip(r.text)}")
        return True, str(pid), ""
    except Exception as e:  # noqa: BLE001
        return False, "", f"instagram error: {e}"
