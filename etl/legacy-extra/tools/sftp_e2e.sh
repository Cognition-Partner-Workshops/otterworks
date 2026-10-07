#!/usr/bin/env bash
# sftp_e2e.sh <legacy|python> [ns] — put a generated CUSTBILL file through the
# SFTP drop fixture (make legacy-sftp-up), run sftp_ingest_poll with the chosen
# implementation and check: the file arrived in incoming/ (cmp), it left the
# drop, and an archive copy exists. Uses OTTERWORKS_LEGACY_ROOT, which must be
# the root the fixture was started with. Demo credentials come from the
# compose file (localhost-only fixture).
set -euo pipefail
ESTATE=$(cd "$(dirname "$0")/.." && pwd)
IMPL=${1:?usage: sftp_e2e.sh <legacy|python> [ns]}
NS=${2:-dev}
ROOT=${OTTERWORKS_LEGACY_ROOT:-/tmp/otterworks-legacy}
CMD=$(sed -n 's/^ *command: *\([^:]*\):\([^:]*\):.*/\1 \2/p' "$ESTATE/docker-compose.sftp.yml")
SFTP_USER=${CMD% *}; SFTP_PASS=${CMD#* }
command -v sshpass >/dev/null || { echo "sshpass required"; exit 2; }

stage=$(mktemp -d)
OTTERWORKS_LEGACY_ROOT=$stage TZ=UTC LC_ALL=C perl "$ESTATE/tools/gen_sample_data.pl" "$NS" 1 > /dev/null
f=$(ls "$stage/sftp-drop/upload/")
mkdir -p "$ROOT/incoming"
rm -f "$ROOT/incoming/$f" "$ROOT/incoming/$f.done"
echo "put $stage/sftp-drop/upload/$f upload/" | sshpass -p "$SFTP_PASS" sftp -oBatchMode=no -P 52222 \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -b - "$SFTP_USER@127.0.0.1" > /dev/null
echo "sftp put: $f -> $ROOT/sftp-drop/upload/ ($(wc -c < "$ROOT/sftp-drop/upload/$f") bytes)"
if [ "$IMPL" = python ]; then
  OTTERWORKS_LEGACY_ROOT=$ROOT TZ=UTC LC_ALL=C python3 "$ESTATE/pyjobs/sftp_ingest_poll.py"
else
  OTTERWORKS_LEGACY_ROOT=$ROOT TZ=UTC LC_ALL=C ksh "$ESTATE/jobs/sftp_ingest_poll.ksh"
fi
rc=0
if cmp "$stage/sftp-drop/upload/$f" "$ROOT/incoming/$f"; then echo "PASS arrived in incoming (cmp identical)"; else echo "FAIL incoming"; rc=1; fi
if [ ! -e "$ROOT/sftp-drop/upload/$f" ]; then echo "PASS left the drop"; else echo "FAIL still in drop"; rc=1; fi
if ls "$ROOT/archive/$f".* > /dev/null 2>&1; then echo "PASS archived ($(cd "$ROOT/archive" && ls "$f".* | tail -1))"; else echo "FAIL archive"; rc=1; fi
rm -rf "$stage"
exit $rc
