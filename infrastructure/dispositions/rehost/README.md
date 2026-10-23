# Rehost module

This module provisions an artifact bucket and object, an application log group, an internet-facing ALB, security groups, a target group and attachment, HTTP (or HTTPS plus redirect) listeners, and one IMDSv2-required EC2 instance with an SSM/CloudWatch/artifact-read role. The instance bootstraps a generic systemd service from the uploaded artifact.

The portfolio disposition standard says: **“Rehost needs a reason the code cannot change cheaply.”** Supply the assessment row in `disposition_evidence`.

## Inputs

| Input | Required/default | Purpose |
|---|---|---|
| `service_name` | Required | Lowercase application identifier. |
| `run_token` | Required, at most 28 characters | Run-scoped names and tags. |
| `expires` | Required | RFC 3339 resource expiry. |
| `disposition_evidence` | Required | Assessment row, such as `portfolio/assessment-report.csv:2`. |
| `vpc_id`, `subnet_ids` | Required | Existing VPC and public subnet IDs; no discovery occurs in the module. |
| `extra_tags` | `{}` | Additional tags; required disposition tags override collisions. |
| `artifact_path` | Required | Local file path to upload; `filemd5` detects changes. |
| `artifact_name` | `null` | S3 object key; defaults to `basename(artifact_path)`. |
| `start_command` | Required | systemd `ExecStart`; artifact is in `/opt/<service_name>/<artifact_name>` and `ARTIFACT_PATH` is exported. |
| `instance_type`, `ami_id` | `t3.small`, `null` | Instance size and optional AMI; null selects the AL2023 SSM parameter. |
| `app_port`, `health_check_path` | `8080`, `/health` | ALB target port and health check path. |
| `packages`, `environment`, `bootstrap_script` | `[]`, `{}`, `""` | dnf packages, service environment, and optional root bootstrap executed before systemd starts. |
| `app_log_path`, `log_retention_days` | `null`, `7` | Shipped log path and retention; null path defaults under `/var/log/<service_name>`. |
| `root_volume_size` | `16` | Root gp3 volume size in GiB. |
| `alb_ingress_cidrs` | `["0.0.0.0/0"]` | CIDRs permitted to reach ALB listener ports. |
| `certificate_arn` | `null` | Optional ACM certificate; enables TLS 1.3/1.2 listener and HTTP redirect. |
| `public_hostname` | `null` | DNS name pointed at `alb_dns_name`; required with `certificate_arn` and must match the certificate. |

## Outputs

| Output | Description |
|---|---|
| `base_url` | HTTP ALB hostname, or the HTTPS `public_hostname` when a certificate is configured. |
| `instance_id` | EC2 instance ID. |
| `artifact_bucket` | Artifact bucket name. |
| `app_log_group` | CloudWatch log group name. |
| `target_group_arn` | ALB target group ARN. |
| `alb_dns_name` | ALB DNS name. |
| `expires` | Expiry timestamp supplied to the module. |

## Apply and cleanup

Copy `example/` into a caller-owned root and set `source` in `main.tf` to the module path relative to that new root (for example, `../../dispositions/rehost` for `infrastructure/terraform/<service>-rehost/`). Provide the artifact path and required values, then initialize with the per-run state key:

```sh
terraform init -backend-config="key=otterworks/dispositions/rehost/<run_token>/terraform.tfstate"
terraform plan -out tfplan -var='artifact_path=/absolute/path/to/service.jar'
terraform show -json tfplan > plan.json
python ../../dispositions/scripts/check-plan-tags.py plan.json "<run_token>" "<expires>"
terraform apply -var='artifact_path=/absolute/path/to/service.jar'
terraform destroy -var='artifact_path=/absolute/path/to/service.jar'
```

Replace the checker arguments with the `run_token` and `expires` values used in the caller root. Use the same key for `terraform destroy`. The module tags resources with `run_token`, `RunToken`, `Expires`, `ManagedBy=terraform`, `disposition=rehost`, `service`, and `disposition_evidence`; caller `extra_tags` are retained unless they conflict with a required tag. CI plans only and never applies. On Linux and macOS, use `python3` instead of `python`.

### Windows (PowerShell 5.1)

The Terraform commands above also work in PowerShell. Set environment variables with `$env:AWS_DEFAULT_REGION = "us-east-1"` and `$env:AWS_ACCESS_KEY_ID`, `$env:AWS_SECRET_ACCESS_KEY`, and `$env:AWS_SESSION_TOKEN` as needed instead of `export`. `cloudworker/assume.sh` is bash-only; run it in Git Bash/WSL or use `aws sts assume-role` and set the `$env:` variables. Use `python`; a standard Windows Python install has no `python3` command. PowerShell 5.1 `>` writes UTF-16, which the checker accepts, but other tools may not; the portable form is `terraform show -json tfplan | Set-Content -Encoding ascii plan.json`. Windows artifact paths work as `-var='artifact_path=C:\path\to\app.jar'`. The module strips CR from `user_data`, so a CRLF checkout is safe.
