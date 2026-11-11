"""SEC-1 regression tests — Docker Compose network defaults.

The default Compose deployment must never publish internal services to the
host's public interfaces: the API binds loopback only (it runs unauthenticated
when OPEN_DISPATCH_API_TOKEN is empty), and Redis/Postgres are never published
at all. These tests parse the resolved compose configuration so a regression
fails in CI before a deployment ever happens.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]

_requires_docker = pytest.mark.skipif(
    shutil.which("docker") is None or subprocess.run(
        ["docker", "info"], capture_output=True, timeout=30).returncode != 0,
    reason="docker daemon not available",
)


def _resolved_config(compose_args: tuple[str, ...] = ()) -> str:
    out = subprocess.run(
        ["docker", "compose", *compose_args, "config"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


def _services(config: str) -> dict[str, str]:
    """Split the resolved YAML into per-service chunks (regex, no yaml dep)."""
    services: dict[str, str] = {}
    current = None
    for line in config.splitlines():
        stripped = line.strip()
        if line.startswith("  ") and stripped.endswith(":") and not line.startswith("    "):
            current = stripped[:-1]
            services[current] = []
        elif current is not None:
            services[current].append(line)
    return {k: "\n".join(v) for k, v in services.items()}


def test_default_compose_api_binds_loopback_only():
    """SEC-1: the default compose maps the API to 127.0.0.1 only."""
    config = _resolved_config()
    api = _services(config).get("api", "")
    assert "host_ip: 127.0.0.1" in api, (
        "default compose must bind the API to loopback (127.0.0.1:8000:8000) — "
        "the API is unauthenticated when OPEN_DISPATCH_API_TOKEN is unset")


def test_default_compose_never_binds_wildcard():
    """No service in the default compose may publish on all interfaces."""
    config = _resolved_config()
    for svc, chunk in _services(config).items():
        if "published:" in chunk:
            before = chunk[: chunk.index("published:")]
            if "host_ip:" not in before.split("- mode: ingress")[-1]:
                # a published port without an explicit host_ip binds 0.0.0.0
                assert False, f"service {svc!r} publishes a wildcard port"


def test_default_compose_redis_never_published():
    """Redis must never publish a host port in the default compose."""
    config = _resolved_config(("--profile", "redis"))
    redis = _services(config).get("redis", "")
    assert "published:" not in redis, "redis must not publish ports to the host"


def test_prod_compose_publishes_nothing():
    """The production compose publishes zero host ports — the reverse proxy
    joins the compose network and is the only access path."""
    config = _resolved_config(("-f", "docker-compose.prod.yml"))
    assert "published:" not in config, (
        "docker-compose.prod.yml must publish no host ports")
    assert "expose:" in config, "the api must still be reachable on the compose network"
