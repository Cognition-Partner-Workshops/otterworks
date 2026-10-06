# billing-data

Terraform root for moving billing off the legacy database. One run token per stack, for example `lp-20261006-bd`,
with its state at `s3://otterworks-terraform-state/otterworks/billing-data/<token>/terraform.tfstate`. Every resource
gets the `run_token` and `Expires` tags through `default_tags`.

So far the root creates:

- the database `lp_<yyyymmdd>_<xx>` on the existing shared instance `otterworks-postgres-dev`. The instance itself is
  only read here, never modified.
- the login role `lp_<yyyymmdd>_<xx>_billing`. It has `CONNECT, CREATE, TEMPORARY` on that database and `USAGE, CREATE`
  on its `public` schema. It has no `SUPERUSER`, `CREATEDB` or `CREATEROLE` and is not a member of any role.
  `PUBLIC` loses its access to the new database.
- the secret `otterworks-<token>/billing-db` (JSON: engine, host, port, dbname, username, password) for that role.

- the `lp-<token>-billing-sql` function, an in-VPC SQL runner that `scripts/billing-to-rds.py` invokes out-of-band
  (`aws lambda invoke`) to load the billing/billing_svc schemas and data and to run the RDS-side row counts. It sits in
  the same subnets and shares the db-init security group; credentials travel in the invocation payload.

- the `lp-<token>-billing-service` function: `services/billing-service` itself, unchanged, run through Mangum in
  the same subnets with the db-init security group. It has no function URL, API Gateway or ingress rule;
  `scripts/billing-service-proxy.py` serves it on `127.0.0.1` by turning each HTTP request into a `lambda:Invoke`
  call and passes the run's login credentials (read once from the secret) in the payload. `/internal/reset` is
  refused unless the proxy is started with `--allow-internal-reset`.

- the nightly usage export (`usage_export.tf`, decision d-export-network = relay): the bucket
  `<token>-billing-usage-<account id>` (SSE-S3, public access blocked, TLS only, `force_destroy`), the function
  `<token>-billing-usage-export` **outside** the VPC with the role `otterworks-<token>-usage-export`, and the
  EventBridge Scheduler schedule `<token>-billing/<token>-billing-usage-export` (`cron(15 2 * * ? *)` UTC, role
  `otterworks-<token>-usage-scheduler`). Schedules take no tags, so the schedule group `<token>-billing` carries them.
  The function reads the run's secret, invokes the in-VPC sql-runner with the credential in the payload (never
  logged), and writes `usage/period=<yyyy-mm>/part-00000.csv.gz`, overwriting the partition on each run.

Phase 3 adds the Glue table and Athena workgroup to this root.

## Usage export

Headerless gzip CSV, one object per month, columns in this order:

| column | type | note |
| --- | --- | --- |
| `event_id` | uuid as string | `billing.usage_events.id` |
| `tenant_id` | uuid as string | |
| `kind` | string | `api`, `storage`, `compute` |
| `units` | int | |
| `occurred_at` | timestamp, UTC | `yyyy-mm-dd hh:mm:ss.ffffff` |
| `usage_date` | date, UTC | `yyyy-mm-dd`, the `occurred_at::date` that `fn_usage_summary` groups on (session time zone UTC) |

A month belongs to `period=<yyyy-mm>` by its UTC `occurred_at`. A month without usage still gets its partition:
`part-00000.csv.gz` holding zero rows (a 20-byte empty gzip), so a query over it returns no rows rather than
failing. Each run also writes `manifests/usage/period=<yyyy-mm>.json` (rows, units, columns), outside the
`usage/` table location.

The schedule sends `{}`: every month present in `billing.usage_events` plus the previous calendar month (UTC), even
when it is empty. A manual run can name the months:

```bash
source <(cloudworker/assume.sh engineer devin-<session id>)
aws lambda invoke --function-name $TOKEN-billing-usage-export --cli-binary-format raw-in-base64-out \
  --payload '{"periods": ["2026-02", "2026-09"]}' /dev/stdout
```

## Reaching a private instance

`otterworks-postgres-dev` is not publicly accessible. Its security group allows 5432 from the VPC CIDR only, and the
private subnets have no NAT gateway and no VPC endpoints. So neither `psql` nor the Postgres provider can reach it from
outside the VPC. Instead, the `lp-<token>-billing-db-init` function runs in the instance's own private subnets. Its
security group has no ingress and allows egress only to the VPC CIDR on 5432. Terraform calls it through
`aws_lambda_invocation` with `lifecycle_scope = "CRUD"`:

- create and update run the DDL and return the `\l` row, the role, and a TLS login as the role (output `db_evidence`).
- destroy runs `DROP DATABASE ... WITH (FORCE)` and `DROP ROLE` before the function is removed.

The master credential is read from `otterworks/dev/rds/master` and passed in the invocation payload, so the function
needs no Secrets Manager endpoint. The function never logs credentials.

## billing-service on the run database and parity

The harness resets the target before grading, so parity runs against the run database itself and the move
script reloads it afterwards (decision d-parity-reset):

```bash
source <(cloudworker/assume.sh engineer devin-<session id>)
uv run scripts/billing-service-proxy.py --token $TOKEN --port 18097 --allow-internal-reset &
make procs-parity NS=dev MODULE=rating BILLING_SVC_URL=http://127.0.0.1:18097
kill %1
uv run scripts/billing-to-rds.py --ns dev --token $TOKEN   # reload, then the legacy vs RDS count table
```

## Apply and destroy

Use the engineer role for apply and destroy, then switch back to the observer role (`.agents/skills/aws-engineer/SKILL.md`).

```bash
cd infrastructure/terraform/billing-data
TOKEN=lp-20261006-bd EXPIRES=2026-10-10T00:00:00Z
source <(../../../cloudworker/assume.sh engineer devin-<session id>)
./build-lambda.sh
terraform init -backend-config="key=otterworks/billing-data/${TOKEN}/terraform.tfstate"
terraform apply -var run_token=$TOKEN -var expires=$EXPIRES
terraform output db_evidence
# teardown: drops the database and role, then removes the functions, secret, security group, bucket and schedule
terraform destroy -var run_token=$TOKEN -var expires=$EXPIRES
source <(../../../cloudworker/assume.sh observer devin-<session id>)
```
