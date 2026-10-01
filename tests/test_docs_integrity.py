"""Docs integrity: no dead internal links, and every env var is documented.

The credentials guide was referenced from the README and the landing page as
the answer to "where do I get API keys", but the file did not exist — a 404 on
the main conversion path, with no replacement anywhere in the repo.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _tracked(*patterns: str) -> list[Path]:
    out = subprocess.run(["git", "ls-files", *patterns], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [ROOT / p for p in out.split("\n") if p]


# ── the credentials guide exists and is linked ─────────────────────────────

def test_credentials_guide_exists() -> None:
    guide = ROOT / "CREDENTIALS_GUIDE.html"
    assert guide.is_file(), "CREDENTIALS_GUIDE.html is referenced by the README " \
                            "and landing page but does not exist"
    assert guide.stat().st_size > 5000


@pytest.mark.parametrize("referrer", ["README.md", "landing/src/app/page.tsx"])
def test_referrer_that_names_the_guide_also_contains_it(referrer: str) -> None:
    path = ROOT / referrer
    if not path.is_file():
        pytest.skip(f"{referrer} not present")
    text = path.read_text(encoding="utf-8")
    if "CREDENTIALS_GUIDE" in text:
        assert (ROOT / "CREDENTIALS_GUIDE.html").is_file(), (
            f"{referrer} links to a credentials guide that is not in the repo")


def test_guide_documents_every_platform_the_code_supports() -> None:
    from adapters import ADAPTERS

    guide = (ROOT / "CREDENTIALS_GUIDE.html").read_text(encoding="utf-8").lower()
    for platform in ADAPTERS:
        assert platform in guide, f"{platform} has an adapter but no guide section"


# ── no dead relative links anywhere in the markdown docs ───────────────────

@pytest.mark.parametrize("doc", ["README.md", "CHANGELOG.md", "SECURITY.md",
                                 "CONTRIBUTING.md", "INSTALL_METHODS.md"])
def test_relative_doc_links_resolve(doc: str) -> None:
    path = ROOT / doc
    if not path.is_file():
        pytest.skip(f"{doc} not present")
    body = path.read_text(encoding="utf-8")
    # Strip fenced code so example links inside blocks are ignored.
    body = re.sub(r"^```.*?^```", "", body, flags=re.S | re.M)
    missing = []
    for m in re.finditer(r"\]\(([^)#][^)]*)\)", body):
        target = m.group(1).strip()
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        clean = target.split("#")[0]
        if clean and not (path.parent / clean).exists():
            missing.append(target)
    assert not missing, f"{doc} links to missing files: {missing}"


# ── every env var the code reads is documented ─────────────────────────────

def _env_vars_read_by_code() -> set[str]:
    files = [p for p in _tracked("*.py") if ".venv" not in p.parts]
    found: set[str] = set()
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"os\.(?:getenv|environ\.get)\(\s*[\"']([A-Z0-9_]+)", text):
            found.add(m.group(1))
    return found


def test_every_env_var_read_by_code_is_in_env_example() -> None:
    """An operator must be able to discover every variable the code reads."""
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    missing = sorted(v for v in _env_vars_read_by_code()
                     if v not in example
                     and v not in {"HOST", "PORT", "OPEN_DISPATCH_URL"})
    assert not missing, f"read by the code but absent from .env.example: {missing}"


def test_credentials_guide_covers_the_platform_env_vars() -> None:
    guide = (ROOT / "CREDENTIALS_GUIDE.html").read_text(encoding="utf-8")
    platform_prefixes = ("TWITTER_", "BLUESKY_", "TELEGRAM_", "IG_", "LINKEDIN_",
                         "THREADS_", "YOUTUBE_", "TIKTOK_", "FACEBOOK_", "DISCORD_")
    creds = {v for v in _env_vars_read_by_code() if v.startswith(platform_prefixes)}
    missing = sorted(v for v in creds if v not in guide)
    assert not missing, f"platform credentials missing from the guide: {missing}"
