#!/usr/bin/env bash
# Apply the w1-b02 Lakebase DDL to ow_tp (project ow-tp-billing, branch mig-invoicing-w1)
# as the migration service principal, in dependency order: 10_ow_tp_invoicing_state.sql
# creates the fourteen tables (+ sequences + trg_usage_events_check), then
# 11_pkg_ow_util.sql, 12_pkg_plans.sql, 13_pkg_rating.sql, 14_pkg_invoicing.sql and
# 15_pkg_dunning.sql install the converted package routines, triggers and job procedures.
# A rerun lands the declared shape and must be followed by extract_state.py | load_state.py.
# Connection: LAKEBASE_MIGRATION_DSN env var (libpq DSN; password is the token minted by
# `databricks postgres generate-database-credential`) — nothing here prints or stores it.
set -euo pipefail
cd "$(dirname "$0")"

if [ -z "${LAKEBASE_MIGRATION_DSN:-}" ]; then
  echo "LAKEBASE_MIGRATION_DSN is not set" >&2
  exit 2
fi

psql "$LAKEBASE_MIGRATION_DSN" \
  -v ON_ERROR_STOP=1 \
  -f 10_ow_tp_invoicing_state.sql \
  -f 11_pkg_ow_util.sql \
  -f 12_pkg_plans.sql \
  -f 13_pkg_rating.sql \
  -f 14_pkg_invoicing.sql \
  -f 15_pkg_dunning.sql
