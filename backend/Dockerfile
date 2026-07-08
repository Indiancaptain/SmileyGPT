FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r smiley && useradd -r -g smiley -d /app -s /sbin/nologin smiley

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# /data is a separate mounted volume (see docker-compose.yml) so uploads,
# the Chroma index, and logs all survive container recreation.
RUN mkdir -p /data/uploads /data/chroma /data/logs && chown -R smiley:smiley /app /data

USER smiley

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
