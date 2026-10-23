# Rehost module

This module provisions an artifact bucket and object, an application log group, an internet-facing ALB, security groups, a target group and attachment, HTTP (or HTTPS plus redirect) listeners, and one IMDSv2-required EC2 instance with an SSM/CloudWatch/artifact-read role. The instance bootstraps a generic systemd service from the uploaded artifact.

The portfolio disposition standard says: **“Rehost needs a reason the code cannot change cheaply.”** Set `disposition_evidence` to the assessment-report row pointer (for example, `portfolio/assessment-report.csv:3`), not the evidence list; it is stamped as an AWS tag value and must use the allowed tag characters and fit within 256 characters.

## Inputs

| Input | Required/default | Purpose |
|---|---|---|
| `service_name` | Required | Lowercase application identifier. |
| `run_token` | Required, at most 28 characters | Run-scoped names and tags. |
| `expires` | Required | RFC 3339 resource expiry. |
| `disposition_evidence` | Required | Assessment-report row pointer stamped as an AWS tag value, such as `portfolio/assessment-report.csv:3`; not the evidence list. |
| `vpc_id`, `subnet_ids` | Required | Existing VPC and public subnet IDs; no discovery occurs in the module. |
| `extra_tags` | `{}` | Additional tags; values must fit the AWS tag value character set and 256-character limit. Required disposition tags override collisions. |
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

Copy `example/` into a caller-owned root, provide the artifact path and required values, then initialize with the per-run state key:

```sh
terraform init -backend-config="key=otterworks/dispositions/rehost/<run_token>/terraform.tfstate"
terraform plan -var='artifact_path=/absolute/path/to/service.jar'
terraform apply -var='artifact_path=/absolute/path/to/service.jar'
terraform destroy -var='artifact_path=/absolute/path/to/service.jar'
```

Use the same key for `terraform destroy`. The module tags resources with `run_token`, `RunToken`, `Expires`, `ManagedBy=terraform`, `disposition=rehost`, `service`, and `disposition_evidence`; caller `extra_tags` are retained unless they conflict with a required tag. Evidence and extra tag values must contain 1–256 characters from letters, digits, spaces and `_ . : / = + - @`. CI plans only and never applies.
