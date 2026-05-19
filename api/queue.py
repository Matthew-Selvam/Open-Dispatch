"""Pluggable queue. JSONL for zero-infra; Redis+RQ when REDIS_URL is set.

Each queue row:
    {
      "id": "uuid",
      "unit": {...ContentUnit dict...},
      "platform": "twitter:pol",
      "scheduled_for": "ISO",
      "status": "queued|publishing|published|failed|dead",
      "attempts": 0,
      "post_id": null,
      "last_error": null,
      "created_at": "ISO",
      "updated_at": "ISO"
    }
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("OPEN_DISPATCH_DATA", REPO_ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
JSONL_PATH = DATA_DIR / "queue.jsonl"

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _read_all() -> list[dict]:
    if not JSONL_PATH.exists():
        return []
    rows = []
    with JSONL_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_all(rows: Iterable[dict]) -> None:
    tmp = JSONL_PATH.with_suffix(".jsonl.tmp")
    with tmp.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(JSONL_PATH)


class JsonlQueue:
    """Single-process JSONL queue. Suitable for self-host MVP."""

    def enqueue(self, unit_dict: dict, platform_key: str, scheduled_for: str) -> str:
        row = {
            "id": str(uuid.uuid4()),
            "unit": unit_dict,
            "platform": platform_key,
            "scheduled_for": scheduled_for,
            "status": "queued",
            "attempts": 0,
            "post_id": None,
            "last_error": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        with _LOCK:
            with JSONL_PATH.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row["id"]

    def list_all(self, status: str | None = None) -> list[dict]:
        with _LOCK:
            rows = _read_all()
        if status:
            rows = [r for r in rows if r["status"] == status]
        return rows

    def get(self, row_id: str) -> dict | None:
        with _LOCK:
            for r in _read_all():
                if r["id"] == row_id:
                    return r
        return None

    def list_due(self, now_iso: str) -> list[dict]:
        with _LOCK:
            return [
                r for r in _read_all()
                if r["status"] == "queued" and r["scheduled_for"] <= now_iso
            ]

    def _update(self, row_id: str, patch: dict[str, Any]) -> None:
        with _LOCK:
            rows = _read_all()
            for r in rows:
                if r["id"] == row_id:
                    r.update(patch)
                    r["updated_at"] = _now()
                    break
            _write_all(rows)

    def mark_publishing(self, row_id: str) -> None:
        self._update(row_id, {"status": "publishing"})

    def mark_published(self, row_id: str, post_id: str) -> None:
        self._update(row_id, {"status": "published", "post_id": post_id, "last_error": None})

    def mark_failed(self, row_id: str, err: str, dead: bool = False) -> None:
        row = self.get(row_id) or {}
        attempts = int(row.get("attempts", 0)) + 1
        self._update(row_id, {
            "status": "dead" if dead else "queued",
            "attempts": attempts,
            "last_error": err[:500],
        })


def get_queue() -> JsonlQueue:
    # Redis backend hook lives here when REDIS_URL is set; JSONL is the MVP.
    return JsonlQueue()
