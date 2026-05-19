"""Bluesky adapter — AT Protocol posting via atproto SDK.

Env:
  BLUESKY_HANDLE[_<ACCT>], BLUESKY_APP_PASSWORD[_<ACCT>]
  (App password from https://bsky.app/settings/app-passwords — never use main pwd.)

Format key: `bluesky_post`
  text: str  (<=300 chars; threads supported via reply chain)
  images: list[{path: str, alt: str}]  (<=4)
  thread: list[str]  (if multiple posts, treats text as ignored)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from api.schema import ContentUnit

log = logging.getLogger("open-dispatch.bluesky")


def _creds(account: str | None) -> tuple[str, str]:
    suffix = f"_{account.upper()}" if account else ""
    handle = os.getenv(f"BLUESKY_HANDLE{suffix}") or os.getenv("BLUESKY_HANDLE", "")
    pwd = os.getenv(f"BLUESKY_APP_PASSWORD{suffix}") or os.getenv("BLUESKY_APP_PASSWORD", "")
    return handle, pwd


def publish(unit: ContentUnit, account: str | None = None) -> tuple[bool, str, str]:
    fmt = unit.formats.get("bluesky_post") or {}
    handle, password = _creds(account)
    if not (handle and password):
        return False, "", "BLUESKY_HANDLE / BLUESKY_APP_PASSWORD missing"

    try:
        from atproto import Client, client_utils  # noqa: F401
    except ImportError:
        return False, "", "atproto not installed (pip install atproto)"

    try:
        client = Client()
        client.login(handle, password)

        thread = fmt.get("thread") or []
        if thread:
            parent = None
            root = None
            first_uri = ""
            for piece in thread:
                ref = client.send_post(text=piece[:300],
                                       reply_to=parent)
                if root is None:
                    root = ref
                    first_uri = ref.uri
                parent = {
                    "root": {"uri": root.uri, "cid": root.cid},
                    "parent": {"uri": ref.uri, "cid": ref.cid},
                }
            return True, first_uri, ""

        text = (fmt.get("text") or "").strip()
        if not text:
            return False, "", "bluesky_post.text empty"

        images = fmt.get("images") or []
        if images:
            embed_images = []
            for img in images[:4]:
                p = Path(img["path"])
                if not p.exists():
                    return False, "", f"image missing: {p}"
                uploaded = client.upload_blob(p.read_bytes())
                embed_images.append({"image": uploaded.blob, "alt": img.get("alt", "")})
            ref = client.send_images(text=text[:300], images_alt=[i["alt"] for i in embed_images],
                                     images=[p["image"] for p in embed_images])
        else:
            ref = client.send_post(text=text[:300])
        return True, ref.uri, ""
    except Exception as e:  # noqa: BLE001
        return False, "", f"bluesky error: {e}"
