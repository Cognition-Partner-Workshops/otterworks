#!/usr/bin/env bash
# Return both on-call tenants and both branches to the before state:
#   1. disarm both (stop k6, worker off through a helm upgrade)
#   2. truncate the seeded data, drop the fix index if a proof created it, and
#      stamp alembic back to the last baseline revision when needed
#   3. force demo-oncall-before / demo-oncall-after back to origin/main, only
#      when they differ (CD then redeploys the golden build)
#   4. clear the incident channel threads and incident/oncall/.state
#
# Usage: incident/oncall/reset.sh
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_bins git kubectl helm jq curl
ensure_kubeconfig

# ---------- 1. disarm ----------
"${ONCALL_DIR}/disarm.sh" "${BEFORE_TENANT}" "${AFTER_TENANT}"

# ---------- 2. data ----------
git -C "${REPO}" fetch -q origin main
baseline_head="$(git -C "${REPO}" ls-tree --name-only origin/main services/document-service/alembic/versions/ |
  sed -nE 's#.*/([0-9]{3})_[^/]*\.py$#\1#p' | sort | tail -n 1)"
for tenant in "${BEFORE_TENANT}" "${AFTER_TENANT}"; do
  ns="$(tenant_ns "${tenant}")"
  if ! kubectl -n "${ns}" get deploy "${PG_DEPLOY}" >/dev/null 2>&1; then
    warn "no ${PG_DEPLOY} in ${ns}; nothing to truncate"
    continue
  fi
  log "Truncating seeded data in ${ns}"
  pg "${tenant}" -v fix_index="${FIX_INDEX}" -v baseline="${baseline_head}" -f - <<'SQL'
SET statement_timeout = 0;
DO $$
BEGIN
  IF to_regclass('public.folder_digests') IS NOT NULL THEN
    TRUNCATE folder_digests;
  END IF;
  IF to_regclass('public.documents') IS NOT NULL THEN
    TRUNCATE documents CASCADE;
  END IF;
END
$$;
DROP INDEX IF EXISTS :"fix_index";
SELECT to_regclass('public.alembic_version') IS NOT NULL AS has_alembic \gset
\if :has_alembic
UPDATE alembic_version SET version_num = :'baseline' WHERE version_num > :'baseline';
\endif
SQL
done

# ---------- 3. branches ----------
main_sha="$(git -C "${REPO}" rev-parse origin/main)"
for tenant in "${BEFORE_TENANT}" "${AFTER_TENANT}"; do
  branch="$(tenant_branch "${tenant}")"
  remote_sha="$(git -C "${REPO}" ls-remote --heads origin "${branch}" | awk '{print $1}')"
  if [ -z "${remote_sha}" ]; then
    warn "${branch} does not exist; make oncall-up creates it"
  elif [ "${remote_sha}" = "${main_sha}" ]; then
    log "${branch} already equals origin/main"
  else
    log "Forcing ${branch} ${remote_sha:0:12} -> origin/main ${main_sha:0:12}"
    git -C "${REPO}" push -q --force-with-lease="refs/heads/${branch}:${remote_sha}" \
      origin "${main_sha}:refs/heads/${branch}"
  fi
done

# ---------- 4. channel and state ----------
token="$(secret_value "${PLATFORM_NS}" incident-channel-secrets CHANNEL_TOKEN)"
if [ -n "${token}" ]; then
  if printf 'header = "Authorization: Bearer %s"\n' "${token}" |
     curl -fsS --max-time 15 --config - -X POST -o /dev/null "https://${CHANNEL_HOST}/api/reset"; then
    log "Incident channel threads cleared"
  else
    warn "incident channel reset failed; clear it from the page or retry"
  fi
else
  warn "CHANNEL_TOKEN not readable; incident channel threads left as they are"
fi
rm -rf "${STATE_DIR}"
log "Reset done. Both tenants are on origin/main with no seed, no load and the worker off."
