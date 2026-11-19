# AWS cost audit — 19 November 2026

**Account spend is up, but not all of it is OtterWorks.** Cost Explorer
reported **$341.16 over 30 days ($11.37/day)** across the account, versus
roughly $290/month before the [September rebuild](COST-OPTIMIZATION-2026-09.md).
September's $130–150/month figure was an estimate for the rebuilt OtterWorks
footprint, not an account-wide baseline. The current bill also includes
Bookstore, DAIWT, Bedrock AgentCore and other demos. In particular, the
Bookstore and DAIWT SQL Server instances, not OtterWorks PostgreSQL, are the
ones accruing RDS CPU credit charges in the 14-day metric window.

## Bill and inventory scope

Cost Explorer: unblended USD, UTC **Oct 20–Nov 18 inclusive**, daily by
service, plus service/usage-type and region/service totals. The last seven
days averaged **$14.51/day** (about **$435 per 30 days** if sustained). Nov 18
showed **$13.11**, estimated; Nov 19 returned $0, also estimated and incomplete,
not evidence that running resources are free. Regional totals were $320.88 in
us-east-1, $19.65 in us-east-2, $0.52 global and $0.12 elsewhere (rounded).

| Service | 30-day actual | Average/day |
|---|---:|---:|
| RDS | $72.47 | $2.42 |
| EKS | $71.80 | $2.39 |
| EC2 compute | $68.13 | $2.27 |
| EC2 Other | $31.96 | $1.07 |
| VPC | $23.48 | $0.78 |
| ELB | $23.24 | $0.77 |
| CloudWatch | $17.26 | $0.58 |
| Bedrock AgentCore | $10.77 | $0.36 |
| ECS | $7.72 | $0.26 |
| KMS and Secrets Manager | $7.30 | $0.24 |
| Cost Explorer, Redshift, Glue, S3, Route 53, ECR, Lambda, DynamoDB and remainder | $7.04 | $0.23 |

The [inventory](COST-AUDIT-2026-11-INVENTORY.csv) records observed resources,
ownership and cost coverage (324 inventory rows). Estimate columns are
**components**, not total spend; blank means unavailable, not zero. Pricing
references: AWS [EC2](https://aws.amazon.com/ec2/pricing/),
[EBS](https://aws.amazon.com/ebs/pricing/), [VPC](https://aws.amazon.com/vpc/pricing/),
[ELB](https://aws.amazon.com/elasticloadbalancing/pricing/),
[RDS](https://aws.amazon.com/rds/postgresql/pricing/),
[CloudWatch](https://aws.amazon.com/cloudwatch/pricing/) and
[Fargate](https://aws.amazon.com/fargate/pricing/). The regional checks covered all 17 enabled EC2
regions; S3, Route 53 and CloudFront were queried globally. The audit matched
live IDs to managed AWS instances in the current state objects of the three
OtterWorks roots and other discoverable states in four visible state buckets.
No match means **not found in examined state**, not that the resource has no
owner. CloudFormation tags, Kubernetes tags and service associations are
ownership evidence in their own right.

The payer has not opted in to resource-level Cost Explorer
(`GetCostAndUsageWithResources` returned `AccessDeniedException`). The monthly
figures below are 30-day **actual usage-line totals** or **estimates** from
resource configuration/rates (720 hours/month), not additive: some estimates
are components of the same bill. Usage-based resources without defensible
attribution have no assigned individual cost. Neither this inventory nor
Cost Explorer can prove that every past billed resource still exists, that
every resource was discoverable, or that a service total is all OtterWorks.

## What to keep, change or ask owners about

| Item | Monthly cost / evidence | Safe to remove? |
|---|---|---|
| OtterWorks EKS and managed Spot node(s) | **$71.80** EKS actual (one standard-support cluster, v1.34). EC2 Spot t3/t3a xlarge lines **$54.68** account-wide; observed Spot prices imply **$31.39/$29.30** per continuously running node. ASG desired/min/max 1/1/2; the ASG follow-up had just one healthy `InService` node. The older running node had **9.9%** hourly mean CPU but **95.0%** max; there is no pod memory/headroom evidence for downsizing. | **Keep.** Set a Kubernetes upgrade reminder before standard support for 1.34 ends; right-size only with workload memory, scheduling and burst measurements. |
| EBS volumes and historical EC2 charges | Initial sampling saw two 20 GiB gp3 root disks, **$1.60** each estimated, both attached and delete-on-termination. Follow-up found one attached root disk, consistent with the ASG returning to one node. No unattached EBS volumes in any enabled region. Historical us-east-2 gp3 was **$7.57**; no corresponding volumes remain. The separate on-demand t3.large line was **$13.45**; no live on-demand EC2 was found. | **Keep** attached roots; review whether historical charges recur before assigning savings. |
| Ingress NLB and Bookstore ALB | **$16.20 each** estimated base, plus IPv4 and usage; **$23.24** combined ELB actual. Ingress targets were healthy and saw **675,320 flows / 493 MB** over 14 days. Bookstore's healthy ALB saw **10,666 requests / 111 MB**. No Classic ELBs or targetless v2 LBs found. | **Keep.** NLB is the shared Kubernetes ingress, not a Terraform orphan; the ALB is CloudFormation-owned. |
| Bookstore NAT, VPC endpoints, public IPv4 | NAT **$32.40** estimated base plus data/IP; historical NAT hours + bytes **$14.18** actual. It saw **1.23 GB** ingress bytes from both sides in 14 days and belongs to Bookstore's CloudFormation VPC. Two interface VPC endpoints have three ENIs each; service-specific rates/payer not established, so no dollar savings claimed. Five current EIPs were associated; the historical **$1.68** us-east-2 idle IPv4 line has no current EIP. Ordinary billable IPv4 estimate **$3.60/address** (not a charge assertion for every service ENI). | **Needs owner** for NAT/endpoints and whether public addressing can be reduced. Check routes/consumers before redesign; none of the EIPs are idle. |
| Shared OtterWorks PostgreSQL | **$25.86** actual small-instance line; 20 GiB gp2 **$2.30** estimated, excluding I/O/backup. Terraform and live size are `db.t3.small`; September recorded a micro. 14 days: **5.25%** mean CPU, **64.3%** max, **43** max connections, **899 MiB** minimum freeable memory, **0** surplus CPU credits. | **Keep.** Review the workload and confirm memory/connection headroom under a workshop peak before scheduling any right-size. Low average CPU alone does not justify halving memory. |
| Bookstore and DAIWT RDS SQL Server | The two `db.t3.micro` DBs share **$11.70** instance actual, plus gp2 storage (**$2.30 each** estimate). Observed CPU averaged **31.8% / 30.2%**; maximum connections **18 / 3**. They accrued **8,135 / 5,037** surplus CPU credits in 14 days; CE's account-wide RDS credit line was **$30.80**. Both have CloudFormation stack tags. | **Needs owner.** DAIWT is the first shutdown/teardown candidate after sign-off; its configured backup retention is zero. For ongoing DBs model non-burstable alternatives before changing tiers. |
| EBS and RDS snapshots | Eleven standard EBS snapshots in us-east-2: ten from September, one Nov 2. **$5.90** actual aggregate; incremental billed bytes are not the source volume sizes. No owned us-east-2 AMIs were returned. Manual `bny-demo-snapshot` (Dec 2025) is the only live us-east-2 RDS snapshot; **$0.07** actual regional charged backup line, not necessarily its full run rate. Twelve east-1 RDS snapshots were automated, under active DBs. | **Needs owner** for demo fixtures and the manual snapshot; verify restore/recovery obligations and service dependencies first. **Keep** automated backups. |
| CloudWatch retention and EKS ingestion | **$16.86** actual vended-log ingestion, not an archive-retention charge. EKS group already has **7 days**, **1.36 GB** stored and **19.1 GB** incoming in 14 days. Across 127 groups, 28 had no expiry; 25 contained **60.1 MB** combined (roughly **$0.002/month** at $0.03/GB-month before free allowance). PostgreSQL's unowned group accounts for **4.38 MB** of that and receives ~**1.52 MB/14d**; storage savings today are **less than $0.01/month**, not an ingestion saving. | **Safe to bound development RDS retention**, not delete the group or disable exports. **Needs owner** for other never-expire groups and log sampling/filtering after security/incident review. |
| KMS and Secrets Manager | Four customer-managed keys are enabled (two OtterWorks demo-platform keys in state); no customer key was pending deletion. **$1/month/key** list before request charges. Fourteen secrets: **$0.40/month each** estimated in us-east-1/us-east-2 before APIs/free allowances. CE: **$3.66 KMS / $3.64 Secrets Manager** actual. | **Keep** known dependency keys/secrets. **Needs owner** for the remaining metadata; check KMS and secret consumers before removal. |
| ECS, Bedrock AgentCore and Redshift Serverless | Bookstore has one running ECS Fargate task (0.5 vCPU/1 GiB, **$17.77/month** estimated; **$7.72** actual service). Nine AgentCore runtimes and one gateway; **$10.77** actual, usage-based. Two Redshift Serverless workgroups/namespaces and **$1.63** actual, usage/storage not allocated. | **Needs owner** for schedule/retirement or min-capacity review; this repo does not manage these workloads. |
| S3, ECR, DynamoDB and remaining services | **$0.90 / $0.43 / $0.10** actual, respectively. Three app buckets in state; only the files bucket has a lifecycle rule. Live bucket-size metrics were ~**34 MB** files; no positive size on the sampled metrics for the data-lake/audit-archive buckets. The six app tables plus demo-control are on-demand in state. Their 14-day reads confirm activity even where table size reports zero. See inventory for additional resources and attribution gaps. | **Keep** app storage, registry and state buckets. **Needs owner** on other demos; agree object/version retention and active image references before applying expiration. |

The core Terraform state and live configuration agree on the EKS cluster,
app Postgres, app S3/DynamoDB and scoped app logs. Shared ElastiCache and
MeiliSearch remain off; the separate Bookstore ECS service is not a regression.
The ingress NLB, EC2 nodes/volumes and their IPs are service-managed children,
not missing Terraform resources. The development RDS export group is a
genuine ownership gap. Platform state and the ECR API both show 15 managed
service repositories, but the root checkout declares 13:
`otterworks/order-service` and `otterworks/workbench` are live/state-owned but
absent from the root's desired list. Do not approve any destroy for them until
the owners confirm image consumers and reconcile the declarations with state.
Similarly, tag/ownership gaps in shared-account resources are not evidence
of safe cleanup.

## Proposed rollout

1. **This PR: development RDS logs only.** Use the app's existing retention
   setting (7 days by default) for both RDS export log groups; retain both
   exports. Fresh deployments create the groups before RDS. For the live stack,
   before a separately approved apply, import the existing group into the
   application root as
   `module.database.aws_cloudwatch_log_group.postgres["postgresql"]` with ID
   `/aws/rds/instance/otterworks-postgres-dev/postgresql`. The `upgrade` group did
   not exist at audit time; recheck and import it at the analogous address if
   RDS has since created it. Confirm the next plan shows retention/tag changes
   only on adopted groups and no DB replacement or configuration change.
   Export logs older than seven days first if required; shortening retention
   expires them. **Nothing was imported, applied or changed in AWS.**
2. Ask demo owners to review SQL Server (CPU credits and retirement), Bookstore
   NAT/public IPv4, and the Ohio snapshots in that order. Get approval,
   ownership, dependency/restore checks and a change window before cleanup.
   Keep KMS and shared infrastructure until those checks are complete.
3. Ask the payer to enable daily resource-level Cost Explorer or supply an
   existing Cost and Usage Report with resource IDs; rerun attribution, match
   state across teams and establish a tagged OtterWorks-only baseline. Check
   EKS log producers and size nodes under an active workshop before reducing
   log volume or compute.
