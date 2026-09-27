#!/usr/bin/env bash
# Idempotent apply of the lakebase_scaffold DDL on Lakebase branch mig-20260927b-w0.
# Drops/recreates only billing.codes, billing.plans, billing.tenants, billing.usage_events
# (plus CREATE SCHEMA IF NOT EXISTS billing). Auth via ~/.pgpass written from
# `databricks postgres generate-database-credential`; the host is a literal.
# Usage: apply.sh [current|prior]   (default: current = 00_scaffold.sql; prior = 00_scaffold.prior.sql)
set -euo pipefail
cd "$(dirname "$0")"
export PGSSLMODE=require
case "${1:-current}" in
  current)
    psql -v ON_ERROR_STOP=1 -q -X -h ep-calm-sea-d1avwe82.database.us-west-2.cloud.databricks.com -p 5432 \
      -U d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 -d ow_tp --single-transaction -f 00_scaffold.sql
    echo "apply.sh: applied 00_scaffold.sql on ow_tp (branch mig-20260927b-w0)" ;;
  prior)
    psql -v ON_ERROR_STOP=1 -q -X -h ep-calm-sea-d1avwe82.database.us-west-2.cloud.databricks.com -p 5432 \
      -U d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 -d ow_tp --single-transaction -f 00_scaffold.prior.sql
    echo "apply.sh: applied 00_scaffold.prior.sql on ow_tp (branch mig-20260927b-w0)" ;;
  *) echo "apply.sh: unknown target (current|prior)" >&2; exit 2 ;;
esac
