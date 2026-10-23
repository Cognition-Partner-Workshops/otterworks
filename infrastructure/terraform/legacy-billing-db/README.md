# Legacy billing database

This stack creates a dedicated Amazon RDS for PostgreSQL 16 instance for `services/legacy-billing`, with encrypted storage and logs, private networking, TLS enforcement, backups, and a final snapshot on deletion. It is code only: it has never been planned against a real account or applied.

The shared `modules/database` stack is not reused because it pins PostgreSQL 15.7, bundles DynamoDB tables, and opens port 5432 to the whole VPC CIDR. This stack targets PostgreSQL 16 to match local `postgres:16`.

Validate locally with:

```bash
terraform init -backend=false
terraform validate
```

A real backend init passes the per-run state key:

```bash
terraform init -backend-config="key=otterworks/legacy-billing-db/<run_token>/terraform.tfstate"
```

The RDS-managed master secret is only for running `db/bootstrap/roles.sql`. The application and `db/migrate.sh` use the owner and app roles created by that bootstrap. Set `PGSSLMODE` or `DB_SSLMODE` to `verify-full` and configure the RDS global CA bundle; `rds.force_ssl` rejects non-TLS connections.

The client security group must be attached to the legacy-billing pods and migration job with a VPC CNI `SecurityGroupPolicy` listing both the client SG and the cluster SG. Pod security groups replace node security groups, so DNS and Secrets Manager egress still needs the cluster SG. This attachment is left to the deploy step.

To destroy the instance, first apply `deletion_protection=false`. RDS leaves the configured final snapshot.
