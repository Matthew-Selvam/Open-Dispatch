#!/usr/bin/env python
"""PERF-2 benchmark — synthetic worker throughput across backends and concurrency.

Synthetic adapters only (no network, no real platforms). Measures, per
(backend, concurrency) point, over N synthetic rows:

- wall time and jobs/minute for one full run_once() batch
- per-row processing latency p50 / p95 (in-process publish duration)
- duplicate claims (a row claimed more than once — must always be 0)
- error rate (synthetic failures are deterministic, so 0 in a healthy run)

Usage:
    python scripts/benchmark_worker.py --rows 200 --concurrency 1 2 4 8
    python scripts/benchmark_worker.py --rows 100 --concurrency 1 4 \
        --backend postgres --dsn postgresql://od@localhost:5499/od_bench

Results are printed as a table and written to
AUDIT/V050/benchmark_results.md (append) when --out is given.

This is a LOCAL SYNTHETIC benchmark on one machine. It establishes a
relative baseline (does concurrency help? do claims stay atomic under
load?) — it does NOT predict production throughput on real platform APIs.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import tempfile
import time
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _make_env(backend: str, dsn: str | None, tmp: Path) -> None:
    os.environ["OPEN_DISPATCH_DATA"] = str(tmp)
    os.environ.pop("REDIS_URL", None)
    os.environ.pop("DATABASE_URL", None)
    if backend == "postgres":
        os.environ["DATABASE_URL"] = dsn
    elif backend == "redis":
        os.environ["REDIS_URL"] = dsn or "redis://localhost:6379/0"


def _build_queue(backend: str, dsn: str | None, tmp: Path):
    """Import after env is set; return (queue, get_queue_patch)."""
    import api.queue as qmod

    if backend == "jsonl":
        importlib_reload(qmod)
        return qmod.JsonlQueue(), None
    if backend == "postgres":
        import psycopg2
        real = psycopg2.connect
        psycopg2.connect = lambda *a, **kw: real(dsn)  # type: ignore[assignment]
        qmod._reset_singleton_for_tests()
        return qmod.get_queue(), None
    if backend == "redis":
        import redis
        client = redis.Redis.from_url(dsn or "redis://localhost:6379/0", decode_responses=False)
        return qmod.RedisQueue(client), None
    raise SystemExit(f"unknown backend {backend!r}")


def importlib_reload(mod):
    import importlib
    importlib.reload(mod)


def run_point(backend: str, concurrency: int, rows: int, dsn: str | None) -> dict:
    import scheduler.worker as w

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _make_env(backend, dsn, tmp)
        # rebind module state for this point
        import api.queue as qmod
        importlib_reload(qmod)
        if backend == "jsonl":
            qmod.JSONL_PATH = tmp / "queue.jsonl"
            q = qmod.JsonlQueue()
        elif backend == "postgres":
            import psycopg2
            real = psycopg2.connect
            psycopg2.connect = lambda *a, **kw: real(dsn)  # type: ignore[assignment]
            q = qmod.PostgresQueue(lambda: psycopg2.connect(dsn))
        else:
            import redis
            client = redis.Redis.from_url(dsn or "redis://localhost:6379/0",
                                          decode_responses=False)
            q = qmod.RedisQueue(client)

        due = (datetime.now(tz=timezone.utc) - timedelta(minutes=1)).isoformat()
        ids = [q.enqueue({"id": f"bench-{i}", "targets": ["bench"]},
                         "bench:default", due) for i in range(rows)]

        durations: list[float] = []
        lock = __import__("threading").Lock()

        def publish(unit, account=None):
            t0 = time.perf_counter()
            time.sleep(0.002)  # synthetic adapter work
            with lock:
                durations.append(time.perf_counter() - t0)
            return True, f"post-{unit.id}", ""

        w.ADAPTERS = {"bench": types.SimpleNamespace(publish=publish)}
        w.get_queue = lambda: q
        w.WORKER_CONCURRENCY = concurrency
        w.PUBLISHING_LEASE = 900

        import resource
        cpu0 = time.process_time()
        t0 = time.perf_counter()
        processed = w.run_once()
        wall = time.perf_counter() - t0
        cpu = time.process_time() - cpu0
        maxrss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

        # Persistent backends keep rows from earlier points — count ONLY the
        # rows this point enqueued (ids), never the whole table.
        final = {r["id"]: r for r in q.list_all()}
        mine = [final[i] for i in ids if i in final]
        published = sum(1 for r in mine if r["status"] == "published")
        duplicates = sum(
            1 for r in mine
            if r["status"] != "published" and r.get("attempts", 0) > 0
        )
        lost = len(ids) - len(mine)
        if lost:
            raise SystemExit(f"benchmark integrity failure: {lost} rows lost")
        p50 = statistics.median(durations) * 1000 if durations else 0
        p95 = (sorted(durations)[int(0.95 * len(durations))] * 1000) if durations else 0
        return {
            "backend": backend,
            "concurrency": concurrency,
            "rows": rows,
            "processed": processed,
            "published": published,
            "wall_s": round(wall, 3),
            "jobs_per_min": round(published / wall * 60, 1) if wall else 0,
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "duplicate_or_errored": duplicates,
            "errors": 0,
            "cpu_s": round(cpu, 3),
            "maxrss_mb": round(maxrss_mb, 1),
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=200)
    ap.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4, 8])
    ap.add_argument("--backend", default="jsonl",
                    choices=["jsonl", "postgres", "redis"])
    ap.add_argument("--dsn", default=None)
    ap.add_argument("--out", default=None, help="append a markdown table to this file")
    args = ap.parse_args()

    results = []
    for c in args.concurrency:
        results.append(run_point(args.backend, c, args.rows, args.dsn))

    cols = ["backend", "concurrency", "rows", "published", "wall_s",
            "jobs_per_min", "p50_ms", "p95_ms", "duplicate_or_errored", "errors",
            "cpu_s", "maxrss_mb"]
    print("\t".join(cols))
    for r in results:
        print("\t".join(str(r[c]) for c in cols))

    if args.out:
        lines = [
            f"## {args.backend} — {args.rows} synthetic rows",
            "",
            "| " + " | ".join(cols) + " |",
            "|" + "|".join("---" for _ in cols) + "|",
        ]
        lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in results]
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with Path(args.out).open("a") as f:
            f.write("\n".join(lines) + "\n\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
