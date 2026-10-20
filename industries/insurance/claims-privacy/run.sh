#!/usr/bin/env bash
# Claims privacy module driver.
#   ./run.sh up       start PostgreSQL 16 and load kit, schema, seed, access
#   ./run.sh test     access and retention tests
#   ./run.sh compare  run queries/claimant_lookup.sql as reader_demo and adjuster_demo, side by side
#   ./run.sh down     stop and remove the container and its data
# NS (default: local) namespaces the compose project.
set -euo pipefail
cd "$(dirname "$0")"
MODULE="$PWD"
KIT="$(git rev-parse --show-toplevel)/shared/compliance-kit/postgres"
PROJECT="claims-privacy-${NS:-local}"
DC=(docker compose -p "$PROJECT" -f docker-compose.yml)

psql_as() {
  local user="$1"; shift
  "${DC[@]}" exec -T -e PGPASSWORD="$user" -e PGOPTIONS="-c client_min_messages=warning" claims-pg \
    psql -X -q -v ON_ERROR_STOP=1 -h localhost -U "$user" -d claims "$@"
}

load() { psql_as claims_owner < "$1"; }

case "${1:-}" in
  up)
    "${DC[@]}" up -d --wait
    # The last script creates purge_closed_claim_pii, so it marks a complete load.
    case "$(psql_as claims_owner -tAc "SELECT (to_regnamespace('claims') IS NOT NULL)::int + (to_regproc('claims.purge_closed_claim_pii') IS NOT NULL)::int")" in
      2) echo "== claims privacy already loaded ($PROJECT)"; exit 0 ;;
      1) echo "== partial load in $PROJECT: run ./run.sh down, then up" >&2; exit 1 ;;
    esac
    for f in "$KIT"/01_masking.sql "$KIT"/02_audit.sql "$KIT"/03_retention.sql sql/*.sql; do load "$f"; done
    echo "== claims privacy ready ($PROJECT)"
    ;;
  test)
    for f in tests/test_*.sql; do
      "${DC[@]}" exec -T -e PGPASSWORD=claims_owner claims-pg \
        psql -X -q -v ON_ERROR_STOP=1 -h localhost -U claims_owner -d claims < "$f" 2>&1 | sed 's/^NOTICE:  //'
    done
    ;;
  compare)
    out="${2:-$MODULE/build}"
    mkdir -p "$out"
    psql_as reader_demo --csv < queries/claimant_lookup.sql > "$out/reader.csv"
    psql_as adjuster_demo --csv < queries/claimant_lookup.sql > "$out/adjuster.csv"
    python3 queries/side_by_side.py "$out/reader.csv" "$out/adjuster.csv"
    ;;
  down)
    "${DC[@]}" down -v --remove-orphans
    ;;
  *)
    sed -n '2,8p' "$0"; exit 2 ;;
esac
