# Signal Harbor public demo for Railway: stage 1 builds the React UI, stage 2 serves it and the API from uvicorn.
FROM node:22-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SH_MODE=prod SH_DATA_ROOT=/data SH_SCHEDULER=on SH_ROUTER=on SH_MODEL_PROVIDER=openrouter \
    TMPDIR=/tmp
# the sketch reader (rapidocr, through opencv) needs these system libraries; the slim image lacks them
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libxcb1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY sh_platform/ sh_platform/
COPY modules/ modules/
COPY packs/ packs/
COPY skills/ skills/
COPY tools/seed.py tools/seed_evergreen.py tools/seed_10uc.py tools/seed_v3_demo.py tools/seed_demo_boot.py tools/seed_demo_ready.py tools/seed_walk_benchmark.py tools/make_e2_statements.py tools/migrate_to_postgres.py tools/worker.py tools/start.sh tools/seed_v3_office.py tools/
# what the code reads at run time from docs/: the data model scripts, and the synthetic universe the demo is seeded from
COPY docs/v2/ docs/v2/
COPY docs/demo/v3-office.zip docs/demo/v3-office.zip
COPY docs/test/10uc_universe.json docs/test/10uc_universe.json
COPY tests/v1/fixtures/10uc/ tests/v1/fixtures/10uc/
COPY --from=ui /ui/dist ui/dist
# the local embedding model caches under ./data/_models: point that at the volume so it downloads once
RUN ln -s /data /app/data
# Railway sets PORT. tools/start.sh seeds an empty volume (never wipes; logins go to /data/_control/seed_credentials.txt, never to the log)
# and, in production mode, migrates to Postgres and starts the worker in this container.
CMD ["sh", "tools/start.sh"]
