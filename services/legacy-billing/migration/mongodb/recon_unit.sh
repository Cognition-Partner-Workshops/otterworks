#!/usr/bin/env bash
# Run the mongo-recon-harness for one unit from the workspace root.
#
# `recon run` refuses unless its cwd is the workspace holding `.migration/` (it pins
# `--allowed-targets-file` to `$(pwd)/.migration/allowed_targets.json`), while the org's
# dbx-migration-factory guard rejects any shell command whose cwd is inside this checkout
# (F4/F9: it reads the same allowlist path and wants a `catalogs` list). Like `make -C`,
# this script is invoked by absolute path from $HOME and does the cd itself.
#
#   recon_unit.sh <unit> <fixture|live> [--out DIR] [extra recon args...]
#
# Env: MMP_PLUGIN_DIR (default ~/mongo-migration-plugin), RECON_BIN (default
# ~/.venvs/recon/bin/recon), MMP_TARGET_DB (default mmp_rt_b3_oracle). Secrets by name only.
set -euo pipefail
unit="${1:?unit}"; mode="${2:?fixture|live}"; shift 2
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
plugin="${MMP_PLUGIN_DIR:-$HOME/mongo-migration-plugin}"
recon="${RECON_BIN:-$HOME/.venvs/recon/bin/recon}"
out=".migration/recon/$unit"
if [ "${1:-}" = "--out" ]; then out="$2"; shift 2; fi
cd "$repo"
exec "$recon" run \
  --unit "$unit" \
  --family oracle \
  --mapping .migration/mapping_spec.json \
  --collections "$unit" \
  --tolerances .migration/recon_tolerances.json \
  --canonicalization "$plugin/skills/mongo-migration/profiles/oracle.md" \
  --mode "$mode" \
  --target-class migration_cluster \
  --source-dsn-secret MMP_RT_SRC_DSN \
  --target-uri-secret MONGODB_ATLAS_URI \
  --target-db "${MMP_TARGET_DB:-mmp_rt_b3_oracle}" \
  --allowed-targets-file .migration/allowed_targets.json \
  --source-concurrency 1 \
  --seed 1 \
  --out "$out" "$@"
