"""Twitter / X adapter - v2 API via tweepy or an opt-in Xquik backend.

Env (per account suffix; uppercase):
  TWITTER_API_KEY, TWITTER_API_SECRET (consumer creds, shared)
  TWITTER_ACCESS_TOKEN[_<ACCT>], TWITTER_ACCESS_SECRET[_<ACCT>]
  TWITTER_BACKEND=xquik, XQUIK_API_KEY, XQUIK_ACCOUNT[_<ACCT>] (optional)

Format key: `twitter_thread`
  tweets: list[str] - each <=280 chars; posted as a reply chain
  media_paths (optional, applied to first tweet): list[str]
  media_urls (optional for Xquik backend): public media URLs for first tweet
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from api.schema import ContentUnit

log = logging.getLogger("open-dispatch.twitter")
XQUIK_DEFAULT_BASE_URL = "https://xquik.com"


def _tokens(account: str | None) -> tuple[str, str]:
    suffix = f"_{account.upper()}" if account else ""
    at = os.getenv(f"TWITTER_ACCESS_TOKEN{suffix}") or os.getenv("TWITTER_ACCESS_TOKEN", "")
    asec = os.getenv(f"TWITTER_ACCESS_SECRET{suffix}") or os.getenv("TWITTER_ACCESS_SECRET", "")
    return at, asec


def _xquik_backend_enabled() -> bool:
    return os.getenv("TWITTER_BACKEND", "").strip().lower() == "xquik"


def _xquik_account(account: str | None) -> str:
    suffix = f"_{account.upper()}" if account else ""
    return (
        os.getenv(f"XQUIK_ACCOUNT{suffix}")
        or os.getenv("XQUIK_ACCOUNT")
        or account
        or ""
    ).strip()


def _xquik_media_urls(fmt: dict[str, Any]) -> list[str]:
    raw_media = fmt.get("media_urls") or fmt.get("media") or []
    if not isinstance(raw_media, list):
        return []
    return [str(url).strip() for url in raw_media if str(url).strip()]


def _xquik_ids(data: dict[str, Any]) -> tuple[str, str]:
    tweet_id = data.get("tweetId")
    write_action_id = data.get("writeActionId")
    return (
        tweet_id if isinstance(tweet_id, str) else "",
        write_action_id if isinstance(write_action_id, str) else "",
    )


def _publish_with_xquik(
    tweets: list[str],
    fmt: dict[str, Any],
    account: str | None,
) -> tuple[bool, str, str]:
    api_key = os.getenv("XQUIK_API_KEY", "").strip()
    if not api_key:
        return False, "", "XQUIK_API_KEY missing"

    xquik_account = _xquik_account(account)
    if not xquik_account:
        return False, "", "XQUIK_ACCOUNT missing"

    base_url = os.getenv("XQUIK_BASE_URL", XQUIK_DEFAULT_BASE_URL).rstrip("/")
    media_urls = _xquik_media_urls(fmt)
    first_id = ""
    in_reply_to: str | None = None

    try:
        for i, text in enumerate(tweets):
            payload: dict[str, Any] = {
                "account": xquik_account,
                "text": text[:280],
            }
            if in_reply_to:
                payload["reply_to_tweet_id"] = in_reply_to
            if i == 0 and media_urls:
                payload["media"] = media_urls[:4]

            response = httpx.post(
                f"{base_url}/api/v1/x/tweets",
                headers={"X-API-Key": api_key},
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                return False, "", "xquik returned non-object response"
            tweet_id, write_action_id = _xquik_ids(data)
            if not tweet_id and i < len(tweets) - 1:
                return False, "", "xquik response missing tweetId for reply chain"
            post_id = tweet_id or write_action_id
            if not post_id:
                return False, "", "xquik response missing tweetId"
            if i == 0:
                first_id = post_id
            in_reply_to = tweet_id or None
        return True, first_id, ""
    except httpx.HTTPError as e:
        return False, "", f"xquik error: {e}"


def publish(unit: ContentUnit, account: str | None = None) -> tuple[bool, str, str]:
    fmt = unit.formats.get("twitter_thread") or {}
    tweets = [str(t).strip() for t in fmt.get("tweets", []) if str(t).strip()]
    if not tweets:
        return False, "", "twitter_thread.tweets is empty"
    if _xquik_backend_enabled():
        return _publish_with_xquik(tweets, fmt, account)

    consumer_key = os.getenv("TWITTER_API_KEY", "").strip()
    consumer_secret = os.getenv("TWITTER_API_SECRET", "").strip()
    access_token, access_secret = _tokens(account)
    if not (consumer_key and consumer_secret and access_token and access_secret):
        return False, "", "twitter credentials missing"

    try:
        import tweepy
    except ImportError:
        return False, "", "tweepy not installed (pip install tweepy)"

    try:
        client = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_secret,
        )
        in_reply_to: str | None = None
        first_id = ""
        media_ids: list[str] = []

        media_paths = fmt.get("media_paths") or []
        if media_paths:
            api_v1 = tweepy.API(tweepy.OAuth1UserHandler(
                consumer_key, consumer_secret, access_token, access_secret,
            ))
            for path in media_paths[:4]:
                m = api_v1.media_upload(filename=path)
                media_ids.append(str(m.media_id))

        for i, text in enumerate(tweets):
            kwargs: dict = {"text": text[:280]}
            if in_reply_to:
                kwargs["in_reply_to_tweet_id"] = in_reply_to
            if i == 0 and media_ids:
                kwargs["media_ids"] = media_ids
            resp = client.create_tweet(**kwargs)
            tid = str(resp.data["id"])
            if i == 0:
                first_id = tid
            in_reply_to = tid
        return True, first_id, ""
    except Exception as e:  # noqa: BLE001
        return False, "", f"twitter error: {e}"
