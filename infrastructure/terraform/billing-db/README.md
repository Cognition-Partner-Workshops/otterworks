# billing-db

Terraform root for the managed PostgreSQL database of `services/legacy-billing`
(plan step s4.2). Background and the reasoning behind each setting are in
`services/legacy-billing/db/MANAGED_POSTGRES.md`.

Code only for now: nothing here has been applied.

## What it creates

| Resource | Notes |
| --- | --- |
| `aws_db_instance.billing` | RDS PostgreSQL 16 (`engine_version`, default `16.15`, minor upgrades off), gp3, `storage_encrypted`, `deletion_protection`, 7-day backups, final snapshot, private only, `manage_master_user_password` (Secrets Manager) |
| `aws_db_parameter_group.billing` | `postgres16` family: `rds.force_ssl=1`, `ssl_min_protocol_version=TLSv1.2`, `timezone=UTC`, `datestyle=ISO, MDY` |
| `aws_db_subnet_group.billing` | private subnets of the `otterworks-dev` VPC (`tag:Name=otterworks-private-*`) |
| `aws_security_group.billing` + `aws_vpc_security_group_ingress_rule.postgres` | TCP 5432 from the VPC CIDR only, no other ingress |
| `aws_cloudwatch_log_group.billing` | `postgresql` and `upgrade` log exports |

Every resource carries `run_token`, `RunToken` and `Expires` through the provider
`default_tags`. Outputs: `endpoint`, `address`, `port`, `database_name`,
`master_user_secret_arn`, `engine_version`, `parameter_group_name`, `ca_cert_identifier`.

## Database bootstrap

RDS creates no application database here (`db_name` is unset) so that the billing
database is created explicitly with the Compose locale and session settings:

```bash
psql "host=<address> dbname=postgres user=billing_admin sslmode=verify-full sslrootcert=global-bundle.pem" \
  -v ON_ERROR_STOP=1 -f bootstrap/create-database.sql
```

Schema, procedures, roles and grants are the next step (s4.3).

## CI

`.github/workflows/billing-db-terraform.yml` runs on pull requests only: `fmt`,
`validate`, then an offline `plan` with mock credentials, `offline_plan=true`
(`skip_credentials_validation`, `skip_requesting_account_id`,
`skip_metadata_api_check`) and literal network ids from `ci/offline.tfvars`.
`ci/check-plan.py` then checks the plan JSON for the tags on every resource, the
engine and version, encryption, deletion protection, the managed password, backups,
`force_ssl`, `timezone`, `datestyle` and the 5432 ingress CIDRs.

Run the same locally:

```bash
printf 'terraform {\n  backend "local" {}\n}\n' > ci_override.tf
AWS_ACCESS_KEY_ID=mock AWS_SECRET_ACCESS_KEY=mock terraform init -reconfigure
AWS_ACCESS_KEY_ID=mock AWS_SECRET_ACCESS_KEY=mock terraform plan -lock=false -out=tfplan \
  -var-file=ci/offline.tfvars -var=run_token=ci-20261023-gh -var=expires=2026-10-30T00:00:00Z
terraform show -json tfplan > plan.json
python3 ci/check-plan.py plan.json --run-token ci-20261023-gh --expires 2026-10-30T00:00:00Z \
  --engine-version 16.15 --allowed-cidr 10.0.0.0/16
```
