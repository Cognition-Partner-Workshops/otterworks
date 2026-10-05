# OtterWorks billing: Oracle `OW_BILLING` to MongoDB Atlas

The migration harness for moving the legacy billing estate from Oracle
`OW_BILLING` into a MongoDB migration database. A run works on its own branch
`tp-run/mongodb-<timestamp>` and its own database `ow_tp_billing_<timestamp>`,
both cut by `make tp-run-branch TRACK=mongodb`. Every unit PR of a run targets
that branch. Oracle stays read-only for the whole run, and the target is
written only in the migration database. Secrets are referenced by name only:
`MONGODB_ATLAS_URI` and `OW_TP_ORACLE_RO_DSN`.

## Layout

| Path | Contents |
|---|---|
| `census/`, `census.json` | Census of `OW_BILLING` with one bucket per object |
| `access_patterns.md`, `access_patterns/` | Every Flask entrypoint mapped to the PL/SQL, tables and transaction it uses |
| `mapping_spec.json`, `mapping/` | Collections, document shapes and indexes, and the generator that writes them |
| `units.md`, `units/` | Units U1 to U5, their dependencies and the recon gate per unit |
| `loaders/oracle_to_mongo.py` | Loader: reads Oracle, maps through `recon.py`, upserts by `_id` |
| `fixtures/` | Anomaly manifest of the `NS=demo` seed and the element shape manifest the loader reads |
| `recon/` | Reconciliation, its self test and tests |
| `tolerances.json` | Exact tolerances, zero row difference |
| `env/` | Post setup checks and the blueprint proposal |
| `scripts/` | Atlas scope check, connectivity probe and the reset |
| `waves/` | Fixture recon and parity harnesses per wave |

Gate files a migration session does not edit: `recon/recon.py`,
`tolerances.json`, `mapping_spec.json`, `units/units.json` and
`scripts/atlas-scope-check.sh`. A change to one of them needs a plan decision
and a human review outside the migration sessions. The one scripted exception
is the run stamp: `make tp-run-branch` replaces the reference token in
`mapping_spec.json`, `units/units.json` and the Mongo backend with the new
run token, and changes nothing else.

## Local rehearsal

```bash
make oracle-billing-up                          # Oracle Free, first boot 10 to 20 minutes
make oracle-billing-seed NS=demo SCALE=demo
make mongo-billing-up                           # mongo:7 on 127.0.0.1:27117, never Atlas
OW_BILLING_ENV_MODE=auto migration/billing/env/postsetup-check.sh all
make tp-validate-schemas
make tp-u2-load MIGRATION_DB=ow_tp_billing_rehearsal
make tp-u2-recon MIGRATION_DB=ow_tp_billing_rehearsal OUT=/tmp/U2.local.recon.json
make tp-u2-parity
make tp-mongodb-reset                           # drops every ow_tp_billing_* database on the fixture
```

A fixture or local recon result is never merge evidence. Only
`recon.py run --mode live` against `OW_TP_ORACLE_RO_DSN` and
`MONGODB_ATLAS_URI` can be.

## Write scope check

`scripts/atlas-scope-check.sh` connects with `MONGODB_ATLAS_URI`, runs
`connectionStatus` with `showPrivileges`, and passes only when the principal's
roles are exactly `readWrite` on the migration database. Only then does it run
the probes: an insert into `<db>_denied_probe` must be refused with
`Unauthorized` (code 13), and an insert into the migration database must
succeed (the probe document is deleted again). An over-scoped principal fails
and the probes are skipped, because the negative probe would otherwise write
outside the migration database. An over-scoped principal is not accepted for
a run.

```bash
make tp-atlas-scope-check DB=ow_tp_billing_<timestamp> OUT=migration/billing/evidence/atlas-scope-check.json
```

Exit code 0 is PASS and anything else is FAIL. The script fails closed with
exit code 2 and makes no connection when `MONGODB_ATLAS_URI` is unset or
empty, when `--db` is missing, when a connection string is passed as an
argument, or when `--uri-env` names another variable. Its output is filtered
so a connection string never reaches the log, and the JSON evidence holds the
user name and roles only.

## Dedicated user

A human with project owner rights creates one database user per run whose only
role is `readWrite` on that run's database, then points `MONGODB_ATLAS_URI` at
it. With the Atlas CLI, after `atlas auth login` or with
`MONGODB_ATLAS_PUBLIC_KEY` and `MONGODB_ATLAS_PRIVATE_KEY` exported:

```bash
RUN=<timestamp>
atlas dbusers create \
  --projectId "$MONGODB_ATLAS_PROJECT_ID" \
  --username "ow_tp_billing_${RUN}" \
  --role "readWrite@ow_tp_billing_${RUN}" \
  --scope <cluster name> \
  --desc "OtterWorks billing migration run ${RUN}" \
  --password '<generate a new password>'
```

The same user from `mongosh`, connected as a user that holds
`userAdminAnyDatabase` on a self managed deployment (Atlas manages users
through the CLI or the UI only):

```javascript
db.getSiblingDB("admin").createUser({
  user: "ow_tp_billing_<timestamp>",
  pwd: passwordPrompt(),
  roles: [{ role: "readWrite", db: "ow_tp_billing_<timestamp>" }]
})
```

The user has no other built in role, no `atlasAdmin` and no
`readWriteAnyDatabase`. The secret then holds
`mongodb+srv://ow_tp_billing_<timestamp>:<password>@<cluster host>/ow_tp_billing_<timestamp>?retryWrites=true&w=majority`.
Rerun the scope check from a fresh shell. Expected: `principal.roles` is
exactly `[{"role": "readWrite", "db": "ow_tp_billing_<timestamp>"}]`, the
denied probe is `refused` with code 13, the allowed probe is `accepted`, and
the verdict is PASS.

To remove the user after the run:

```bash
atlas dbusers delete "ow_tp_billing_<timestamp>" --projectId "$MONGODB_ATLAS_PROJECT_ID" --force
```

## Reach of `readWrite`

`readWrite` covers what the data migration needs on the migration database:
`createCollection` (with a `$jsonSchema` validator at creation time),
`createIndex`, `insert`, `update`, `remove`, `find` and `dropCollection`. It
does not include `collMod`, `dropDatabase` or `enableProfiler`; those belong
to `dbAdmin`, so `make tp-mongodb-reset TARGET=atlas` drops each collection
instead of the database.
