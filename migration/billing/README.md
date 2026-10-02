# OtterWorks billing: Oracle `OW_BILLING` to MongoDB Atlas

Migration artifacts for the Oracle-to-Atlas billing run live under this
directory. Every PR targets the run branch `tp-run/mongodb-20261001T233613Z`.
Oracle `OW_BILLING` is read-only for the whole run; Atlas writes go only to the
migration database named below. Secrets are referenced by name only
(`MONGODB_ATLAS_URI`, `OW_TP_ORACLE_RO_DSN`).

## Target

| Item | Value |
|---|---|
| Atlas project | `otterworks-demos` |
| Cluster | `otterworks-demo` (M0, 512 MB, so `SCALE=demo` data only; `SCALE=full` needs an M10+ tier, out of scope) |
| Migration database (decision `d-migration-db`: fresh `ow_tp_billing_<run>` per run) | `ow_tp_billing_20261001T233613Z` |
| Principal | `otterworks-app` (`readWriteAnyDatabase`, `dbAdminAnyDatabase` on `admin`), accepted for this run by decision below; the scoped target was exactly `readWrite@ow_tp_billing_20261001T233613Z` |

The run id is the timestamp of the run branch (`tp-run/mongodb-20261001T233613Z`).

## Write scope check

`migration/billing/scripts/atlas-scope-check.sh` connects with `MONGODB_ATLAS_URI`,
runs `connectionStatus` with `showPrivileges`, and passes only when the
principal's roles are exactly `readWrite` on the migration database. Only in
that case does it run the probes: an insert into another database
(`<db>_denied_probe`) must be refused by Atlas with `Unauthorized` (code 13),
and an insert into the migration database must succeed (the probe document is
deleted again). When the principal is over-scoped the probes are skipped,
because the negative probe would otherwise succeed and write outside the
migration database.

```bash
migration/billing/scripts/atlas-scope-check.sh \
  --db ow_tp_billing_20261001T233613Z \
  --out migration/billing/evidence/atlas-scope-check.json
```

Exit code 0 is PASS; anything else is FAIL. The JSON evidence is written to
`--out` and printed; it contains the username and roles, never the URI.

## Decision (2026-10-01): existing principal accepted for this run

The scope check FAILs against the principal currently in `MONGODB_ATLAS_URI`,
and the human decided to keep using it for this run rather than provision a
dedicated user ("Go ahead and use the existing one and continue for this
run", recorded on UNT-3). Consequences:

- Atlas does **not** enforce the write boundary for this run. The rule "Atlas
  writes only to `ow_tp_billing_20261001T233613Z`" is enforced by convention:
  every migration script takes the database name explicitly and writes
  nowhere else; reviewers check the target database on each PR.
- The acceptance probe (an insert into another database refused with code 13)
  cannot be produced, because that insert would succeed. It was not run, since
  it would itself be a write outside the migration database.
- `migration/billing/evidence/atlas-scope-check.json` stays at `FAIL` as the
  live record of the principal's roles. Later tickets do not need to rerun it.
- A later tier bump or a `SCALE=full` run should revisit this and provision
  the dedicated user below.

## Principal in `MONGODB_ATLAS_URI` (live, 2026-10-01)

`connectionStatus` for the principal currently in `MONGODB_ATLAS_URI`
(`migration/billing/evidence/atlas-scope-check.json`):

```json
"principal": {
  "user": "otterworks-app",
  "authDb": "admin",
  "roles": [
    {"role": "readWriteAnyDatabase", "db": "admin"},
    {"role": "dbAdminAnyDatabase", "db": "admin"}
  ]
}
```

`otterworks-app` can write to every database on the cluster, including the
other demo databases that live there (`ow_tp_mmp_live`, `ow_tp_mongodb_*`,
`ow_billing_migration`). Its roles must not be narrowed, because other demo
state depends on it; the scoped alternative is a dedicated user.

### Dedicated user (reference; not applied for this run by decision above)

Create a dedicated database user whose only role is `readWrite` on the
migration database, scoped to the migration cluster, then repoint the
`MONGODB_ATLAS_URI` secret at it. The same pattern is already in use on this
project for `ow_tp_mmp_live` (`readWrite@ow_tp_mmp_live`, scope
`otterworks-demo`).

Atlas CLI (`atlas auth login` as a project owner first; `MONGODB_ATLAS_PROJECT_ID`
is the `otterworks-demos` project id):

```bash
atlas dbusers create \
  --projectId "$MONGODB_ATLAS_PROJECT_ID" \
  --username ow_tp_billing_20261001T233613Z \
  --role readWrite@ow_tp_billing_20261001T233613Z \
  --scope otterworks-demo \
  --desc "OtterWorks billing migration run 20261001T233613Z (UNT-3)" \
  --password '<generate a new password; do not reuse otterworks-app>'
```

Atlas UI equivalent: project `otterworks-demos` > Security > Database Access >
Add New Database User > Password authentication; username
`ow_tp_billing_20261001T233613Z`; Database User Privileges > Specific Privileges >
`readWrite` with database `ow_tp_billing_20261001T233613Z` (collection blank);
Restrict Access to Specific Clusters > `otterworks-demo`; no other built-in
role, no `atlasAdmin`, no `readWriteAnyDatabase`.

Then update the `MONGODB_ATLAS_URI` secret to the new user. Keep the current
host and options and change only the credentials and default database:

```
mongodb+srv://ow_tp_billing_20261001T233613Z:<password>@<same host as today>/ow_tp_billing_20261001T233613Z?retryWrites=true&w=majority
```

Network access does not change: the cluster's IP access list is a project
setting and already admits the sessions that run this migration.

### Verifying if the dedicated user is ever provisioned

Rerun the scope check above from a fresh shell (so the rotated secret is
picked up). Expected:

- `principal.roles` is exactly `[{"role": "readWrite", "db": "ow_tp_billing_20261001T233613Z"}]`
- probe `ow_tp_billing_20261001T233613Z_denied_probe`: `"result": "refused"`, `"code": 13`, `"codeName": "Unauthorized"`
- probe `ow_tp_billing_20261001T233613Z`: `"result": "accepted"`
- `"verdict": "PASS"`, exit code 0

Commit the refreshed `migration/billing/evidence/atlas-scope-check.json` and
paste the probe output on the ticket; that output is the acceptance evidence.

### What `readWrite` does and does not allow

`readWrite` covers everything the data migration needs on the migration
database: `createCollection` (including `validator` / `$jsonSchema` at
creation time), `createIndex`, `insert`, `update`, `remove`, `find`,
`dropCollection`. It does not include `collMod` (changing a validator on an
existing collection), `dropDatabase`, or `enableProfiler`; those are `dbAdmin`
actions. If a later ticket needs `collMod`, it asks the manager for a decision
rather than widening the user.
