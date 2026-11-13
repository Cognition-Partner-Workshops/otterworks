# audit-service: patch propagation-header memory exhaustion and query-string telemetry leakage

Baseline source: `origin/demo-ciso` commit `449e5f7ae04f5ce64808fc1618072d77e3e97203`.
After source: the service source change in this PR, independently based on that commit.
These are complete locally rebuilt Linux/amd64 image scans, not deployed ECR scans.
Trivy **0.71.0**; vulnerability DB `2026-11-13T12:56:33.451543713Z`, held fixed for both scans.
Java DB metadata is included. The gzip files are unmodified raw scanner JSON,
compressed only for size; `gzip -dc before.trivy.json.gz | jq .` reads them.
No severity filtering, ignore file, ignore-unfixed setting, or suppression was used.
Counts are package/advisory records, not distinct CVEs; no-fix counts mean no
`FixedVersion` published in this scanner database for the installed package.

|Scan|Total|Critical|High|Medium|Low|Unknown|No published fix|
|---|---:|---:|---:|---:|---:|---:|---:|
|Before|417|2|107|151|153|4|415|
|After|415|2|107|149|153|4|415|

Baseline local image ID/digest: `sha256:d20bced7a1f7570826870e4c2b4586a12bf050a417ac467b4ff77620c6a6babf`.
After local image ID/digest: `sha256:06793f1702dc13f4a0c2d04cecb86b94b5855538986f9c58a312503955378042`.
Full target, package versions, finding titles, advisories, layer and base-image
metadata are preserved in the scanner JSON. `removed-records.json` lists the exact
removed package/advisory/version records. Residuals remain visible in the after file.

## Reproduction

Use two separate source worktrees (baseline commit above and this PR) and Trivy 0.71.0.
Preserve the SAME vulnerability and Java DB caches for both scans. Copy the archived
DB into `$TRIVY_CACHE` to reproduce these historical counts; a current DB will differ.
This repository stores metadata rather than the large database artifact.

```bash
# Run from the appropriate baseline/after source worktree; set TAG accordingly.
docker build -t local/audit-service:TAG services/audit-service
trivy --version
cat "$TRIVY_CACHE/db/metadata.json"
docker image inspect local/audit-service:TAG --format '{{.Id}} {{json .RepoDigests}}'
trivy image --cache-dir "$TRIVY_CACHE" --skip-db-update --skip-java-db-update \
  --scanners vuln --ignorefile /dev/null --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL \
  --format json --output scan.json local/audit-service:TAG
```

## Operator reconciliation (NOT executed)

Prerequisites: approved review/merge into `demo-ciso` by an operator; GitHub Actions
permission; AWS access to the intended ECR repository in `us-east-1`; kubeconfig
for `otterworks-dev`. No account ID or live digest has been assumed. The existing
`cd-tenant.yml` runs on a merge/push to `demo-ciso` and reconciles that tenant.
Review that workflow's target before any manual retry. A `rebuild_all=true` retry
rebuilds every tenant service, not just this one, and may interrupt tenant traffic.
No Terraform changes or commands are required by this image-only fix.

```bash
# First inspect the CD run for the reviewed merge commit.
: "${MERGED_SHA:?Set to the reviewed merge commit on demo-ciso}"
gh run list --repo Cognition-Partner-Workshops/otterworks --workflow cd-tenant.yml --branch demo-ciso --commit "$MERGED_SHA"
: "${CD_RUN_ID:?Select the matching CD run ID from the previous output}"
gh run watch "$CD_RUN_ID" --repo Cognition-Partner-Workshops/otterworks --exit-status
# Optional operator-only retry through the official CD system after reviewing current demo-ciso:
gh workflow run cd-tenant.yml --repo Cognition-Partner-Workshops/otterworks --ref demo-ciso --field rebuild_all=true
# Read-only checks, explicitly scoped to the requested context/namespace.
kubectl --context otterworks-dev --namespace otterworks-ciso rollout status deployment/audit-service --timeout=300s
kubectl --context otterworks-dev --namespace otterworks-ciso get deployment/audit-service -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
kubectl --context otterworks-dev --namespace otterworks-ciso get pods -l app.kubernetes.io/name=audit-service -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{range .status.containerStatuses[*]}{.name}{"="}{.imageID}{" "}{end}{"\n"}{end}'
# Set from the matching running container's immutable imageID (remove docker-pullable:// if present).
: "${DEPLOYED_IMAGE:?Set verified ECR repository@sha256:digest from the running container}"
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "${DEPLOYED_IMAGE%%/*}"
trivy image --scanners vuln --ignorefile /dev/null --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL --format json --output deployed-scan.json "$DEPLOYED_IMAGE"
```

Deployment/container names follow the service Helm chart and release names in
`scripts/deploy-tenant.sh`; the service name is the container name. No live AWS or
cluster credentials were available here. Successful local builds/scans do not prove
live rollout, reachability, or elimination of these records in ECR.
