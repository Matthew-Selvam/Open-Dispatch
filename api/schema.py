"""ContentUnit — the single payload every adapter consumes.

Derived from the content-poster schema in CommandCenter (private), stripped of
CommandCenter-specific fields (source_project, paperclip approval hooks) so the
public Open-Dispatch repo stays generic.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CAPTION_LIMITS = {
    "instagram": 2200,
    "twitter": 280,
    "telegram": 4096,
    "youtube": 5000,
    "tiktok": 2200,
    "bluesky": 300,
    "linkedin": 3000,
    "threads": 500,
}

TARGET_RE = re.compile(r"^(?P<platform>[a-z]+)(?::(?P<account>[a-z0-9._-]+))?$")


class ValidationError(Exception):
    """Raised when a ContentUnit fails validation."""


def parse_target(target: str) -> tuple[str, str | None]:
    m = TARGET_RE.match(target.strip().lower())
    if not m:
        raise ValidationError(f"invalid target: {target!r}")
    return m.group("platform"), m.group("account")


@dataclass
class ContentUnit:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    category: str = "general"
    targets: list[str] = field(default_factory=list)
    scheduled_for: str | None = None
    formats: dict[str, Any] = field(default_factory=dict)
    webhook_url: str | None = None
    profile_id: str | None = None  # which profile's creds to use when dispatching

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "ContentUnit":
        return cls(
            id=d.get("id") or str(uuid.uuid4()),
            created_at=d.get("created_at") or datetime.now(tz=timezone.utc).isoformat(),
            category=d.get("category", "general"),
            targets=list(d.get("targets") or []),
            scheduled_for=d.get("scheduled_for"),
            formats=dict(d.get("formats") or {}),
            webhook_url=d.get("webhook_url"),
            profile_id=d.get("profile_id"),
        )

    @classmethod
    def load(cls, path: Path) -> "ContentUnit":
        return cls.from_dict(json.loads(Path(path).read_text()))


def validate(unit: ContentUnit) -> list[str]:
    errs: list[str] = []
    if not unit.targets:
        errs.append("targets must be non-empty")
    for t in unit.targets:
        try:
            parse_target(t)
        except ValidationError as e:
            errs.append(str(e))
    if not unit.formats:
        errs.append("formats must be non-empty")
    if unit.scheduled_for:
        try:
            datetime.fromisoformat(unit.scheduled_for.replace("Z", "+00:00"))
        except ValueError:
            errs.append(f"scheduled_for is not ISO-8601: {unit.scheduled_for!r}")
    return errs
