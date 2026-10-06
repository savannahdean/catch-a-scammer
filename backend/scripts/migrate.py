"""Apply supabase/migrations/*.sql in order, once each (tracked in _migrations).

Works on a fresh database and on one where 001/002 were already applied by hand
with psql (it detects the existing schema and marks those as done).
No psql install needed, so it runs the same on Windows/macOS/Linux.
"""
import os
import sys
from pathlib import Path

import psycopg

url = os.environ.get("DATABASE_URL") or sys.exit("DATABASE_URL not set")
files = sorted(Path("supabase/migrations").glob("*.sql"))
with psycopg.connect(url, prepare_threshold=None, autocommit=True) as conn:
    conn.execute("create table if not exists public._migrations (name text primary key, applied_at timestamptz default now())")
    conn.execute("alter table public._migrations enable row level security")
    done = {r[0] for r in conn.execute("select name from public._migrations")}
    if not done and conn.execute("select to_regclass('public.entities')").fetchone()[0]:
        for f in files[:2]:        # schema + functions applied before this runner existed
            conn.execute("insert into public._migrations(name) values (%s)", (f.name,))
            done.add(f.name)
        print("existing schema detected: marked 001-002 as applied")
    for f in files:
        if f.name in done:
            continue
        print("applying", f.name)
        conn.execute(f.read_text())
        conn.execute("insert into public._migrations(name) values (%s)", (f.name,))
    print("database is up to date")
