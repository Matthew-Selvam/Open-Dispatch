"""LinkedIn adapter — UGC Post API for personal profile or organization page.

Env:
  LINKEDIN_ACCESS_TOKEN[_<ACCT>]   (3-legged OAuth token with w_member_social)
  LINKEDIN_AUTHOR_URN[_<ACCT>]     ("urn:li:person:XXX" or "urn:li:organization:XXX")

Format key: `linkedin_post`
  text: str (<=3000 chars)
  image_url: str (optional, public HTTPS — for image asset; full asset upload not
                  implemented here, use image_url referencing a pre-uploaded asset URN
                  or supply asset_urn directly)
  asset_urn: str (optional — pre-uploaded LinkedIn asset URN to attach)
"""

from __future__ import annotations

import logging
import os

import httpx

from api.schema import ContentUnit

log = logging.getLogger("open-dispatch.linkedin")
UGC = "https://api.linkedin.com/v2/ugcPosts"


def _creds(account: str | None) -> tuple[str, str]:
    suffix = f"_{account.upper()}" if account else ""
    token = os.getenv(f"LINKEDIN_ACCESS_TOKEN{suffix}") or os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    author = os.getenv(f"LINKEDIN_AUTHOR_URN{suffix}") or os.getenv("LINKEDIN_AUTHOR_URN", "")
    return token, author


def publish(unit: ContentUnit, account: str | None = None) -> tuple[bool, str, str]:
    fmt = unit.formats.get("linkedin_post") or {}
    text = (fmt.get("text") or "").strip()
    if not text:
        return False, "", "linkedin_post.text empty"

    token, author = _creds(account)
    if not (token and author):
        return False, "", "LINKEDIN_ACCESS_TOKEN / LINKEDIN_AUTHOR_URN missing"

    payload: dict = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text[:3000]},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    asset_urn = fmt.get("asset_urn")
    if asset_urn:
        payload["specificContent"]["com.linkedin.ugc.ShareContent"].update({
            "shareMediaCategory": "IMAGE",
            "media": [{"status": "READY", "media": asset_urn}],
        })

    try:
        r = httpx.post(UGC,
                       headers={"Authorization": f"Bearer {token}",
                                "X-Restli-Protocol-Version": "2.0.0",
                                "Content-Type": "application/json"},
                       json=payload,
                       timeout=30)
        if r.status_code >= 400:
            return False, "", f"linkedin: {r.status_code} {r.text[:400]}"
        urn = r.headers.get("x-restli-id") or r.json().get("id", "")
        return True, str(urn), ""
    except Exception as e:  # noqa: BLE001
        return False, "", f"linkedin error: {e}"
