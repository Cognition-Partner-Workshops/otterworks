FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN useradd -r -u 1001 appuser
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/search-service-prometheus
RUN mkdir -p "$PROMETHEUS_MULTIPROC_DIR" && chown appuser "$PROMETHEUS_MULTIPROC_DIR"
USER appuser

EXPOSE 8087
HEALTHCHECK --interval=10s --timeout=3s CMD curl -f http://localhost:8087/health || exit 1
CMD ["sh", "-c", "rm -f \"$PROMETHEUS_MULTIPROC_DIR\"/*.db && exec gunicorn --bind 0.0.0.0:8087 --workers 2 --threads 4 'app.main:create_app()'"]
