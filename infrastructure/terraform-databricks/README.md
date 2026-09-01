# CUSTBILL Databricks wave-0 scaffold

This directory owns the shared wave-0 Databricks objects for the CUSTBILL
workflow. Every object is scoped to the `ow_tp` catalog or carries the
`ow_tp` prefix. The configuration uses the existing serverless SQL warehouse
`565cd2fd713738c4`; it does not create a cluster or warehouse.

## Authentication

Export the demo credentials into the provider names before running Terraform:

```bash
export DATABRICKS_HOST="$DATABRICKS_DEMO_HOST"
export DATABRICKS_TOKEN="$DATABRICKS_DEMO_TOKEN"
export TF_VAR_sftp_password='...'
```

Do not put credential values in Terraform files, state committed to git, or
documentation. The fixture host and user are the values documented by
`etl/legacy-extra/docker-compose.sftp.yml`; supply its password through
`TF_VAR_sftp_password` rather than copying it here.

## Existing shared objects

The catalog, schemas, managed landing volume, and secret scope can already be
present in the shared demo workspace. If they exist, import them into this
local state before planning:

```bash
terraform init
./import.sh
terraform plan
```

`import.sh` attempts imports for `ow_tp`, `ow_tp.bronze`, `ow_tp.silver`,
`ow_tp.gold`, `ow_tp.bronze.landing`, and the `ow_tp` secret scope. An import
that returns not-found is ignored so a new object can still be created by a
later reviewed apply. The four managed tables, notebooks, and job are also
declared idempotently; import any pre-existing instance of those resources
with the provider's documented import ID before applying if a workspace
already contains one.

## Resources

Terraform declares the managed catalog, three schemas, `ow_tp.bronze.landing`,
the `ow_tp` secret scope and three SFTP keys, four managed Delta tables, three
placeholder serverless notebook tasks, and the paused `ow_tp_custbill` job.
The job has the dependency chain `ingest -> parse -> finance`, one active run
at a time, the legacy-compatible fifteen-minute schedule, and failure-only
notifications.

The exact table columns and dictionary comments follow
`docs/tech-partnerships/CUSTBILL_analysis.md` §4, with the requested wave-0
column names. The quarantine `reason` comment uses
`short_record|nonnumeric_amount|invalid_calendar_date|trailer_count_mismatch`.
`databricks_sql_table` is used directly; no `databricks_sql_query` or
`null_resource` fallback is needed.

## Plan-only workflow

```bash
terraform fmt
terraform init
terraform validate
terraform plan
```

Do not run `terraform apply` from this scaffold without the migration owner's
review.
