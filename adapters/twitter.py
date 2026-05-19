"""Twitter / X adapter — v2 API via tweepy.

Env (per account suffix; uppercase):
  TWITTER_API_KEY, TWITTER_API_SECRET (consumer creds, shared)
  TWITTER_ACCESS_TOKEN[_<ACCT>], TWITTER_ACCESS_SECRET[_<ACCT>]

Format key: `twitter_thread`
  tweets: list[str] — each <=280 chars; posted as a reply chain
  media_paths (optional, applied to first tweet): list[str]
"""

from __future__ import annotations

import logging
import os

from api.schema import ContentUnit

log = logging.getLogger("open-dispatch.twitter")


def _tokens(account: str | None) -> tuple[str, str]:
    suffix = f"_{account.upper()}" if account else ""
    at = os.getenv(f"TWITTER_ACCESS_TOKEN{suffix}") or os.getenv("TWITTER_ACCESS_TOKEN", "")
    asec = os.getenv(f"TWITTER_ACCESS_SECRET{suffix}") or os.getenv("TWITTER_ACCESS_SECRET", "")
    return at, asec


def publish(unit: ContentUnit, account: str | None = None) -> tuple[bool, str, str]:
    fmt = unit.formats.get("twitter_thread") or {}
    tweets = [str(t).strip() for t in fmt.get("tweets", []) if str(t).strip()]
    if not tweets:
        return False, "", "twitter_thread.tweets is empty"

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
