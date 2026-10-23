# Stored-procedure recording loop

The `procs/` directory contains the declarative scenarios and immutable
recordings for the legacy billing application. The recordings are made against
the running PostgreSQL stack, not against a Python reimplementation.

## Loop

```bash
make procs-up NS=dev
make procs-list
make procs-record NS=dev
make procs-rules-gate MODULE=plans
make procs-parity NS=dev
cd frontend/client-app && npm run dev
make procs-down NS=dev
```

The Makefile derives the Postgres and HTTP host ports from `NS`, so separate
namespaces can run concurrently. Use `OUTPUT_DIR` when recording isolated
fixtures for a namespace-specific verification run.

The client Vite server proxies `/billing-api/*` to the extracted service. With
the default `NS=dev` stack, run the client command above and open
`http://localhost:3000/billing/plans`; no billing URL environment variable is
required. Vite dev enables the billing routes by default. A preview build
requires the explicit fixture flag:

```bash
VITE_ENABLE_BILLING_FIXTURE=true npm run build
npm run start -- --host 127.0.0.1 --port 4173
```

The `/billing-api` proxy is used by the dev server and by this explicitly
flagged preview. Builds without the flag leave the routes unregistered, as do
production builds. These screens are part of this local parity fixture, not
the deployed application. For another namespace, set `BILLING_SERVICE_URL` to
that namespace's derived target port when starting Vite.

Each scenario resets the `billing` schema to the checked-in schema, procedure
definitions, and seed. The recorder invokes the declared entrypoint, captures
the selected result fields, runs the named state probes, and writes one JSON
transcript under `procs/transcripts/<module>/`.

Transcripts are immutable. Re-recording requires `--allow-rerecord` and a
changed procedure source hash. If only the harness changed, use the explicit
audited escape `--allow-rerecord --rerecord-reason harness-change`; if the
scenario/probe design changed, use
`--allow-rerecord --rerecord-reason scenario-redesign`. Each resulting
transcript records that reason. The namespace affects only the running
database; it is not written into transcript content.

Recording an existing checkout is intentionally refused unless the procedure
source changed. Through Make, the normal command is:

```bash
make procs-record NS=dev
```

For a procedure-source change, explicitly authorize the refresh:

```bash
make procs-record NS=dev ALLOW_RERECORD=1
```

For a harness-only normalization or recorder change, use the auditable reason:

```bash
make procs-record NS=dev ALLOW_RERECORD=1 RERECORD_REASON=harness-change
```

For a scenario/probe redesign with unchanged procedures, use:

```bash
make procs-record NS=dev ALLOW_RERECORD=1 RERECORD_REASON=scenario-redesign
```

Each non-procedure reason is valid only for the named change; neither is a
substitute for recording changed procedures.

## Add a scenario

1. Add a YAML file under `procs/scenarios/<module>/`.
2. Set `id`, `module`, `description`, `entrypoint`, and `kind`.
3. Declare typed `inputs`.
4. Select returned `fields`, or use `capture_query` for a side-effecting
   procedure.
5. Add named `probes` with stable SQL queries.
6. Add stable `rules` identifiers for the later rules gate.
7. Run `make procs-record NS=<namespace>` against a fresh namespace and inspect
   the resulting transcript.

Scenario SQL should observe the legacy state. It should not duplicate
procedure logic in Python.

## Extraction verification

`routes.yaml` maps extracted legacy entrypoints to target HTTP endpoints. The
replay harness resets the target before each scenario, replays only modules
marked `extracted`, and records semantic field/probe comparisons in
`procs/reports/parity.md` and `parity.json`. Pending modules are reported as
`SKIP`, never as a pass. Replay also checks that the transcript source hash
still matches the checked-in procedure files.

The rules gate is a separate human-approval check:

```bash
make procs-rules-gate MODULE=plans
```

It validates the ledger decision, scenario coverage, source ranges, and
target-test markers before parity is allowed to grade an extracted module.

## Migrated-schema parity (`g-procs-parity`)

`make procs-parity` grades the extracted service and skips pending modules.
`make procs-schema-parity` instead proves the legacy procedures themselves
still reproduce every recording after the database is built by the migration
runner rather than `schema.sql`:

```bash
make procs-up NS=dev                       # original schema.sql stack (baseline)
make procs-schema-parity-original NS=dev
make procs-up-migrated NS=dev              # postgres:16 + roles.sql + migrate.sh, TLS
make procs-schema-parity NS=dev BASELINE=procs/reports/schema-parity-original.json
make procs-down-migrated NS=dev
make procs-down NS=dev
```

`docker-compose.procs.migrated.yml` starts an empty `postgres:16` with TLS,
creates a non-superuser `platform_admin` that runs
`services/legacy-billing/db/bootstrap/roles.sql`, and lets the billing roles
connect only over `hostssl`. `legacy-billing-migrate` runs `db/migrate.sh` as
`billing_owner` and loads `seed.sql`; `legacy-billing` connects as
`billing_app` with `DB_SSLMODE=verify-full` against the local throwaway CA.

`procs/harness/migrated/parity.sh` checks the app's own `db_connect()` session
(billing_app, not superuser, TLS, PostgreSQL 16), then
`procs/harness/schema_parity.py` replays every scenario of every module as
`billing_app` over verify-full TLS, rebuilding the schema with `migrate.sh`
before each scenario. Business fields, state probes, entrypoint and inputs must
equal the transcript. A module or scenario without a recording is an error,
not a skip, and the run refuses to grade when the migrations no longer match
the procedure sources the transcripts were recorded from. Transcripts are only
read. Reports go to `procs/reports/schema-parity-<label>.{md,json}`.

Tenant 1's three seeded rating periods (2025-11, 2025-12, 2026-01) make
`sp_finalize_rating` raise on every platform (see
`services/legacy-billing/db/MANAGED_POSTGRES.md`). The run records those
outcomes separately, does not grade them, and with `BASELINE` requires them to
be identical to the original `schema.sql` database.
