# Replatform module

This Terraform module moves one containerized application onto managed services on the shared EKS cluster. It provisions a managed target for each stateful dependency the caller declares, an IRSA role for the workload, and installs the bundled Helm chart (`chart/`) with `helm_release`, wiring the connection settings into the release.

The portfolio disposition standard says: **"Replatform needs a managed target for each stateful dependency and a named upgrade path for anything past end of life."** Declare each dependency (`postgres`, `redis`, `buckets`, `queues`), name each end-of-life upgrade in `upgrade_paths`, and supply the assessment row in `disposition_evidence`.

| Dependency | Input (default) | Managed target | Small default when set |
|---|---|---|---|
| Relational store | `postgres` (`null`) | RDS PostgreSQL, Secrets Manager credential | `db.t4g.micro`, PostgreSQL 16, 20 GiB gp3 (autoscale to 50), 1-day backups, single AZ |
| Cache / sessions | `redis` (`null`) | ElastiCache Redis, TLS + auth token | `cache.t4g.micro`, Redis 7.1, one node |
| Files | `buckets` (`{}`) | S3, private, SSE, owner-enforced | versioning off, `force_destroy` on |
| Messages | `queues` (`{}`) | SQS with dead-letter queue, SSE | 30 s visibility, 4-day retention, 5 receives |

Nothing is created for a dependency that is not declared.

## Inputs

| Input | Required/default | Purpose |
|---|---|---|
| `service_name` | Required | Lowercase application identifier; names the release, objects and IRSA role. |
| `run_token` | Required, at most 28 characters | Run-scoped names and tags (`<prefix>-YYYYMMDD-xx`). |
| `expires` | Required | RFC 3339 expiry (`Expires` tag, `otterworks.io/expires` annotation). |
| `disposition_evidence` | Required | Assessment row, such as `portfolio/assessment-report.csv:2`. |
| `namespace` | Required | Tenant namespace `otterworks-<ID>`; `otterworks-main` is rejected. |
| `vpc_id`, `subnet_ids` | `null`, `[]` | Cluster VPC and at least two private subnets; required with `postgres` or `redis`. |
| `client_security_group_ids`, `client_cidr_blocks` | `[]`, `[]` | Who may reach the database and cache (normally the EKS cluster security group); one is required with `postgres` or `redis`. |
| `oidc_provider_arn` | `null` | EKS OIDC provider; when set, an IRSA role scoped to `system:serviceaccount:<namespace>:<service account>` is created with access to the declared buckets, queues and DB secret. |
| `iam_policy_statements` | `[]` | Extra statements for the IRSA role. |
| `upgrade_paths` | `{}` | Component to upgrade path, stamped on the pod as `otterworks.io/upgrade-paths`. |
| `deploy_release` | `true` | `false` provisions only the managed services and role. |
| `image_repository`, `image_tag` | Required with `deploy_release` | Container image. |
| `container_port`, `health_check_path`, `replicas` | `8080`, `/health`, `1` | Workload shape. |
| `environment` | `{}` | Non-secret settings for the ConfigMap. |
| `ingress_host` | `null` | Host on the shared ingress-nginx (`className: nginx`); `null` keeps the service internal. |
| `chart_values` | `[]` | Extra YAML documents for chart settings the module does not expose. |
| `service_account_name`, `helm_timeout_seconds`, `extra_tags` | `null`, `300`, `{}` | Overrides. |

## What the workload receives

ConfigMap: `AWS_REGION`; with `postgres`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_SSLMODE=require`, `DB_SECRET_ARN`; with `redis`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_TLS=true`; per bucket `S3_BUCKET_<KEY>`; per queue `SQS_QUEUE_URL_<KEY>`. Secret: `DB_PASSWORD`, `REDIS_AUTH_TOKEN`. Map them to the application's own names with `environment` or `chart_values` if they differ.

## Tags and guardrails

Every AWS resource that accepts tags gets `run_token`, `RunToken`, `Expires`, `ManagedBy=terraform`, `disposition=replatform`, `service` and `disposition_evidence`; caller `extra_tags` never override them. Every Kubernetes object and the pod template carry the `otterworks.io/run-token` label and the `otterworks.io/expires` and `otterworks.io/disposition-evidence` annotations. The chart refuses any `service.type` other than `ClusterIP` (AGENTS.md: the shared ingress-nginx is the only LoadBalancer), and its NetworkPolicy admits only the release namespace, `ingress-nginx` and `monitoring`.

## Apply and cleanup

Copy `example/` into a caller-owned root, set the service's values, then:

```sh
terraform init -backend-config="key=otterworks/dispositions/replatform/<run_token>/terraform.tfstate"
terraform plan  -var namespace=otterworks-<ID> -var image_repository=<repo> -var image_tag=<tag>
terraform apply -var namespace=otterworks-<ID> -var image_repository=<repo> -var image_tag=<tag>
terraform destroy -var namespace=otterworks-<ID> -var image_repository=<repo> -var image_tag=<tag>
```

## CI

`.github/workflows/disposition-replatform.yml` runs on pull requests only: `terraform fmt`/`validate` for the module, `example/` and `ci/`, an offline plan of `ci/` (mock credentials, fake IDs, every dependency enabled) checked by `../scripts/check-plan-tags.py`, then `helm lint --strict`, `helm template`, `chart/ci/check-rendered.py` and negative render checks on the chart. It never applies or installs anything.

Render the chart alone:

```sh
helm lint infrastructure/dispositions/replatform/chart --strict \
  -f infrastructure/dispositions/replatform/chart/ci/values-ci.yaml
helm template sample infrastructure/dispositions/replatform/chart \
  -f infrastructure/dispositions/replatform/chart/ci/values-ci.yaml
```
