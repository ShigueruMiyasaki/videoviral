#!/bin/sh
set -e

if [ -z "$DASHBOARD_PASSWORD" ]; then
    echo "DASHBOARD_PASSWORD vazio. Rode deploy/vps-up.sh ou preencha o .env."
    exit 1
fi

mkdir -p \
    /app/storage/raw \
    /app/storage/clips \
    /app/storage/output \
    /app/storage/audio \
    /app/storage/avatars \
    /app/storage/studio

chown -R videoviral:videoviral /app/storage

exec gosu videoviral uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips="*"
