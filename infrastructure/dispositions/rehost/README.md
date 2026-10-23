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

Copy `example/` into a caller-owned root and set `source` in `main.tf` to the module path relative to that new root (for example, `../../dispositions/rehost` for `infrastructure/terraform/<service>-rehost/`). The example hard-codes `service_name`, `run_token`, `expires`, `disposition_evidence` and `start_command` in `main.tf`; change them there, because only `artifact_path`, `region`, `vpc_name` and `public_subnet_name_prefix` are variables. Provide the artifact path, then initialize with the per-run state key:

```sh
terraform init -backend-config="key=otterworks/dispositions/rehost/<run_token>/terraform.tfstate"
terraform plan -out tfplan -var='artifact_path=/absolute/path/to/service.jar'
terraform show -json tfplan > plan.json
python ../../dispositions/scripts/check-plan-tags.py plan.json "<run_token>" "<expires>"
terraform apply -var='artifact_path=/absolute/path/to/service.jar'
terraform destroy -var='artifact_path=/absolute/path/to/service.jar'
```

Replace the checker arguments with the `run_token` and `expires` values used in the caller root. Use the same key for `terraform destroy`. The module tags resources with `run_token`, `RunToken`, `Expires`, `ManagedBy=terraform`, `disposition=rehost`, `service`, and `disposition_evidence`; caller `extra_tags` are retained unless they conflict with a required tag. Evidence and extra tag values must contain 1–256 characters from letters, digits, spaces and `_ . : / = + - @`. CI plans only and never applies. On Linux and macOS, use `python3` instead of `python`.

### Credentials the plan needs

`init` and `plan` read AWS before anything is created: the state object under `s3://otterworks-terraform-state/otterworks/dispositions/rehost/<run_token>/`, `ec2:DescribeVpcs` and `ec2:DescribeSubnets` for the VPC and subnet lookups in `example/main.tf`, and `ssm:GetParameter` on `/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64` when `ami_id` is null. Run-scoped `appassess-*` role sessions have none of these, so `init` fails with an S3 `403 Forbidden` and `plan` with `UnauthorizedOperation` / `AccessDeniedException`. Ask for those permissions before a real plan.

For a plan-only rehearsal without them, in your copy only: delete the `backend "s3"` block from `versions.tf` (with Terraform 1.9.8 a `backend_override.tf` containing `backend "local" {}` did not replace it; `init` still prompted for `key`), delete `.terraform` if an earlier `init` ran, replace the two data sources with literal `vpc_id` and `subnet_ids`, and set `ami_id`. That plan checks the resource graph and tags only; never apply it.

### Windows (PowerShell 5.1)

Terraform is not preinstalled on Windows. Install the version CI uses and check it against HashiCorp's checksums:

```powershell
$v = "1.9.8"; $d = "$env:USERPROFILE\tools\terraform"
New-Item -ItemType Directory -Force $d | Out-Null
$ProgressPreference = "SilentlyContinue"
Invoke-WebRequest "https://releases.hashicorp.com/terraform/$v/terraform_${v}_windows_amd64.zip" -OutFile "$d\tf.zip" -UseBasicParsing
$sums = (Invoke-WebRequest "https://releases.hashicorp.com/terraform/$v/terraform_${v}_SHA256SUMS" -UseBasicParsing).Content
if ($sums -notmatch "$((Get-FileHash "$d\tf.zip").Hash.ToLower())  terraform_${v}_windows_amd64.zip") { throw "checksum mismatch" }
Expand-Archive "$d\tf.zip" $d -Force
$env:Path = "$d;$env:Path"   # add $d to the user PATH to keep it
terraform version
```

The Terraform commands above also work in PowerShell. Set environment variables with `$env:AWS_DEFAULT_REGION = "us-east-1"` and `$env:AWS_ACCESS_KEY_ID`, `$env:AWS_SECRET_ACCESS_KEY`, and `$env:AWS_SESSION_TOKEN` as needed instead of `export`. `cloudworker/assume.sh` is bash-only; run it in Git Bash/WSL or use `aws sts assume-role` and set the `$env:` variables. Use `python`; a standard Windows Python install has no `python3` command. PowerShell 5.1 `>` writes UTF-16, which the checker accepts, but other tools may not. Piping through `Set-Content` re-encodes Terraform's UTF-8 through the console code page, so write the file byte-for-byte instead: `cmd /c "terraform show -json tfplan > plan.json"`. Windows artifact paths work as `-var='artifact_path=C:\path\to\app.jar'`. The module strips CR from `user_data`, so a CRLF checkout is safe. Windows PowerShell 5.1 reads UTF-8 files without a BOM as ANSI, so read this README with `Get-Content -Encoding UTF8`.
