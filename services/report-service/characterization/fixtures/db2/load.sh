#!/bin/bash
# Runs inside the db2 container as db2inst1: applies migration/source/db2/ddl (mounted at /ldm-ddl)
# and the characterization fixture to CHARDB. Idempotent: skips when ARCHIVE.DOCARCH has rows.
set -euo pipefail
. ~/sqllib/db2profile
db2 connect to CHARDB >/dev/null
if db2 -x "SELECT COUNT(*) FROM ARCHIVE.DOCARCH" 2>/dev/null | grep -qv '^ *0$'; then
  echo "fixture already loaded"; exit 0
fi
for f in /ldm-ddl/*.sql; do
  db2 -tvf "$f" > /tmp/ddl.log 2>&1 || { grep -E 'SQL[0-9]+N' /tmp/ddl.log; exit 8; }
done
db2 -tvf /fixtures/fixture.sql > /tmp/fixture.log 2>&1 || { grep -E 'SQL[0-9]+N' /tmp/fixture.log; exit 8; }
db2 -x "SELECT COUNT(*) FROM ARCHIVE.DOCARCH"
db2 connect reset >/dev/null
