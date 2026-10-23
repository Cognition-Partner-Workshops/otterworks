#!/usr/bin/env bash
# Nightly housekeeping, run from cron on the batch host at 02:15 UTC:
#   15 2 * * * /opt/otterworks/scripts/nightly-share-links-purge.sh
set -euo pipefail

SHARE_LINKS_URL="${SHARE_LINKS_URL:-http://share-links.internal:8080/share-links}"

curl -fsS -X POST -A "otterworks-nightly/2.3" "${SHARE_LINKS_URL}/admin/purge-expired"
echo
