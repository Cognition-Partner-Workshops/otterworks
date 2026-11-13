# report-service: Disable dangerous default interpolation lookups

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
|Before|203|14|58|111|19|1|35|
|After|202|13|58|111|19|1|35|

Baseline local image ID/digest: `sha256:340c82f7246837bb8e8336c69941f5ef9b3c18c1972e3f1c4029e97b0e4167f3`.
After local image ID/digest: `sha256:d164cceb55b49a3ceda42c688be7b1067d15cd0a30e97d1aace9f9314075184b`.
Full target, package versions, finding titles, advisories, layer and base-image
metadata are preserved in the scanner JSON. `removed-records.json` lists the exact
removed package/advisory/version records. Residuals remain visible in the after file.

## Reproduction

This patch upgrades Commons Text 1.9 to 1.10.0, removing critical CVE-2022-42889
(Text4Shell): configured report templates can otherwise trigger script execution,
DNS resolution and outbound URL fetches. The registered transcript retains all
8 contract cases byte-for-byte and leaves the 3 dangerous lookup markers literal.
The historical owner directive `${script:javascript:"ops-analyst"}` is supported
only as a whole-string quoted identity matching `[A-Za-z0-9._@-]+`; no JavaScript
engine or disabled global lookup is restored. Executable, concatenated and prefixed
forms fail closed even for an administrator. This is a deliberately narrow legacy
configuration compatibility rule, not a general script evaluator.

Validation: 105 tests, 0 failures/errors/skips with transcript emission enabled;
the unchanged repository grader passes all 11 before/after transcript cases.
The emitted observations and full grades are included. Checkstyle still reports
the two unchanged 121-character lines in ReconciliationRepository.java:126 and
JdbcArchiveStoreTest.java:171; no new violation was introduced.

To repeat the service and transcript validation using the Maven mirror:

```bash
cd services/report-service
mvn -s ../../security/evidence/report-commons-text/maven-settings.xml test \
  -Dow.deps.cases="$PWD/../../security/deps/cases/report-service.json" \
  -Dow.deps.observed="$PWD/target/text-after-observed.json"
cd ../..
make deps-transcript MODULE=report-service
```

The captured run used the Java 8 Maven builder container, matching this service's
runtime and CI. The harness normally requests JDK 11 for Nashorn availability;
Java 8 also supplies Nashorn. The unchanged Python grading function was invoked
on the actual emitted JSON; no golden recordings or attack cases were edited.
The estate-wide `make deps-gate` does not accept a module filter; other services
still carry the advisory and are outside this PR's exclusive report-service scope.
The captured `after-tree.txt` and image scan show that this module resolves 1.10.0
and no longer contains the vulnerable artifact version.

Use two separate source worktrees (baseline commit above and this PR) and Trivy 0.71.0.
Preserve the SAME vulnerability and Java DB caches for both scans. Copy the archived
DB into `$TRIVY_CACHE` to reproduce these historical counts; a current DB will differ.
This repository stores metadata rather than the large database artifact.

```bash
# Run from the appropriate baseline/after source worktree; set TAG accordingly.
docker build -t local/report-service:TAG services/report-service
trivy --version
cat "$TRIVY_CACHE/db/metadata.json"
docker image inspect local/report-service:TAG --format '{{.Id}} {{json .RepoDigests}}'
trivy image --cache-dir "$TRIVY_CACHE" --skip-db-update --skip-java-db-update \
  --scanners vuln --ignorefile /dev/null --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL \
  --format json --output scan.json local/report-service:TAG
```

Maven Central returned HTTP 429. These scans used an otherwise identical, build-only
Dockerfile with `RUN mvn` replaced by
`RUN --mount=type=secret,id=maven-settings,target=/root/.m2/settings.xml mvn`.
The supplied settings mirror Central to Google's Central mirror; no settings are
copied into the application image. No dependency versions are overridden.

```bash
sed 's/RUN mvn /RUN --mount=type=secret,id=maven-settings,target=\/root\/.m2\/settings.xml mvn /g' services/report-service/Dockerfile > /tmp/report-scan.Dockerfile
docker build -f /tmp/report-scan.Dockerfile --secret id=maven-settings,src=security/evidence/report-commons-text/maven-settings.xml -t local/report-service:text services/report-service
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
kubectl --context otterworks-dev --namespace otterworks-ciso rollout status deployment/report-service --timeout=300s
kubectl --context otterworks-dev --namespace otterworks-ciso get deployment/report-service -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
kubectl --context otterworks-dev --namespace otterworks-ciso get pods -l app.kubernetes.io/name=report-service -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{range .status.containerStatuses[*]}{.name}{"="}{.imageID}{" "}{end}{"\n"}{end}'
# Set from the matching running container's immutable imageID (remove docker-pullable:// if present).
: "${DEPLOYED_IMAGE:?Set verified ECR repository@sha256:digest from the running container}"
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "${DEPLOYED_IMAGE%%/*}"
trivy image --scanners vuln --ignorefile /dev/null --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL --format json --output deployed-scan.json "$DEPLOYED_IMAGE"
```

Deployment/container names follow the service Helm chart and release names in
`scripts/deploy-tenant.sh`; the service name is the container name. No live AWS or
cluster credentials were available here. Successful local builds/scans do not prove
live rollout, reachability, or elimination of these records in ECR.
