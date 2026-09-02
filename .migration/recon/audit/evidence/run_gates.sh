#!/usr/bin/env bash
# Independent audit re-run of sampled gates. Fixture-local dev DSNs only (00_context: not org secrets).
set -uo pipefail
cd /home/ubuntu/repos/otterworks
source /home/ubuntu/audit-venv-packera/bin/activate
export OW_BILLING_FIXTURE_DSN="<fixture-local dev DSN; value not recorded>"
export OW_PG_DSN="<fixture-local dev DSN; value not recorded>"
export AWS_ENDPOINT_URL="http://localhost:4566"
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1
A=/home/ubuntu/audit_work/run_packera; mkdir -p "$A"
MAP=.migration/03_mapping_spec.json; TOL=.migration/02_tolerances.json; CAN=.migration/canonicalization.json
COMMON=(--tolerances "$TOL" --canonicalization "$CAN" --mode live --target-uri-secret MONGODB_ATLAS_URI \
        --target-db ow_tp_mongodb_205236 --seed 714559852 --param batch_no=85559852 --param source_ns=demo)
log(){ echo "[$(date -u +%H:%M:%S)] $*"; }
log "source_pre"; python /home/ubuntu/audit_work/source_check.py "$A/source_pre.json" 2>&1 | tail -3
for U in U0 U1 U2 U5; do
  mkdir -p "$A/$U"; python /home/ubuntu/audit_work/subset.py "$MAP" "$U" "$A/$U/mapping_${U,,}_subset.json"
  log "$U oracle"; recon run --unit $U --family oracle --mapping "$A/$U/mapping_${U,,}_subset.json" \
       --source-dsn-secret OW_BILLING_FIXTURE_DSN "${COMMON[@]}" --out "$A/$U/gate" > "$A/$U/stdout.log" 2>&1; echo "  exit=$?"
done
mkdir -p "$A/U3" "$A/U4"
log "U3 postgres"; python .migration/recon_ext/recon_pg.py --unit U3 --family postgres --mapping "$MAP" --unit-only \
     --source-dsn-secret OW_PG_DSN "${COMMON[@]}" --out "$A/U3/gate" > "$A/U3/stdout.log" 2>&1; echo "  exit=$?"
log "U4 dynamo"; python .migration/recon_ext/run_dynamo_recon.py --unit U4 --mapping "$MAP" \
     --source-endpoint-secret AWS_ENDPOINT_URL "${COMMON[@]}" --out "$A/U4/gate" > "$A/U4/stdout.log" 2>&1; echo "  exit=$?"
for U in U7 U8; do
  mkdir -p "$A/$U"
  log "$U clone reset"; python scripts/tp_mongo/load_${U,,}.py --report "$A/$U/load_report.json" > "$A/$U/load.log" 2>&1; echo "  exit=$?"
  log "$U tier1-4"; python .migration/recon_ext/recon_${U,,}.py --unit $U --mapping "$MAP" \
       --source-dsn-secret OW_BILLING_FIXTURE_DSN "${COMMON[@]}" --out "$A/$U/gate" > "$A/$U/stdout.log" 2>&1; echo "  exit=$?"
done
log "source_post"; python /home/ubuntu/audit_work/source_check.py "$A/source_post.json" 2>&1 | tail -3
log "guards"; python /home/ubuntu/audit_work/guards.py "$A" 2>&1 | tail -5
log done
