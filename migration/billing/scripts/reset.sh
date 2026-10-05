#!/usr/bin/env bash
# Reset the MongoDB migration target between rehearsals.
#
#   TARGET=fallback  drop every ow_tp_billing_* database on the local mongo:7 fixture
#                    (container ow-billing-mongo, 127.0.0.1 only) and list what is left
#   TARGET=atlas     drop every collection of DB=ow_tp_billing_<run> through MONGODB_ATLAS_URI
#                    (by name, never printed). readWrite allows dropCollection but not
#                    dropDatabase, so the empty database name stays until Atlas reaps it. The
#                    scoped user is recreated by a human with the Atlas CLI command in
#                    migration/billing/README.md
#   RESEED=1         also reseed the Oracle fixture with NS=demo (deterministic)
#
# The application backend is chosen by the BILLING_BACKEND environment variable of the
# process that serves it; restart legacy-billing with BILLING_BACKEND=oracle after a reset.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TARGET="${TARGET:-fallback}"
CONTAINER="${MONGO_BILLING_CONTAINER:-ow-billing-mongo}"
DB_RE='^ow_tp_billing_[A-Za-z0-9]+$'
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
redact() { sed -E 's#mongodb(\+srv)?://[^[:space:]"]+#mongodb://<redacted>#g'; }

case "$TARGET" in
  fallback)
    docker inspect "$CONTAINER" >/dev/null 2>&1 || { echo "$(stamp) reset: $CONTAINER is not running; nothing to drop"; exit 0; }
    echo "$(stamp) reset: fallback mongo:7 ($CONTAINER), dropping ow_tp_billing_* databases"
    docker exec "$CONTAINER" mongosh --quiet --eval '
      const re = /^ow_tp_billing_[A-Za-z0-9]+$/;
      db.adminCommand({listDatabases: 1, nameOnly: true}).databases.map(d => d.name).filter(n => re.test(n))
        .forEach(n => { db.getSiblingDB(n).dropDatabase(); print("dropped " + n); });
      const left = db.adminCommand({listDatabases: 1, nameOnly: true}).databases.map(d => d.name);
      print("databases after reset: " + JSON.stringify(left));
      const stray = left.filter(n => !["admin", "config", "local"].includes(n));
      if (stray.length) { print("NOT EMPTY: " + JSON.stringify(stray)); quit(1); }
      print("fallback target empty: only admin, config and local remain");'
    ;;
  atlas)
    [[ "${DB:-}" =~ $DB_RE ]] || { echo "reset: DB must match $DB_RE for TARGET=atlas" >&2; exit 2; }
    [ -n "${MONGODB_ATLAS_URI:-}" ] || { echo "reset: MONGODB_ATLAS_URI is not set; nothing dropped" >&2; exit 2; }
    command -v mongosh >/dev/null 2>&1 || { echo "reset: mongosh is required for TARGET=atlas" >&2; exit 2; }
    echo "$(stamp) reset: atlas, dropping every collection of $DB through MONGODB_ATLAS_URI"
    set +e
    mongosh "$MONGODB_ATLAS_URI" --quiet --eval "
      const t = db.getSiblingDB('$DB');
      t.getCollectionNames().forEach(c => { t.getCollection(c).drop(); print('dropped $DB.' + c); });
      const left = t.getCollectionNames().length;
      print('collections left in $DB: ' + left);
      if (left) quit(1);" 2>&1 | redact
    rc=${PIPESTATUS[0]}
    set -e
    [ "$rc" = 0 ] || { echo "reset: atlas drop failed (exit $rc)" >&2; exit "$rc"; }
    ;;
  *) echo "reset: TARGET must be fallback or atlas (got $TARGET)" >&2; exit 2 ;;
esac

if [ "${RESEED:-}" = 1 ]; then
  echo "$(stamp) reset: reseeding the Oracle fixture with NS=demo"
  make -C "$REPO_ROOT" -s oracle-billing-seed NS=demo
fi
echo "$(stamp) reset: done; serve legacy-billing with BILLING_BACKEND=oracle until the next switch"
