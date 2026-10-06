"""Connection pool for the game database (local Postgres via docker compose).

prepare_threshold=None disables server-side prepared statements so the same
code also works behind a transaction-mode connection pooler.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def _configure(conn):
    conn.execute("set search_path to public, extensions")
    conn.commit()


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        url = os.environ["DATABASE_URL"]
        _pool = ConnectionPool(url, min_size=1, max_size=int(os.environ.get("DB_POOL_MAX", "5")),
                               kwargs={"prepare_threshold": None, "row_factory": dict_row},
                               configure=_configure, open=True)
    return _pool


@contextmanager
def tx():
    """One transaction per request; commits on success, rolls back on error."""
    with pool().connection() as conn:
        with conn.transaction():
            yield conn
