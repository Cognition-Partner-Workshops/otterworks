# Rearchitect module

This module provisions Aurora Serverless v2 with the RDS Data API and a Secrets Manager credential, one placeholder Lambda per application context, aliases and CodeDeploy canaries, an HTTP API with two routes per context plus `$default`, 5xx/Lambda/composite alarms, and an EventBridge page to the automation webhook with a DLQ. Optional event subscriptions each get an encrypted DynamoDB table, rule, target, and consumer Lambda. Optional probe steps add a stopped Synthetics canary and expiring artifact bucket. An optional SQL file is applied with the RDS Data API during apply.

The portfolio disposition standard says: **“Rearchitect needs clean seams and a parity corpus that can prove each port.”** Supply the assessment row in `disposition_evidence`.

## Inputs

| Input | Required/default | Purpose |
|---|---|---|
| `service_name` | Required | Application identifier and page tenant. |
| `run_token` | Required, at most 15 characters | Run-scoped names and tags; limited by the 21-character Synthetics canary name. |
| `expires` | Required | RFC 3339 expiry. |
| `disposition_evidence` | Required | Assessment row, e.g. `portfolio/assessment-report.csv:2`. |
| `vpc_id`, `subnet_ids` | Required | Existing VPC and private subnet IDs; no module discovery. |
| `extra_tags` | `{}` | Additional tags; required disposition tags override collisions. |
| `contexts` | Required | Context map with `schema`, `route_prefix`, optional `publishes_events` and `environment`; context environments must not set module-owned keys (`CONTEXT`, `DB_SCHEMA`, `DB_NAME`, `CLUSTER_ARN`, `SECRET_ARN`, `RUN_TOKEN`, `EVENT_BUS_NAME`). |
| `default_route_context` | `null` | Defaults to the first sorted context key. |
| `database_name`, `master_username` | `app`, `app_admin` | Aurora database and master username. |
| `schema_sql_path` | `null` | Optional SQL file sent through the Data API during apply. |
| Aurora capacity/version | `16.13`, `0`–`1` ACU, `600` seconds | Small, auto-pausing defaults. |
| Lambda/deployment/alarm settings | `512` MB, 3-day logs, CodeDeploy canary, 20% 5xx threshold | Context runtime and alarm settings. |
| `devin_webhook_url`, `devin_webhook_secret` | `""`, `""` | Empty values disable the page rule. The secret is sensitive. |
| `builder_role_name` | `""` | Attaches the run-scoped policy only when non-empty. |
| `account_id` | `null` | Optional account ID; null uses `aws_caller_identity`. |
| `event_subscriptions` | `{}` | Optional map of event source and detail types. |
| `probe_steps` | `[]` | Optional list of `{ name, path }` HTTP GET steps. |

## Outputs

The module exports `api_url`, `api_id`, `lambda_names`, `aurora_cluster_arn`, `aurora_capacity`, `db_secret_arn`, `db_name`, `builder_policy_arn`, `event_bus_name`, `subscription_tables`, `consumer_functions`, `live_aliases`, `codedeploy_app`, `deployment_groups`, `probe_canary`, `probe_artifacts_bucket`, the three alarm names, page rule name/state, API destination name, DLQ URL, and `expires`.

## Apply and cleanup

Copy `example/` into a caller-owned root and set the required context, VPC/subnet, evidence, and expiry values. The example uses name-based lookup for the existing `otterworks-dev` VPC and private subnets. Initialize with the run-scoped backend key:

```sh
terraform init -backend-config="key=otterworks/dispositions/rearchitect/<run_token>/terraform.tfstate"
terraform plan
terraform apply
terraform destroy
```

Use the same backend key for destroy. Resources carry `run_token`, `RunToken`, `Expires`, `ManagedBy=terraform`, `disposition=rearchitect`, `service`, and `disposition_evidence`; additional caller tags are accepted. CI only plans and never applies.
