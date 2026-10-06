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

Phase 3 adds the S3 export, Glue, Athena and EventBridge resources to this root.

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
# teardown: drops the database and role, then removes the function, secret and security group
terraform destroy -var run_token=$TOKEN -var expires=$EXPIRES
source <(../../../cloudworker/assume.sh observer devin-<session id>)
```
