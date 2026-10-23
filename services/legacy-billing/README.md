# Legacy Billing — database-centric before state

`legacy-billing` is a deliberately database-centric billing application. It
is the durable before-state for the stored-procedure extraction flow: the
running application has server-rendered pages and a small JSON API, while the
business behavior is implemented in PostgreSQL under the `billing` schema.

This component is part of the OtterWorks golden app as a durable before-state.
The extraction target and the modern client are separate components and are
not part of this service.

## Modules

| Module | Procedures/functions | Routes |
|---|---|---|
| Plans | `fn_list_plans`, `fn_entitlement`, `sp_change_plan` | `/plans`, `/plans/<tenant>/entitlement`, `/plans/<tenant>/change` |
| Rating | `fn_usage_rating`, `fn_usage_summary`, `sp_finalize_rating` | `/api/rating/preview`, `/api/rating/finalize` |
| Invoicing | `fn_invoice_preview`, `fn_invoice_lines`, `sp_issue_invoice` | `/api/invoices/<tenant>/preview`, `/api/invoices/<tenant>/issue`, `/api/invoices/<invoice>/lines` |
| Dunning | `fn_overdue_accounts`, `sp_schedule_dunning`, `sp_suspend_overdue` | `/api/dunning/overdue`, `/api/dunning/schedule`, `/api/dunning/suspend` |

The Flask layer intentionally binds request values, calls a database
entrypoint, and renders the returned values. It does not reproduce domain
decisions in Python.

## Why it is an extraction candidate

- The domain boundaries are already grouped into database procedure modules.
- The service has a narrow HTTP surface that maps to those entrypoints.
- PostgreSQL owns the state transitions and computed billing results.
- The database can be reset to a deterministic seed for repeatable recordings.

## Full verification loop

The extracted reference service is `services/billing-service/`, backed by a
separate Postgres database and `billing_svc` schema. The
declarative contract and human-approved ledger live under `procs/`. From the
repository root:

```bash
make procs-up NS=dev
make procs-rules-gate MODULE=plans
make procs-parity NS=dev
make procs-down NS=dev
```

The parity report compares the target's returned fields and target-side state
probes with immutable recordings. Modules not yet extracted remain skipped.
The legacy procedure files and recordings remain the source of truth for the
before-state.

## Run locally

From the repository root:

```bash
make procs-up NS=dev
curl http://localhost:8096/health
make procs-down NS=dev
```

The Compose profile is intentionally separate from the Helm/EKS path. It
models the legacy application running with its own PostgreSQL database.

### Connection settings

| Setting | Default | Managed PostgreSQL |
|---|---|---|
| `DB_HOST` | `localhost` | RDS endpoint |
| `DB_PORT` | `5432` | `5432` |
| `DB_NAME` | `billing_dev` | Tenant billing database |
| `DB_USER` | `billing` | `billing_app` |
| `DB_PASSWORD` | `billing` | Direct password only if not using a secret ARN |
| `DB_PASSWORD_SECRET_ARN` | Unset | Optional Secrets Manager ARN; requires `secretsmanager:GetSecretValue` and `AWS_REGION` or `AWS_DEFAULT_REGION` |
| `DB_PASSWORD_CACHE_SECONDS` | `300` | Secret refresh interval in seconds |
| `DB_SSLMODE` | `PGSSLMODE` or `prefer` | `verify-full` |
| `DB_SSLROOTCERT` | `PGSSLROOTCERT`, otherwise unset unless verification mode selects the baked bundle | `/etc/ssl/certs/rds-global-bundle.pem` |
| `DB_CONNECT_TIMEOUT` | `10` seconds | `10` seconds |

When `DB_PASSWORD_SECRET_ARN` is set, the application lazily reads its
`SecretString` from Secrets Manager. A JSON secret with a `password` key uses
that value; other strings are used as-is. The value is cached for
`DB_PASSWORD_CACHE_SECONDS` so password rotation is picked up without a restart.
`DB_SSLROOTCERT` and `DB_SSLMODE` take precedence over the corresponding libpq
variables `PGSSLROOTCERT` and `PGSSLMODE`. The image contains the RDS global CA
bundle at `/etc/ssl/certs/rds-global-bundle.pem`; it is selected automatically
only for `verify-ca` or `verify-full` when no root certificate is configured.

### Run locally with TLS

The TLS override creates a throwaway local CA and an isolated database volume:

```bash
make procs-up-tls NS=dev
make billing-tls-verify NS=tlscheck
make procs-down-tls NS=dev
```

## Database layout

- `db/schema.sql` — tables and constraints
- `db/procs/` — database entrypoints
- `db/seed.sql` — deterministic starting state
- `db/migrations/` — ordered SQL migrations; 0001–0005 preserve the source files verbatim
- `db/bootstrap/roles.sql` — one-time owner and runtime-role setup
- `db/migrate.sh` — checksum-tracked migration runner for the non-superuser owner role
- `db/verify-migrations.sh` — disposable PostgreSQL 16 migration, permission, and parity check

### Applying to managed PostgreSQL

Run the role bootstrap as the database admin, then set both role passwords
interactively with `\password`. Run the migration runner as `billing_owner`:

```bash
psql -X -v ON_ERROR_STOP=1 -v owner_role=billing_owner -v app_role=billing_app \
  -d billing_t -f services/legacy-billing/db/bootstrap/roles.sql
psql -X -d billing_t
# At the psql prompt:
# \password billing_owner
# \password billing_app
# \q

export PGSSLMODE=verify-full PGSSLROOTCERT="<rds-ca-bundle>"
PGHOST="<rds-endpoint>" PGDATABASE=billing_t PGUSER=billing_owner \
  BILLING_APP_ROLE=billing_app services/legacy-billing/db/migrate.sh
```

For managed connections, configure `DB_SSLMODE=verify-full` and
`DB_SSLROOTCERT=/etc/ssl/certs/rds-global-bundle.pem` (or provide the
corresponding `PGSSLMODE` and `PGSSLROOTCERT` libpq variables). The local TLS
override is in `docker-compose.procs.tls.yml`.
