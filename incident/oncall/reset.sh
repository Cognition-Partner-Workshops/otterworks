#!/usr/bin/env bash
# Return both on-call tenants and both branches to the before state:
#   1. truncate the seeded data, drop the fix index if a proof created it, and
#      stamp alembic back to the last baseline revision when needed. This runs
#      first: document-service runs alembic upgrade head on start, so a pod of
#      the baseline image crash-loops while the database is at 005, and the
#      disarm rollout would fail.
#   2. disarm both (stop k6, worker off through a helm upgrade)
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

# ---------- 1. data ----------
# The between-runs baseline is origin/main once it carries the on-call work, or
# the integration baseline while it has not merged (ONCALL_RESET_REF).
git -C "${REPO}" fetch -q origin main
reset_ref="${ONCALL_RESET_REF:-origin/main}"
baseline_head="$(branch_alembic_head "${reset_ref}")"
[ -n "${baseline_head}" ] || die "no document-service migrations found on ${reset_ref}"
for tenant in "${BEFORE_TENANT}" "${AFTER_TENANT}"; do
  ns="$(tenant_ns "${tenant}")"
  if ! kubectl -n "${ns}" get deploy "${PG_DEPLOY}" >/dev/null 2>&1; then
    warn "no ${PG_DEPLOY} in ${ns}; nothing to truncate"
    continue
  fi
  wake_postgres "${tenant}"
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

# ---------- 2. disarm ----------
"${ONCALL_DIR}/disarm.sh" "${BEFORE_TENANT}" "${AFTER_TENANT}"

# ---------- 3. branches ----------
main_sha="$(git -C "${REPO}" rev-parse "${reset_ref}")"
for tenant in "${BEFORE_TENANT}" "${AFTER_TENANT}"; do
  branch="$(tenant_branch "${tenant}")"
  remote_sha="$(git -C "${REPO}" ls-remote --heads origin "${branch}" | awk '{print $1}')"
  if [ -z "${remote_sha}" ]; then
    warn "${branch} does not exist; make oncall-up creates it"
  elif [ "${remote_sha}" = "${main_sha}" ]; then
    log "${branch} already equals ${reset_ref}"
  else
    log "Forcing ${branch} ${remote_sha:0:12} -> ${reset_ref} ${main_sha:0:12}"
    git -C "${REPO}" push -q --force-with-lease="refs/heads/${branch}:${remote_sha}" \
      origin "${main_sha}:refs/heads/${branch}"
  fi
done

# ---------- 4. channel and state ----------
token="$(secret_value "${PLATFORM_NS}" incident-channel-secrets CHANNEL_TOKEN)"
[ -n "${token}" ] ||
  die "CHANNEL_TOKEN not readable from ${PLATFORM_NS}/incident-channel-secrets; the incident channel still holds the old threads"
printf 'header = "Authorization: Bearer %s"\n' "${token}" |
  curl -fsS --max-time 15 --retry 2 --config - -X POST -o /dev/null "https://${CHANNEL_HOST}/api/reset" ||
  die "incident channel reset failed at https://${CHANNEL_HOST}/api/reset; rerun make oncall-reset"
log "Incident channel threads cleared"
rm -rf "${STATE_DIR}"
log "Reset done. Both tenants are on ${reset_ref} with no seed, no load and the worker off."
