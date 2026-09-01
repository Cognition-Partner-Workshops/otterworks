#!/usr/bin/env bash
# Final delta catch-up (phase 4): re-grade every loaded unit against Oracle at one watermark.
#
# The recon harness reads the source live, so running it at the watermark IS the watermark
# recon -- any row the estate changed since the wave loads shows up here as a failing tier,
# not as a silently stale document. Results land beside the wave results as
# result.watermark.json so the two can be compared rather than overwritten.
set -euo pipefail

cd "$(dirname "$0")/../.."
source /home/ubuntu/.ow_oracle_dsn

PY=/home/ubuntu/.mongo-venv/bin
WATERMARK=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "watermark: $WATERMARK"

for unit in reference customers subscriptions invoices usage_rating subscription_invoices collections_ops; do
    echo "=== $unit"
    "$PY/recon" run \
        --unit "$unit" \
        --family oracle \
        --mapping ".migration/mapping/$unit.json" \
        --tolerances .migration/02_tolerances.json \
        --canonicalization .migration/recon_canonicalization.json \
        --mode live \
        --source-dsn-secret OW_ORACLE_BILLING_DSN \
        --target-uri-secret MONGODB_ATLAS_URI \
        --target-db ow_tp_mongodb_orc1 \
        --source-concurrency 1 \
        --seed 20260901 \
        --param batch_no=85559852 \
        --out ".migration/recon/$unit/watermark"
done
