# syntax=docker/dockerfile:1
# OtterWorks ETL on Apache Airflow 2.8 (etl/ETL_UPGRADE_GUIDE.md).
# Stage 1 resolves the Airflow constraints file and builds the otterworks_etl wheel;
# stage 2 installs the providers and the wheel against those constraints onto a clean
# official image, so build tooling and sources never reach the runtime layer.
ARG AIRFLOW_VERSION=2.8.4
ARG PYTHON_VERSION=3.11

FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION} AS build
ARG AIRFLOW_VERSION
ARG PYTHON_VERSION
USER root
RUN mkdir -p /build && chown airflow:root /build
USER airflow
WORKDIR /build
RUN curl -fsSL -o constraints.txt \
      "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
COPY --chown=airflow:root pyproject.toml ./
COPY --chown=airflow:root otterworks_etl ./otterworks_etl
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels .

FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION} AS runtime
LABEL org.opencontainers.image.title="otterworks-etl-airflow" \
      org.opencontainers.image.source="https://github.com/Cognition-Partner-Workshops/otterworks" \
      org.opencontainers.image.description="OtterWorks ETL DAGs on Apache Airflow 2.8 (LocalExecutor)"
COPY --from=build --chown=airflow:root /build/constraints.txt /build/wheels/ /tmp/otterworks/
COPY --chown=airflow:root requirements.txt /tmp/otterworks/requirements.txt
RUN pip install --no-cache-dir \
      --constraint /tmp/otterworks/constraints.txt \
      -r /tmp/otterworks/requirements.txt \
      /tmp/otterworks/otterworks_etl-*.whl \
 && pip check \
 && rm -rf /tmp/otterworks
COPY --chown=airflow:root dags/ /opt/airflow/dags/
USER airflow
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD curl --fail --silent --show-error http://localhost:8080/health || exit 1
