#!/bin/sh
# Nightly database backup: a compressed pg_dump in deploy/backups/, keeping the
# newest 14. Run it by hand or from cron (see docs/DEPLOY.md):
#   0 3 * * *  cd /opt/catch-a-scammer/deploy && ./backup.sh >> backups/backup.log 2>&1
# Restore one with:
#   docker compose exec -T db pg_restore -U cas -d osint --clean --if-exists < backups/<file>.dump
set -e
cd "$(dirname "$0")"
mkdir -p backups
file="backups/cas-$(date +%Y-%m-%d-%H%M).dump"
docker compose exec -T db pg_dump -U cas -Fc osint > "$file"
echo "$(date) wrote $file ($(du -h "$file" | cut -f1))"
ls -1t backups/cas-*.dump | tail -n +15 | xargs -r rm --
