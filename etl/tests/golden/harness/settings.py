"""Paths, local endpoints and dev-only credentials used by the harness.

Every endpoint is local (docker-compose.infra.yml); nothing here ever points
at a cloud account. Values can be overridden with the GOLDEN_* env vars.
"""

from __future__ import annotations

import os
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parent.parent
ETL_DIR = GOLDEN_DIR.parent.parent
REPO_ROOT = ETL_DIR.parent
LEGACY_DIR = GOLDEN_DIR / "legacy"
RUNS_DIR = GOLDEN_DIR / ".runs"
SQL_DIR = Path(__file__).resolve().parent / "sql"

SCRIPTS = (
    "analytics_daily",
    "audit_archive_weekly",
    "search_reindex_weekly",
    "storage_cleanup_daily",
    "user_activity_daily",
)

LOCALSTACK_URL = os.environ.get("GOLDEN_LOCALSTACK_URL", "http://localhost:4566")
MEILI_URL = os.environ.get("GOLDEN_MEILI_URL", "http://localhost:7700")
MEILI_API_KEY = "golden-dev-key"
AWS_REGION = "us-east-1"
AWS_ACCESS_KEY = "test"
AWS_SECRET_KEY = "test"

PG_HOST = os.environ.get("GOLDEN_PG_HOST", "localhost")
PG_PORT = int(os.environ.get("GOLDEN_PG_PORT", "5432"))
PG_USER = "otterworks"
PG_PASSWORD = "otterworks_dev"
PG_ADMIN_DB = "otterworks"
PG_DB = "otterworks_etl_golden"

# Resources the scripts expect that scripts/localstack-init.sh does not create.
HARNESS_QUEUES = ("otterworks-analytics",)
HARNESS_TABLES = {
    "otterworks-analytics-events": [("event_id", "S", "HASH")],
}
HARNESS_BUCKETS = ("otterworks-file-storage", "otterworks-file-quarantine")
HARNESS_PG_DDL = ("analytics_daily_summary.sql",)

# Bucket names the generated config.ini hands to the scripts.
S3_CONFIG = {
    "data_lake_bucket": "otterworks-data-lake",
    "analytics_prefix": "analytics/daily",
    "archive_bucket": "otterworks-audit-archive",
    "file_storage_bucket": "otterworks-file-storage",
    "quarantine_bucket": "otterworks-file-quarantine",
}

# infra.reset() empties every bucket, table, queue and index it can reach. It only
# runs when every endpoint is one of these hosts and the caller opted in
# (`make etl-golden` sets RESET_OPT_IN_ENV=1).
RESET_ALLOWED_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "localstack", "postgres", "meilisearch"}
)
RESET_OPT_IN_ENV = "GOLDEN_ALLOW_RESET"

LEGACY_IMAGE_REPO = "otterworks-etl-legacy"
LEGACY_BASE_IMAGE = os.environ.get("GOLDEN_LEGACY_BASE_IMAGE", "python:3.9-slim")
DOCKER_NETWORK = os.environ.get("GOLDEN_DOCKER_NETWORK", "host")
CONTAINER_TIMEOUT_SECONDS = int(os.environ.get("GOLDEN_CONTAINER_TIMEOUT", "600"))
