# Cost anomaly attribution: FINOPS_20261128 (dev)

Attribution only. No change is recommended or made here.

- Alert: `aws.cost-anomaly:9f6305ea-bacb-486e-9157-7b3fc3b21a39`, SNS message `8bc7335c-522e-4e98-8226-27832cae01f1`, alert day 2026-11-28
- Scope: account `000000000000`, monitor `arn:aws:ce::000000000000:anomalymonitor/finops-fixture`, env `dev`
- Windows (UTC): baseline 2026-11-14..20, observed 2026-11-21..27
- Sources: `demos/finops/fixtures/billing.csv`, `cloudtrail.json`, `anomaly-sns.json` on `demo-finops` @ a84f1b648
- Cost basis: **unblended** (`cost_usd` = `usage_quantity` x `unit_rate_usd`, synthetic on-demand rates; the export carries no RI/SP amortization or credits, so amortized = unblended here)

Observed total $1.7534 matches the alert's `impact.totalActualSpend`.

## Lines that moved

| Service / usage type | Resource | Baseline 7d | Observed 7d | Delta | Usage/request base -> obs |
|---|---|---|---|---|---|
| document-service / CloudWatch-TimedStorage | `/otterworks/dev/document-service` | 91 GB-day, $0.0910 | 218.4 GB-day, $0.2184 | **+$0.1274** | 0.010 -> 0.020 GB-day |
| tenant-compute / EBS-VolumeUsage.gp3 | `ec2nodeclass/default:/dev/xvda` | 273 GiB-day, $0.6825 | 546 GiB-day, $1.3650 | **+$0.6825** | 0.030 -> 0.050 GiB-day |
| (untagged) / DataTransfer-Regional-Bytes | (none) | none | 17 GB, $0.1700 | **+$0.1700** | n/a |
| **Total** | | $0.7735 | $1.7534 | **+$0.9799** | |

Fleet requests (counted once per day): 9,100 -> 10,920 (+20%).

Split of each attributed delta (volume = baseline x 1.2; config = rest):

| Line | Volume (+20% requests) | Config change |
|---|---|---|
| CloudWatch log storage | +$0.0182 | +$0.1092 (usage per request x2.0, matches 7 -> 14 day retention) |
| EBS gp3 root volumes | +$0.1365 | +$0.5460 (usage per request x1.667, matches 30 -> 50 GiB) |

## Causing changes

| CloudTrail event | Time (UTC) | Resource | Change | Config commit |
|---|---|---|---|---|
| `logs:PutRetentionPolicy` `c29345e7-7232-4d69-816e-672e21a9eb71` | 2026-11-20T23:54:00Z | `/otterworks/dev/document-service` | `retentionInDays` 14 (var default 7) | `infrastructure/terraform/main.tf`: `log_retention_days = var.environment == "dev" ? max(var.log_retention_days, 14) : ...` |
| `ec2:RunInstances` `620ec4b8-afba-4bda-8073-c599d118ac0d` | 2026-11-20T23:58:00Z | `ec2nodeclass/default:/dev/xvda` | gp3 root `volumeSize` 50 | `demo-platform/k8s/karpenter/nodepool.yaml`: `volumeSize: 30Gi -> 50Gi` |

Both config blobs (`fb0f02e0`, `ee6de0c9`) first appear in commit `17dcad000b9d` "Increase dev log history and node storage headroom", author Devin AI (devin-ai-integration[bot]), squash-merged into `demo-finops` as a84f1b648 via [#3405](https://github.com/Cognition-Partner-Workshops/otterworks/pull/3405).

Actor caveat: the synthetic CloudTrail records carry no `userIdentity`, so the actor is taken from the joined commit author, not from CloudTrail. The commit timestamp (2026-11-28) postdates the synthetic event times (2026-11-20); the join is by blob ID per the fixtures README.

## Workload owner

`platform/team: otterworks` (the team label on the document-service Helm deployment). Billing services: `document-service` (log group) and `tenant-compute` (Karpenter `EC2NodeClass default` root volumes). Note `nodepool.yaml` describes node capacity for the shared workshop cluster; this attribution touches nothing there.

## Unattributed (deferred)

- `DataTransfer-Regional-Bytes`, 17 GB, **$0.1700**, 2026-11-27 only: blank service and resource ID (no allocation tag), no workload requests, no matching CloudTrail event. Deferred; no cause and no saving claimed.
