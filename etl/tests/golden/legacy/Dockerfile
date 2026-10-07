# Legacy ETL runtime for golden recordings: Python 3.9 with the exact pins in
# etl/requirements.txt. Scripts, run.sh, config.ini and the sitecustomize shim
# are bind-mounted read-only at run time, so the image never carries code.
# Build context: etl/
ARG BASE_IMAGE=python:3.9-slim
FROM ${BASE_IMAGE}

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
    && mkdir -p /opt/etl/scripts \
    && chown -R etl /opt/etl

USER etl
WORKDIR /opt/etl
CMD ["/opt/etl/run.sh"]
