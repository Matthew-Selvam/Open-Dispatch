"""Telegram adapter — text/photo/video via Bot API.

Env: TELEGRAM_BOT_TOKEN (required), TELEGRAM_CHAT_ID (required for default account).
Per-account override: TELEGRAM_CHAT_ID_<ACCOUNT> when target is `telegram:<account>`.

Format key: `telegram_message`
  text (required), photo_path (optional), video_path (optional), parse_mode (default "HTML")
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx

from api.schema import CAPTION_LIMITS, ContentUnit

log = logging.getLogger("open-dispatch.telegram")


def _chunk(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def _chat_id(account: str | None) -> str:
    if account:
        v = os.getenv(f"TELEGRAM_CHAT_ID_{account.upper()}")
        if v:
            return v
    return os.getenv("TELEGRAM_CHAT_ID", "")


def publish(unit: ContentUnit, account: str | None = None) -> tuple[bool, str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = _chat_id(account)
    if not (token and chat_id):
        return False, "", "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing"

    data = unit.formats.get("telegram_message") or {}
    text = (data.get("text") or data.get("caption") or "").strip()
    parse_mode = data.get("parse_mode", "HTML")
    photo = data.get("photo_path")
    video = data.get("video_path")

    base = f"https://api.telegram.org/bot{token}"
    try:
        if photo:
            p = Path(photo)
            if not p.exists():
                return False, "", f"photo_path does not exist: {photo}"
            with p.open("rb") as f:
                r = httpx.post(
                    f"{base}/sendPhoto",
                    data={"chat_id": chat_id, "caption": text[:1024], "parse_mode": parse_mode},
                    files={"photo": f},
                    timeout=60,
                )
            r.raise_for_status()
            msg_id = str(r.json().get("result", {}).get("message_id", ""))
            if len(text) > 1024:
                for chunk in _chunk(text[1024:], CAPTION_LIMITS["telegram"]):
                    httpx.post(f"{base}/sendMessage",
                               data={"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode},
                               timeout=30).raise_for_status()
            return True, msg_id, ""

        if video:
            v = Path(video)
            if not v.exists():
                return False, "", f"video_path does not exist: {video}"
            with v.open("rb") as f:
                r = httpx.post(
                    f"{base}/sendVideo",
                    data={"chat_id": chat_id, "caption": text[:1024], "parse_mode": parse_mode},
                    files={"video": f},
                    timeout=120,
                )
            r.raise_for_status()
            msg_id = str(r.json().get("result", {}).get("message_id", ""))
            if len(text) > 1024:
                for chunk in _chunk(text[1024:], CAPTION_LIMITS["telegram"]):
                    httpx.post(f"{base}/sendMessage",
                               data={"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode},
                               timeout=30).raise_for_status()
            return True, msg_id, ""

        if not text:
            return False, "", "text empty"
        first_id = None
        for chunk in _chunk(text, CAPTION_LIMITS["telegram"]):
            r = httpx.post(
                f"{base}/sendMessage",
                data={"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode},
                timeout=30,
            )
            r.raise_for_status()
            if first_id is None:
                first_id = str(r.json().get("result", {}).get("message_id", ""))
        return True, first_id or "", ""

    except httpx.HTTPStatusError as e:
        return False, "", f"HTTP {e.response.status_code}: {e.response.text[:300]}"
    except Exception as e:  # noqa: BLE001
        return False, "", f"telegram error: {e}"
