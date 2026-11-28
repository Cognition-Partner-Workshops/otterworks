# file-service PodDisruptionBudget — Kubernetes 1.35 validation

**API check: PASS for file-service.** The [original sweep](https://github.com/Cognition-Partner-Workshops/otterworks/pull/3413) found a removed API in the standalone PDB. Its replacement at the [same sweep input path](../fixtures/legacy-api.yaml) passed the disposable kind v1.35.0 server dry run, and the combined input passed both API scanners. The historical fixture still fails as a negative control. This is API compatibility evidence, not rollout, restart, or wave approval.

Owner: `storage`. Last known-good workload Git: `74421355a6b2df82b2f3d984ffdfdfffa9c8aac2`, Helm revision 1. Restart constraint: none recorded. The standalone PDB is not part of that Helm release.

Only `apiVersion` changed. The budget still requires `minAvailable: 1` for `app: file-service` in `devops-fleet`; a single healthy matching replica is still protected from voluntary eviction. The selector is explicit and non-empty, so the change in empty-selector behavior does not apply. `maxUnavailable` and `unhealthyPodEvictionPolicy` remain unspecified.

## Server dry run on disposable kind v1.35.0

From the repo root with kind v0.31.0 and kubectl v1.34.2. The Git SHA used to extract the historical PDB is the sweep's baseline, not a workload rollout SHA.

```bash
out="$HOME/file-service-pdb-work"
mkdir -p "$out"
export KUBECONFIG="$out/kubeconfig"
pdb=demos/devops/fixtures/legacy-api.yaml
git show "95273d7c5ce14ced2f4d43e5376edf76262292eb:$pdb" > "$out/pdb-before.yaml"
demos/devops/kind/up.sh 1.35
context=kind-devops-20261128-1-35
kubectl --context "$context" version -o yaml
python - "$out/pdb-before.yaml" "$pdb" <<'PY'
import sys
from pathlib import Path
import yaml

before, after = (yaml.safe_load(Path(p).read_text()) for p in sys.argv[1:])
assert (before.pop('apiVersion'), after.pop('apiVersion')) == ('policy/v1beta1', 'policy/v1')
assert before == after
print('All fields except apiVersion are identical.')
PY
kubectl --context "$context" apply --dry-run=server -f "$pdb"
kubectl --context "$context" apply --dry-run=server -f "$pdb" -o json |
  python -c 'import json,sys; d=json.load(sys.stdin); print(d["apiVersion"], d["metadata"]["namespace"], d["metadata"]["name"], d["spec"])'
kubectl --context "$context" apply --dry-run=server -f "$out/pdb-before.yaml"
printf 'Historical fixture dry-run exit=%s\n' "$?"
kubectl --context "$context" --namespace devops-fleet get pdb
```

Output excerpts:

```text
serverVersion:
  gitVersion: v1.35.0
All fields except apiVersion are identical.
poddisruptionbudget.policy/file-service created (server dry run)
policy/v1 devops-fleet file-service {'minAvailable': 1, 'selector': {'matchLabels': {'app': 'file-service'}}}
error: resource mapping not found for name: "file-service" namespace: "devops-fleet" from "/home/ubuntu/file-service-pdb-work/pdb-before.yaml": no matches for kind "PodDisruptionBudget" in version "policy/v1beta1"
ensure CRDs are installed first
Historical fixture dry-run exit=1
No resources found in devops-fleet namespace.
```

## Rerun the 1.35 sweep

With Helm v3.19.5, Pluto v5.23.0, and Python with `platform/standards/fleet/requirements.txt` installed, use the same render and scans as the original sweep, plus the historical combined input as a separate negative control:

```bash
for workload in api-gateway auth-service collab-service document-service file-service search-service; do
  helm template "$workload" platform/standards/helm/app --kube-version 1.35.0 \
    --include-crds --namespace devops-fleet -f demos/devops/values/common.yaml \
    -f "demos/devops/values/$workload.yaml" || exit
done > "$out/rendered.yaml"
{ cat "$out/rendered.yaml"; printf '\n---\n'; cat demos/devops/kind/controls.yaml; } > "$out/desired.yaml"
{ cat "$out/desired.yaml"; printf '\n---\n'; cat "$pdb"; } > "$out/combined.yaml"
{ cat "$out/desired.yaml"; printf '\n---\n'; cat "$out/pdb-before.yaml"; } > "$out/combined-before.yaml"
helm template api-gateway platform/standards/helm/app --kube-version 1.35.0 \
  --include-crds --namespace devops-fleet -f demos/devops/values/common.yaml \
  -f demos/devops/values/api-gateway.yaml -f demos/devops/values/api-gateway-observed.yaml \
  > "$out/gateway-observed.yaml"
curl -fsSL https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.8.1/components.yaml \
  > "$out/metrics-server.yaml"

for scan in desired combined combined-before gateway-observed metrics-server; do
  ns=devops-fleet
  if [ "$scan" = metrics-server ]; then ns=kube-system; fi
  fleet_exit=0
  pluto_exit=0
  python platform/standards/fleet/fleet.py api "$out/$scan.yaml" --target 1.35 --namespace "$ns" \
    --markdown "$out/$scan.md" --json "$out/$scan.json" || fleet_exit=$?
  printf '%s: fleet exit=%s\n' "$scan" "$fleet_exit"
  python -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["counts"]); print(*[r for r in d["resources"] if r["status"] != "no_catalog_finding" or r["resource"] == "policy/PodDisruptionBudget/devops-fleet/file-service"], sep="\n")' "$out/$scan.json"
  pluto detect "$out/$scan.yaml" --target-versions k8s=v1.35.0 || pluto_exit=$?
  printf '%s: Pluto exit=%s\n' "$scan" "$pluto_exit"
done
```

| Input | Fleet exit | Removed | Deprecated | No catalog finding | Pluto exit |
| --- | --- | --- | --- | --- | --- |
| Desired render plus controls | 0 | 0 | 0 | 20 | 0 |
| Desired plus current standalone PDB | 0 | 0 | 0 | 21 | 0 |
| Desired plus historical standalone PDB | **1** | **1** | 0 | 20 | **3** |
| api-gateway observed values render | 0 | 0 | 0 | 3 | 0 |
| Pinned Metrics Server components | 0 | 0 | 0 | 9 | 0 |

```text
{'resource': 'policy/PodDisruptionBudget/devops-fleet/file-service', 'apiVersion': 'policy/v1', 'status': 'no_catalog_finding'}
{'resource': 'policy/PodDisruptionBudget/devops-fleet/file-service', 'apiVersion': 'policy/v1beta1', 'status': 'removed', 'replacement': 'policy/v1', 'removed_minor': 25}
```

The [upstream v1.35.0 OpenAPI](https://raw.githubusercontent.com/kubernetes/kubernetes/v1.35.0/api/openapi-spec/swagger.json) cross-check reported:

```text
/apis/policy/v1/namespaces/{namespace}/poddisruptionbudgets: True
/apis/policy/v1beta1/namespaces/{namespace}/poddisruptionbudgets: False
```

No shared add-ons were changed and no AWS calls were made.

**Rollback:** Revert the PR to restore the prior Git state and red API result; do not apply that reverted `policy/v1beta1` manifest to 1.35. Nothing was persisted by the dry run, so there is no cluster or Helm rollback to perform.
