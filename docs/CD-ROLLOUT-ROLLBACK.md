# CD rollout and rollback

## Maturity assessment

| Area | Level after this change | Evidence / remaining gap |
| --- | --- | --- |
| Pipelines | Repeatable | `.github/workflows/cd-tenant.yml` builds changed services, drives dashboard sync, waits for runner completion and smokes ingress. Independent CI/security workflows are not promotion gates. |
| Promotion / approvals | Partial | Deploy/rollback use `t-main` or `workshop` GitHub environments. Reviewers and branch restrictions still require repository settings. Moving tenant/golden tags are not immutable release promotion. |
| Rollout safety | Basic | `scripts/deploy-tenant.sh` bounds Helm history, verifies deployments, and optionally waits atomically/fails strictly. App charts expose rollout policy and optional PDBs. Verification is advisory by default for demo compatibility. |
| Rollback | Manual, repeatable | `scripts/rollback-tenant.sh` and `cd-rollback.yml` show history, roll back selected app releases, wait, and verify. No automatic application rollback on smoke failure; no database/schema rollback. |
| Progressive delivery | Not implemented | Ordinary Deployments, no Argo Rollouts/Flagger or metrics-based traffic shifts. |

Previously tenant CD returned after dashboard enqueue and Helm app upgrades did not
wait. It could be green while pods failed. The tenant detail API
(`demo-platform/dashboard/app/api/tenants/[id]/route.ts`) already returns audit
events. `demo-platform/scripts/tenant.sh sync BRANCH --wait --smoke` now waits for
a **new** `deploy_ok` / `deploy_fail` event, ignoring old events and reconciled
`active` status (`dashboard/lib/tenants.ts`). Missing events fail closed on timeout.
Polling assumes client/runner clocks are synchronized (epoch milliseconds).
This proves runner completion, not every service's business health. Ingress checks
require HTTP 200 from the tenant's recorded web root and API `/health`; results
are written to `GITHUB_STEP_SUMMARY`. Existing sync callers remain enqueue-only.

## Enable safely (before merging the workflow)

1. Configure GitHub environments at
   <https://github.com/Cognition-Partner-Workshops/otterworks/settings/environments>:
   `t-main` allows **main only**; `workshop` allows **workshop-* / demo-* only**.
   Set required reviewers as appropriate. Environments alone do not enforce approval.
2. Review/apply `demo-platform/infra/terraform/iam_github_actions.tf` through the
   platform's normal Terraform process **before** merging environment-gated CD.
   GitHub changes the OIDC subject from a branch to `environment:<name>`; the old
   trust policy rejects it. Existing branch trust remains for image build jobs.
   Environment branch restrictions are essential because the subject loses its ref.
3. For rollback, configure environment secret `AWS_ROLLBACK_ROLE_ARN` with OIDC
   trust for the matching environment, `eks:DescribeCluster`, and EKS access/RBAC
   limited to the intended tenant namespaces: Helm release Secrets, application
   resources (including optional PDBs), and Deployment/ReplicaSet/Pod reads.
   The workflow falls back to `AWS_ROLE_ARN` for existing authorized installations;
   the repository's default CD role intentionally has **no EKS access** and cannot
   perform rollback without separate provisioning. No privileges are widened here.

## Deployment controls

```bash
# Default: no atomic upgrade; rollout failures reported but non-fatal.
scripts/deploy-tenant.sh attendee --branch workshop-attendee
# Opt in only for a demo whose selected app releases are expected to be healthy.
VERIFY_IGNORE=deliberately-broken-service VERIFY_TIMEOUT=120s \
  scripts/deploy-tenant.sh attendee --strict
HELM_ATOMIC=true scripts/deploy-tenant.sh attendee --profile core
# Equivalent CLI atomic switch: --atomic (adds --wait --atomic).
```

`VERIFY_IGNORE` is a comma-separated Deployment-name list; it affects verification,
**not** Helm atomic waiting. `--strict` affects rollout failures, not Helm errors
(Helm errors always fail). Atomic first installs may uninstall a failing release;
never enable atomic upgrades for the full golden tenant: **admin-service is
intentionally crash-looping**. Default CD does not enable atomic/strict or roll it
back; web/gateway smoke does not depend on admin-service. Do not fix that planted bug.
Helm keeps 10 revisions; Deployment `revisionHistoryLimit` defaults to 10.

The 12 ordinary app charts default to RollingUpdate (`maxSurge: 1`,
`maxUnavailable: 0`). Document-service preserves its existing strategy mechanism,
including **Recreate** for main/incident overlays (intentional downtime, no overlap).
All 13 charts have opt-in `pdb.enabled: false`, `pdb.minAvailable: 1`; enabling this
with one replica can block voluntary node drains. PDBs do not prevent Deployment
updates. RollingUpdate needs surge/quota capacity. No Service type changes: ClusterIP.

CLI polling defaults: `CD_WAIT_TIMEOUT=2400` seconds, `CD_POLL_INTERVAL=10`,
`CD_SMOKE_ATTEMPTS=18`. There is no dedicated job-status endpoint; terminal audit
polling uses the existing authenticated tenant detail endpoint. Avoid concurrent
operator operations on the same tenant while waiting or rolling back.

## Rollback runbook

1. Stop new pushes/deploys for the tenant; inspect runner activity and release
   histories. Select the affected service rather than `all` for golden main.
2. Obtain the normal operator kubeconfig (`aws eks update-kubeconfig --name
   otterworks-dev --region us-east-1`) and confirm the context/tenant.
3. Preview, then execute:
   ```bash
   scripts/rollback-tenant.sh attendee api-gateway --dry-run
   scripts/rollback-tenant.sh attendee api-gateway              # previous revision
   scripts/rollback-tenant.sh attendee api-gateway --to-revision 7
   scripts/rollback-tenant.sh attendee all --dry-run
   ```
   Only the 13 known app release names are eligible; `all` selects those installed.
   Each release prints `helm history` before rollback. Missing previous history
   fails visibly; dry-run performs only reads and prints commands. Rollback uses
   `--wait --timeout 4m` (`ROLLBACK_TIMEOUT` override), then Deployment rollout
   status (`VERIFY_TIMEOUT`, default 120s). Errors return nonzero; no uninstall.
4. Alternatively dispatch `.github/workflows/cd-rollback.yml` from an allowed
   branch with tenant, service/all, and optional revision; approve the environment.
   `all` includes admin-service and its wait will fail on golden main by design:
   never use it as an automatic response to that planted failure.
5. Check web root/API health via the tenant's recorded URLs and inspect logs/metrics.
   A Helm rollback does not restore data or moving ECR tags. The next CD sync can
   reapply current images: revert/fix the branch before resuming pushes.

## Phase 2

Use **Argo Rollouts (OSS)** for selected stateless services, retaining ClusterIP
Services and the shared ingress. Start with a canary traffic split and pause;
Prometheus AnalysisTemplates should evaluate request success/error rate and p95
latency against a baseline with minimum traffic/sample thresholds. Failed or
inconclusive analysis should abort to stable and alert; test this in an ephemeral
tenant before enabling it on t-main. Keep planted-bug workloads out of automatic
analysis/rollback until the lab explicitly opts in.

Build once, sign/scan/test and record each image **digest** in an immutable release
manifest. Promote that same manifest across environments behind approvals, never
rebuild or resolve a moving tag during promotion. Add schema compatibility gates,
rollback drills, and CI/security evidence gates before automatic production promotion.
