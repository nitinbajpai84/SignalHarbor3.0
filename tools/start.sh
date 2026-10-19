#!/bin/sh
# Container start for Railway. Simple mode: seed an empty volume, then the web app.
# Production mode (DATABASE_URL and REDIS_URL both set): also copy the seeded data into Postgres (idempotent)
# and run the job worker in this same container, because a Railway volume (the DuckDB warehouse) attaches to one service.
set -e
if [ "$SH_V3_OFFICE" = "1" ]; then
  python tools/seed_v3_office.py --data-root "$SH_DATA_ROOT"   # 3.0 tester demo: the synthetic Evergreen Office, never wiped
else
  python tools/seed_demo_boot.py --data-root "$SH_DATA_ROOT"
fi
if [ -n "$DATABASE_URL" ] && [ -n "$REDIS_URL" ]; then
  python tools/migrate_to_postgres.py "$SH_DATA_ROOT"
  python tools/worker.py &
fi
exec uvicorn sh_platform.app:create_app --factory --host 0.0.0.0 --port "${PORT:-8200}" --proxy-headers --forwarded-allow-ips="*" --timeout-keep-alive 75  # = sh_platform.app.KEEP_ALIVE_S
