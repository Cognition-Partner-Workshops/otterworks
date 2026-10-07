# syntax=docker/dockerfile:1
# legacy-etl-cron: the legacy ETL runtime (Python 3.9 with the exact pins the
# golden harness records against) plus supercronic, running etl/crontab
# unmodified. Scripts, run.sh, crontab, the harness shim and config renderer are
# bind-mounted read-only at run time (docker-compose.airflow.yml), so the image
# never carries ETL code or config.
# Build context: etl/ (see Dockerfile.dockerignore: only the pin files and the
# entrypoint are sent; no config.ini enters the build, it is rendered at start).
ARG BASE_IMAGE=python:3.9-slim

FROM ${BASE_IMAGE} AS supercronic
ARG TARGETARCH
ARG SUPERCRONIC_VERSION=v0.2.33
ARG SUPERCRONIC_SHA1_AMD64=71b0d58cc53f6bd72cf2f293e09e294b79c666d8
ARG SUPERCRONIC_SHA1_ARM64=e0f0c06ebc5627e43b25475711e694450489ab00
RUN set -eu; \
    arch="${TARGETARCH:-amd64}"; \
    case "$arch" in \
      amd64) sha="$SUPERCRONIC_SHA1_AMD64" ;; \
      arm64) sha="$SUPERCRONIC_SHA1_ARM64" ;; \
      *) echo "unsupported arch $arch" >&2; exit 1 ;; \
    esac; \
    python -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], '/supercronic')" \
      "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${arch}"; \
    echo "${sha}  /supercronic" | sha1sum -c -; \
    chmod 0755 /supercronic

FROM ${BASE_IMAGE} AS runtime
LABEL org.opencontainers.image.title="otterworks-etl-legacy-cron" \
      org.opencontainers.image.source="https://github.com/Cognition-Partner-Workshops/otterworks" \
      org.opencontainers.image.description="Legacy OtterWorks ETL cron (etl/crontab via etl/run.sh) for Airflow coexistence"
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC
COPY requirements.txt /tmp/legacy-requirements.txt
COPY tests/golden/legacy/constraints.txt /tmp/constraints.txt
COPY tests/golden/legacy/requirements-shim.txt /tmp/requirements-shim.txt
RUN pip install -r /tmp/legacy-requirements.txt -r /tmp/requirements-shim.txt -c /tmp/constraints.txt \
    && rm /tmp/*.txt \
    && useradd --create-home --uid 10001 etl \
    && mkdir -p /opt/etl/scripts /opt/legacy-cron/golden/harness /var/log/etl /run/legacy-etl \
    && ln -s /run/legacy-etl/config.ini /opt/etl/config.ini \
    && chown etl /var/log/etl /run/legacy-etl
COPY --from=supercronic /supercronic /usr/local/bin/supercronic
COPY legacy-cron/legacy_cron.py /opt/legacy-cron/legacy_cron.py
USER etl
WORKDIR /opt/etl
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD ["python3", "/opt/legacy-cron/legacy_cron.py", "healthcheck"]
ENTRYPOINT ["python3", "/opt/legacy-cron/legacy_cron.py"]
CMD ["serve"]
