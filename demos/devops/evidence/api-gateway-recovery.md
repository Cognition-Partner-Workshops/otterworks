# api-gateway recovery — local kind only

**Recovered:** `devops-fleet/api-gateway` is 1/1 ready on the locally stored,
last known-good manifest: Git `74421355a6b2df82b2f3d984ffdfdfffa9c8aac2`,
Helm revision **1**. Helm recorded the rollback as deployed revision **3**.
**Kubernetes 1.35: held.** The workload manifests pass; the recorded EKS add-on
inventory blocks the move. No AWS resources or shared add-ons were changed.

| Fleet-readiness-standard check | Result |
| --- | --- |
| Owner | **Pass:** `platform-edge` in [desired values](../values/api-gateway.yaml) and the observed Deployment. |
| Last known-good | **Pass:** Helm history ties revision 1 to the Git SHA above. The initial rollout was healthy, and revision 3's stored manifest is byte-for-byte identical to revision 1's. |
| Restart constraint | **Pass for local dev:** use RollingUpdate, preserving the serving replica. The Deployment has 25% maxUnavailable (rounds down to 0 of 1) and 25% maxSurge (rounds up to 1). The ready pod kept its UID and had zero restarts through recovery. There is no api-gateway PDB or workload-specific time window declared in the fixture; this does not establish permission to restart elsewhere. |
| API compatibility | **Pass for api-gateway:** no removed APIs in the restored render, and all three objects pass server dry-run on Kubernetes v1.35.0. |
| Desired equals observed | **Red before; pass after:** replica count and both probe paths reconverged; requests, limits and image match, with one updated and available replica. |
| Capacity envelope | **Red before; pass after:** under identical bounded load, the bad rollout stayed at two total replicas, with zero ready for the latest revision. Steady state after rollback kept one ready replica, no restarts, CPU below the 100m request and p95 below 200 ms. No HPA targets api-gateway in either phase. |

## Recorded alarm and local reproduction

[Alarm](../fixtures/alarm.json) and [metric export](../fixtures/cloudwatch-metric.json):
**fixture: recorded, not live AWS**. Alarm `otterworks-devops-api-gateway-not-ready`
was recorded as `ALARM` at `2026-11-28T03:00:08Z`: “The latest rollout revision
reported zero ready replicas for two periods.” This is a per-revision metric,
not a claim that the entire Deployment was down.

Run from repo root using Bash, Helm, kubectl, Docker, kind, Python with the
[fleet runner requirements](../../../platform/standards/fleet/requirements.txt),
and jq. Output below is from this run (irrelevant lines omitted).

```bash
D=demos/devops
F=platform/standards/fleet
C=kind-devops-20261128-1-34
T=kind-devops-20261128-1-35
N=devops-fleet
k() { kubectl --context "$C" -n "$N" "$@"; }
h() { helm --kube-context "$C" -n "$N" "$@"; }
history_rows() { h history api-gateway -o json | jq -r '.[] | [.revision,.status,.description] | @tsv'; }
rs_rows() {
  k get rs -l app=api-gateway -o json | jq -r '.items[] | [
    .metadata.name,.metadata.annotations["deployment.kubernetes.io/revision"],
    .spec.template.spec.containers[0].readinessProbe.httpGet.path,
    .spec.replicas,(.status.readyReplicas // 0)] | @tsv'
}
"$D/kind/up.sh"
kubectl --context "$C" version -o json | jq -r '.serverVersion.gitVersion'
"$D/kind/render.sh" api-gateway > api-gateway-rendered.yaml
"$D/kind/render.sh" --deployments api-gateway > api-gateway-deployment.yaml
history_rows
rs_rows
k rollout status deploy/api-gateway --timeout=5s
```

```text
deployment.apps/api-gateway condition met
v1.34.3
1  superseded  git 74421355a6b2df82b2f3d984ffdfdfffa9c8aac2
2  deployed    git b80e6fb71b5217a2a50f33f0b5e657832c7aa104
api-gateway-55b4df567b  2  /healthz  1  0
api-gateway-f8f79b49d   1  /health   1  1
Waiting for deployment "api-gateway" rollout to finish: 1 old replicas are pending termination...
error: timed out waiting for the condition
```

[The observed overlay](../values/api-gateway-observed.yaml) switched both
HTTP probes to `/healthz`. The chart sends both probes to that path on the
container's HTTP port. The bad pod itself returned 404 at `/healthz` but 200
at `/health`, ruling out a dead HTTP server as the cause of its readiness
failure. The preceding ReplicaSet kept its ready pod.

```bash
bad_rs=$(k get rs -l app=api-gateway -o json | jq -er \
  '.items[] | select(.metadata.annotations["deployment.kubernetes.io/revision"]=="2") | .metadata.name')
bad_pod=$(k get pods -l "pod-template-hash=${bad_rs##*-}" -o jsonpath='{.items[0].metadata.name}')
k get events --field-selector "involvedObject.name=$bad_pod,reason=Unhealthy" \
  -o custom-columns=REASON:.reason,MESSAGE:.message
k exec "$bad_pod" -- python -c 'from http.client import HTTPConnection
for path in ("/healthz", "/health"):
    conn = HTTPConnection("127.0.0.1", 8080, timeout=3)
    conn.request("GET", path)
    print(path, conn.getresponse().status)
    conn.close()'
python "$F/fleet.py" drift api-gateway-deployment.yaml --namespace "$N" --context "$C"
```

```text
Unhealthy   Readiness probe failed: HTTP probe failed with statuscode: 404
/healthz 404
/health 200
```

The drift command exited 1: readiness and liveness differed
(`/health` desired vs. `/healthz` observed). It also reported an omitted
`env` key: Helm renders it as YAML null here and the API omits it. The
post-rollback check below compares the fields named in the standard directly.

## Dry run and rollback

Capture the **before** load sample (commands below) while revision 2 is
deployed. Then preflight the stored revision and roll back only this release.

```bash
h get manifest api-gateway --revision 1 > api-gateway-helm-1.yaml
k apply --dry-run=server -f api-gateway-helm-1.yaml
h history api-gateway -o json > api-gateway-history-pre-dryrun.json
h rollback api-gateway 1 --dry-run --debug
h history api-gateway -o json | diff - api-gateway-history-pre-dryrun.json
k get pod -l app=api-gateway -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,READY:.status.containerStatuses[0].ready,RESTARTS:.status.containerStatuses[0].restartCount
h rollback api-gateway 1 --wait --timeout 120s
k rollout status deployment/api-gateway --timeout=120s
history_rows
h get manifest api-gateway --revision 3 | diff - api-gateway-helm-1.yaml
rs_rows
```

```text
networkpolicy.networking.k8s.io/api-gateway configured (server dry run)
service/api-gateway configured (server dry run)
deployment.apps/api-gateway configured (server dry run)
[debug] rolling back api-gateway (current: v2, target: v1)
[debug] dry run for api-gateway
Rollback was a success! Happy Helming!
# dry-run history diff: no output, exit 0
NAME                           UID                                    READY   RESTARTS
api-gateway-55b4df567b-mhvdt   d22b3bbb-4155-4718-a478-2c24ee072d1f   false   0
api-gateway-f8f79b49d-xj2zd    f02147a4-10a1-4de7-997a-34c891ab0371   true    0
Rollback was a success! Happy Helming!
deployment "api-gateway" successfully rolled out
1  superseded  git 74421355a6b2df82b2f3d984ffdfdfffa9c8aac2
2  superseded  git b80e6fb71b5217a2a50f33f0b5e657832c7aa104
3  deployed    Rollback to 1
# stored manifest diff: no output, exit 0
api-gateway-55b4df567b  2  /healthz  0  0
api-gateway-f8f79b49d   3  /health   1  1
```

Helm kept both source revisions in history. No rebuild or manual pod deletion
was needed. Do not roll forward to revision 2: it is the known-bad revision.

```bash
project='{owner:.metadata.labels.owner,replicas:.spec.replicas,container:(.spec.template.spec.containers[] | select(.name=="api-gateway") | {image,resources,readiness:.readinessProbe.httpGet.path,liveness:.livenessProbe.httpGet.path})}'
sed '${/^---$/d;}' api-gateway-deployment.yaml |
  python -c 'import json,sys,yaml; print(json.dumps(yaml.safe_load(sys.stdin)))' |
  jq -S "$project" > api-gateway-desired-fields.json
k get deploy api-gateway -o json | jq -S "$project" > api-gateway-observed-fields.json
diff -u api-gateway-desired-fields.json api-gateway-observed-fields.json
k get deploy api-gateway -o json | jq '{
  generation:.metadata.generation,observedGeneration:.status.observedGeneration,
  replicas:.status.replicas,updated:.status.updatedReplicas,
  ready:.status.readyReplicas,available:.status.availableReplicas}'
k get pod -l app=api-gateway -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,READY:.status.containerStatuses[0].ready,RESTARTS:.status.containerStatuses[0].restartCount,IMAGE:.status.containerStatuses[0].image
```

Field diff: no output, exit 0. Both sides: owner `platform-edge`, one replica,
image `otterworks/devops-workload:fixture-v1`, requests `100m/128Mi`, limits
`500m/256Mi`, both probes `/health`.

```text
{
  "generation": 3,
  "observedGeneration": 3,
  "replicas": 1,
  "updated": 1,
  "ready": 1,
  "available": 1
}
NAME                          UID                                    READY   RESTARTS   IMAGE
api-gateway-f8f79b49d-xj2zd    f02147a4-10a1-4de7-997a-34c891ab0371   true    0          docker.io/otterworks/devops-workload:fixture-v1
```

## Same bounded load before and after

Run this port-forward in a separate terminal for each phase and stop it when
the capture ends. The steady-state after capture starts once the bad pod is
gone. The [fixed profile](../fixtures/load-profile.json) is 48 requests at
3/s, concurrency 2, request timeout 4s, sample interval 2s, p95 limit 200 ms,
and zero allowed failures.

```bash
kubectl --context "$C" -n "$N" port-forward deployment/api-gateway 18080:8080 --address=127.0.0.1
```

```bash
# phase=before while Helm 2 is active; phase=steady after the bad pod is gone.
phase=before
hpa() {
  k get hpa -o json | jq -c '[.items[] | select(.spec.scaleTargetRef.kind=="Deployment"
    and .spec.scaleTargetRef.name=="api-gateway") |
    {name:.metadata.name,current:.status.currentReplicas,desired:.status.desiredReplicas}]'
}
hpa
python "$F/load_compare.py" capture --profile "$D/fixtures/load-profile.json" \
  --context "$C" --namespace "$N" --deployment api-gateway \
  --url http://127.0.0.1:18080/work --json "api-gateway-load-$phase.json"
hpa
# While the after forward is up:
curl -fsS -o /dev/null -w 'GET /health HTTP %{http_code}\n' http://127.0.0.1:18080/health
python "$F/load_compare.py" compare api-gateway-load-before.json api-gateway-load-steady.json \
  --json api-gateway-load-comparison-steady.json
```

| Metric | Before (Helm 2) | After, steady (Helm 3 → 1) |
| --- | ---: | ---: |
| requests / failures | 48 / 0 | 48 / 0 |
| p95_ms | 21.71 | 18.033 |
| cpu_peak_millicores | 55.259 | 40.583 |
| restarts_before / restarts_after | 0 / 0 | 0 / 0 |
| restarts_on_retained_pods | 0 | 0 |
| replaced_or_removed_pods | 0 | 0 |
| replicas_before / replicas_after / replicas_peak | 2 / 2 / 2 | 1 / 1 / 1 |
| ready_replicas_after (Deployment total) | 1 | 1 |
| elapsed_seconds | 17.67 | 17.64 |
| runner `passed` | true | true |
| Targeting HPA (at start and end) | `[]` | `[]` |
| **Fleet capacity result** | **Red: two total; latest revision 0/1 ready** | **Pass: one total, 1/1 ready** |

After rollback, `GET /health HTTP 200`. Deployment port-forward reaches one
pod, not a fleet-wide service load test. The healthy old pod could serve
requests even with the bad ReplicaSet present. The runner's `passed` field
checks latency, failures and CPU sample availability; it does not clear the
red replica/rollout gate. An initial post-rollback capture during pod
termination reported restart counts 1 → 1 on visible pods and no new restarts.
The sole ready pod had zero restarts; the table uses the settled run after
the terminating revision-2 pod disappeared.

## Kubernetes 1.35 decision

```bash
"$D/kind/up.sh" 1.35
kubectl --context "$T" version -o json | jq -r '"target server: " + .serverVersion.gitVersion'
python "$F/fleet.py" api api-gateway-rendered.yaml --namespace "$N" --target 1.35 --json api-gateway-api-135.json
jq '.counts' api-gateway-api-135.json
kubectl --context "$T" -n "$N" apply --dry-run=server -f api-gateway-rendered.yaml
kubectl --context "$T" -n "$N" get deploy -l app=api-gateway
```

```text
target server: v1.35.0
{"removed": 0, "deprecated": 0, "no_catalog_finding": 3}
networkpolicy.networking.k8s.io/api-gateway created (server dry run)
service/api-gateway created (server dry run)
deployment.apps/api-gateway created (server dry run)
No resources found in devops-fleet namespace.
```

This is workload-scoped; the [legacy PDB fixture](../fixtures/legacy-api.yaml)
belongs to file-service and was not included.

The [EKS inventory](../fixtures/eks-addons.json) is **fixture: recorded, not live AWS**.
It lists VPC CNI `v1.20.4-eksbuild.1` as 1.35-compatible, CoreDNS
`v1.12.4-eksbuild.1` as 1.34-only with no approved maintenance window recorded,
and kube-proxy `v1.34.1-eksbuild.2` as 1.34-only, managed with the control plane.
**Do not schedule api-gateway for the next 1.35 maintenance cycle yet.**
`platform-edge` should coordinate with `platform-runtime` to confirm
compatible add-on versions and an approved maintenance window, including
CoreDNS and the kube-proxy/control-plane plan, then re-evaluate the hold.
This local recovery did not authorize or perform those changes.
