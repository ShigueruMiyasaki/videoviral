FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-liberation gosu \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 videoviral

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY config ./config
COPY src ./src
COPY run_api.py .
COPY deploy/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && mkdir -p storage/raw storage/clips storage/output storage/audio storage/avatars storage/studio

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

ENTRYPOINT ["/entrypoint.sh"]
