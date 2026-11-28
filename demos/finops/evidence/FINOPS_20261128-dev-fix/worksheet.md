# FINOPS_20261128 — dev correction worksheet

- **Source:** `aws.cost-anomaly:9f6305ea-bacb-486e-9157-7b3fc3b21a39`, SNS delivery `8bc7335c-522e-4e98-8226-27832cae01f1`, alert date 2026-11-28 UTC.
- **Spend scope:** dev, account `000000000000`, monitor `arn:aws:ce::000000000000:anomalymonitor/finops-fixture`, 2026-11-21 to 2026-11-27 inclusive (UTC).
- **Workload owner:** `platform/team: otterworks` (the [document-service deployment label](../../../../infrastructure/helm/document-service/templates/deployment.yaml)); billed services are `document-service` (app logs) and `tenant-compute` (node roots).
- **Prior evidence:** [Attribution #3418](https://github.com/Cognition-Partner-Workshops/otterworks/pull/3418) isolates the retention and root-volume changes after adjusting for +20% fleet requests; [dev baseline #3419](https://github.com/Cognition-Partner-Workshops/otterworks/pull/3419) supplies the reference settings and workload.
- **Audit:** Keep the 90-day minimum and configured retention unchanged. Explicitly exclude `/otterworks/dev/audit-service` from the retention change and all savings calculations.

## Matched dev health results

Each run used the same 100 synthetic requests as #3419 (SHA-256 `810278341b159d70fc061efcad044a45017d270079d119587be98f2aac348d17`). Gates: error rate ≤1%, modeled p95 ≤20 ms, no disk pressure, app retention ≥7 days, audit retention unchanged at 90 days. Loopback p95 is measured but informational.

| Run | Root (GiB) | App retention (days) | Audit (days) | Requests | Errors | Modeled p95 (ms) | Loopback p95 (ms) | HTTP 507s | Health / disposition |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| [Baseline](1-baseline.json) | 50 | 14 | 90 | 100 | 0 (0%) | 15 | 0.852 | 0 | Pass / reference |
| [A — app logs only](2-logs-only.json) | 50 | 7 | 90 | 100 | 0 (0%) | 15 | 1.399 | 0 | Pass independently |
| [B — disk only](3-disk-only.json) | 36 | 14 | 90 | 100 | 0 (0%) | 15 | 0.456 | 0 | Pass independently |
| [A + B — combined](4-combined.json) | 36 | 7 | 90 | 100 | 0 (0%) | 15 | 2.672 | 0 | Pass / proposed |
| [30 GiB + A](5-rejected-30gib.json) | 30 | 7 | 90 | 100 | 48 (48%) | 46 | 0.708 | 48 | Fail / withheld |

The 30 GiB candidate failed the error-rate, modeled latency, and disk-pressure gates, despite passing both retention gates. The 36 GiB candidate has 2 GiB above the model's maximum 34 GiB allocation (27 GiB reserved + 7 GiB scratch). This loopback proof models dev settings; it does not benchmark live nodes, resize disks, or measure CloudWatch log expiry.

## Savings worksheet

**Basis:** Synthetic unblended USD (`usage_quantity × unit_rate_usd`) from the [billing fixture](../../fixtures/billing.csv), with no RI/SP amortization or credits. Use the observed seven-day usage and the two attributed rates only. The app-log projection applies only to stored bytes for `/otterworks/dev/document-service`, not ingest, other log groups, or audit. The unallocated regional transfer charge ($0.1700) receives no savings credit.

| Passing correction | Observed 7-day usage | Projected 7-day usage at observed activity | Fixture rate (USD/unit) | Observed → projected 7-day cost (USD) | Projected 7-day savings (USD) | Low 30-day (USD) | High 30-day (USD) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A — CloudWatch-TimedStorage | 218.4 GB-days | 109.2 GB-days | 0.001 / GB-day | 0.2184 → 0.1092 | 0.1092 | 0.3900 | 0.4680 |
| B — EBS-VolumeUsage.gp3 | 546 GiB-days | 393.12 GiB-days | 0.0025 / GiB-day | 1.3650 → 0.9828 | 0.3822 | 1.3650 | 1.6380 |
| **A + B — total** | — | — | — | **1.5834 → 1.0920** | **0.4914** | **1.7550** | **2.1060** |

- **Usage model:** At a fixed activity level, app storage scales by `7/14` once steady state is reached; assume stable ingest at that activity, no retention run-in or expiry delay, and no ingest cost change. Provisioned gp3 GiB-days scale by `36/50` at the same node-volume time; assume unchanged gp3 rates and that eligible dev node roots run at the proposed size for the full period.
- **Low:** Assume activity at the historical 9,100 requests/week, versus 10,920 observed. For this fixture, scale both the app byte-days and node-volume time in proportion to activity (`9,100 / 10,920`); apply `30 / 7` to translate seven days into a 30-day month.
- **High:** Assume the observed 10,920 requests/week and its observed app and node activity persist; apply `30 / 7` without a volume adjustment. These are two fixture scenarios, not guaranteed limits.
- **Projected savings: $1.7550–$2.1060 per 30 days. Confirmed billed savings: $0.0000.** There is no post-change bill or live rollout; recognize savings only after comparable post-change billed data supports them.

## Proposed dev change and rollback

Keep the correction scoped to dev: move from 50 to 36 GiB on dev-only roots and 14 to 7 days for the dev document-service application log group. The [forward plan](plan-forward.txt) changes one provider-free `terraform_data.dev_settings` resource; no AWS or shared-fleet change is included. Do not apply these values to the shared Karpenter node class or a global log-retention input. A real rollout needs an isolated dev target for each correction.

The [rollback plan](plan-rollback.txt) restores 36 → 50 GiB and 7 → 14 days while holding audit at 90 days. If a dev rollout breaches a gate, restore the document-service policy to 14 days and reprovision dev-only roots at 50 GiB, then rerun the same 100-request gate against the baseline. Restoring the retention setting cannot recover logs already expired.

[Machine-readable worksheet](worksheet.json)
