# Dev Cost Correction Evidence & Savings Worksheet

Markdown twin of [`savings-worksheet.csv`](./savings-worksheet.csv) and [`comparison-results.json`](./comparison-results.json).

## Governance & Cost Basis

| Field | Value |
| --- | --- |
| Anomaly ID | `aws.cost-anomaly:9f6305ea` |
| Run tag / Environment | `FINOPS_20261128` / `dev` |
| Attributing commit | `a84f1b648` on `demo-finops` |
| Workload owner | `platform/team: otterworks` (`document-service`, `tenant-compute`) |
| Cost basis | Unblended (no amortization/credits in export); synthetic fixture rates: `$0.001/GB-day` (`CloudWatch-TimedStorage`), `$0.0025/GiB-day` (`EBS-VolumeUsage.gp3`) |
| Minimum audit log retention | `90` days (hardcoded in `infrastructure/terraform/modules/monitoring/main.tf`) |
| Audit log exclusion | `/otterworks/dev/audit-service` (excluded from all retention reductions; untouched) |
| Shared fleet boundary | `demo-platform/k8s/karpenter/nodepool.yaml` (`EC2NodeClass/default`) is shared workshop fleet — untouched |
| Matched workload SHA-256 | `810278341b159d70fc061efcad044a45017d270079d119587be98f2aac348d17` (100 requests, verified identical across all runs) |

## Before & After Settings

| Setting | Source File | Before (`demo-finops`) | After (This PR) | Status |
| --- | --- | --- | --- | --- |
| Dev app log retention floor | `infrastructure/terraform/main.tf` | `14` days (`max(var.log_retention_days, 14)`) | `7` days (`max(var.log_retention_days, 7)`) | **Changed (dev-only)** |
| Audit log retention | `infrastructure/terraform/modules/monitoring/main.tf` | `90` days (`/otterworks/dev/audit-service`) | `90` days | **Untouched (policy)** |
| Root EBS volume (`gp3`) | `demo-platform/k8s/karpenter/nodepool.yaml` | `50Gi` | `50Gi` | **Untouched (shared fleet)** |

## Dev Workload Comparison (`demos/finops/workload/compare.py`)

All four runs executed the exact same 100 synthetic requests with identical workload hash `810278341b159d70fc061efcad044a45017d270079d119587be98f2aac348d17`.

| Candidate | Root (GiB) | App Logs (d) | Audit Logs (d) | HTTP Errors (507) | Error Rate | Modeled p95 (ms) | Loopback p95 (ms) | Disk Pressure | Health Gate | Disposition |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Baseline (current) | 50 | 14 | 90 | 0 / 100 | 0.0% | 15 | 0.456 | 0 | **PASS** | Reference baseline |
| **Dev app logs 7d (PR)** | **50** | **7** | **90** | **0 / 100** | **0.0%** | **15** | **0.475** | **0** | **PASS** | **Applied in PR (dev-only)** |
| 36 GiB root + 7d app logs | 36 | 7 | 90 | 0 / 100 | 0.0% | 15 | 0.524 | 0 | **PASS** | Withheld (shared fleet) |
| 30 GiB root + 7d app logs | 30 | 7 | 90 | 48 / 100 | 48.0% | 46 | 0.490 | 48 | **FAIL** | Withheld (HTTP 507 breach) |

Gate thresholds: `error_rate <= 1%`, `modeled_p95_ms <= 20 ms`, `disk_pressure_responses == 0`, `app_retention_days >= 7`, `audit_retention_days == 90`.

## Savings Worksheet (Projected vs. Billed)

> **Projected savings are strictly separate from billed savings.** Nothing counts as saved until subsequent billing exports confirm the reduction. Current billed savings: **$0.00**.

| Item | Service / Resource | Disposition | Projected 7-Day (Low / High) | Projected 30-Day Monthly (Low / High) | Billed Savings |
| --- | --- | --- | ---: | ---: | ---: |
| Dev app log retention (`14d -> 7d`) | `document-service` (`/otterworks/dev/document-service`) | **Implemented in PR** | `$0.0910` / `$0.1092` | **`$0.3900` / `$0.4680`** | **`$0.00`** |
| Audit log retention (`90d`) | `audit-service` (`/otterworks/dev/audit-service`) | Excluded (policy) | `$0.0000` / `$0.0000` | `$0.0000` / `$0.0000` | `$0.00` |
| Root volume `36 GiB` (`50 -> 36 GiB`) | `tenant-compute` (`ec2nodeclass/default:/dev/xvda`) | Withheld (shared fleet) | `$0.0000` / `$0.0000` | `$0.0000` / `$0.0000` | `$0.00` |
| Root volume `30 GiB` (`50 -> 30 GiB`) | `tenant-compute` (`ec2nodeclass/default:/dev/xvda`) | Withheld (HTTP 507 fail) | `$0.0000` / `$0.0000` | `$0.0000` / `$0.0000` | `$0.00` |
| Untagged transfer (`DataTransfer-Regional-Bytes`) | Unallocated | Deferred ($0 claimed) | `$0.0000` / `$0.0000` | `$0.0000` / `$0.0000` | `$0.00` |
| **Total Claimed by This PR** | | | **`$0.0910` / `$0.1092`** | **`$0.3900` / `$0.4680`** | **`$0.00`** |

*Note on `36 GiB` root volume*: Although `36 GiB` passes all local health gates (`0` errors, `15 ms` modeled p95), it is excluded from this PR because `demo-platform/k8s/karpenter/nodepool.yaml` configures the shared workshop cluster fleet. For reference only (not claimed here), if a future dev-isolated `EC2NodeClass` applied `50 GiB -> 36 GiB`, its unimplemented modeled potential would be `$0.3185–$0.3822 / 7d` (`$1.3650–$1.6380 / 30d`).

## Assumptions & Methodology

1. **Low estimate (`$0.3900 / 30d`)**: Uses baseline window demand (`9,100` requests/7d, `91 GB-days` at 7d retention). Lowering retention from 14d to 7d halves steady-state stored byte-days (`$0.0910 / 7d * 30 / 7 = $0.3900 / 30d`).
2. **High estimate (`$0.4680 / 30d`)**: Uses observed window demand (`10,920` requests/7d, +20% demand, `218.4 GB-days` at 14d retention = `$0.2184 / 7d`). Halving steady-state storage saves `$0.1092 / 7d` (`$0.1092 * 30 / 7 = $0.4680 / 30d`).
3. **Retention run-in & scope**: CloudWatch log expiry takes up to 7 days after `PutRetentionPolicy` to reach steady-state storage reduction; ingestion charges are unchanged. The `compare.py` harness exercises a loopback HTTP server with modeled disk pressure and latency and does not mount an EBS volume or exercise CloudWatch expiry delay.
4. **Demand variance excluded**: The `+$0.1547 / 7d` demand-driven increase (+20% requests) is not a configuration defect and is excluded from savings estimates.

## Rollback Steps

1. Revert the single-line change in `infrastructure/terraform/main.tf` (restore `log_retention_days = var.environment == "dev" ? max(var.log_retention_days, 14) : var.log_retention_days`) or run `git revert <commit-sha>` against `demo-finops`.
2. Re-apply the dev Terraform stack (`terraform apply -var="environment=dev"`) so `PutRetentionPolicy` restores `14` days on non-audit dev CloudWatch log groups.
3. Verify `/otterworks/dev/audit-service` remains at `90` days and `demo-platform/k8s/karpenter/nodepool.yaml` remains unchanged (`50Gi`).
