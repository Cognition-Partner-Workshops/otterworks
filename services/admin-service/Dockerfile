# Opt-in Databricks read path: build with --build-context contract-kit=consumers/contract-kit.
# Without it this empty stage is used and the image keeps only the default Teradata path.
FROM scratch AS contract-kit

FROM ruby:3.3-slim AS builder

RUN apt-get update && apt-get install -y build-essential libpq-dev libyaml-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY Gemfile Gemfile.lock ./
RUN bundle config set --local without 'test development' && bundle install

FROM ruby:3.3-slim
RUN apt-get update && apt-get install -y libpq5 curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /usr/local/bundle /usr/local/bundle
COPY . .
# DatabricksClient resolves the shared bridge at /consumers/contract-kit from /app/app/services/finance_warehouse.
COPY --from=contract-kit / /consumers/contract-kit/
ENV CONTRACT_KIT_PYTHON=/opt/contract-kit-venv/bin/python
RUN if [ -f /consumers/contract-kit/databricks_bridge.py ]; then \
      apt-get update && apt-get install -y --no-install-recommends python3 python3-venv && rm -rf /var/lib/apt/lists/* && \
      python3 -m venv /opt/contract-kit-venv && \
      /opt/contract-kit-venv/bin/pip install --no-cache-dir -r /consumers/contract-kit/requirements-databricks.txt; \
    fi

RUN useradd -r -u 1001 appuser && mkdir -p /app/tmp/pids /app/tmp/cache /app/log && chown -R appuser:appuser /app/tmp /app/log
USER appuser

EXPOSE 8089
HEALTHCHECK --interval=15s --timeout=5s CMD curl -f http://localhost:8089/health || exit 1
CMD ["sh", "-c", "bundle exec rails db:migrate; bundle exec rails server -b 0.0.0.0 -p 8089"]
