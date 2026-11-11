"""Real PostgreSQL transaction and claim checks; requires a disposable test DSN."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from api.queue import PostgresQueue


@pytest.fixture()
def pg_queue():
    dsn = os.getenv("OPEN_DISPATCH_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("set OPEN_DISPATCH_TEST_POSTGRES_DSN to a disposable PostgreSQL database")
    psycopg2 = pytest.importorskip("psycopg2")
    from psycopg2 import sql

    schema = f"od_audit_{uuid.uuid4().hex}"
    admin = psycopg2.connect(dsn)
    try:
        with admin:
            with admin.cursor() as cur:
                cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

        def factory():
            return psycopg2.connect(dsn, options=f"-c search_path={schema}")

        q = PostgresQueue(factory)
        q._test_schema = schema  # so tests can touch rows outside the API
        yield q
    finally:
        with admin:
            with admin.cursor() as cur:
                cur.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        admin.close()


def test_transactions_persist_and_only_one_worker_claims(pg_queue):
    due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    rid = pg_queue.enqueue({"id": "audit"}, "fake:default", due)
    assert pg_queue.get(rid)["unit"] == {"id": "audit"}
    assert [r["id"] for r in pg_queue.list_due(datetime.now(timezone.utc).isoformat())] == [rid]

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(pg_queue.mark_publishing, [rid, rid]))
    assert sorted(claims) == [False, True]
    assert pg_queue.mark_published(rid, "platform-post-id")
    assert pg_queue.get(rid)["post_id"] == "platform-post-id"
    assert pg_queue.get(rid)["status"] == "published"


def test_stale_publishing_claims_are_quarantined_not_requeued(pg_queue):
    """A crashed worker's row must land in failed with a verify-before-retry
    error — never straight back to queued, which would double-post."""
    due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    rid = pg_queue.enqueue({"id": "stale"}, "fake:default", due)
    assert pg_queue.mark_publishing(rid)

    # Age the claim beyond the lease directly in the DB.
    psycopg2 = pytest.importorskip("psycopg2")
    dsn = os.getenv("OPEN_DISPATCH_TEST_POSTGRES_DSN")
    schema = pg_queue._test_schema
    admin = psycopg2.connect(dsn)
    try:
        with admin:
            with admin.cursor() as cur:
                cur.execute(
                    f"UPDATE {schema}.open_dispatch_queue "
                    "SET updated_at = now() - interval '1 hour' WHERE id = %s",
                    (rid,),
                )
    finally:
        admin.close()

    assert pg_queue.reap_stale_publishing(900) == [rid]
    row = pg_queue.get(rid)
    assert row["status"] == "failed"
    assert "verify on the platform before retrying" in row["last_error"]
    assert row["attempts"] == 0
    # Operator-verified retry re-queues normally.
    assert pg_queue.retry(rid)
    assert pg_queue.get(rid)["status"] == "queued"
