#!/bin/sh
# Container start: bring the database schema up to date, build the shared world
# on the very first start, then run the API (which also serves the game).
set -e

python scripts/migrate.py

# Seeding wipes every case, so it only runs while the world is still empty.
world=$(python - <<'EOF'
import os, psycopg
with psycopg.connect(os.environ["DATABASE_URL"]) as c:
    print(c.execute("select count(*) from entities where case_id is null").fetchone()[0])
EOF
)
if [ "$world" = "0" ]; then
  echo "first start: seeding the world"
  python -m server.generator.world
fi

# --proxy-headers: rate limits see the player's IP, not the proxy's (Caddy or Render).
# Only that proxy can reach this port, so trusting its headers is safe.
# --no-access-log: don't keep a log of every visitor's IP address (errors are still logged).
# PORT: Render says which port to listen on; deploy/compose.yml leaves it at 8000.
exec uvicorn server.app:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*" --no-access-log
