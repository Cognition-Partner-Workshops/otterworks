# Monday fleet sweep: desired versus observed drift

**RED / HELD.** Dev only; no Kubernetes or Helm changes were made. The six
synthetic releases in `devops-fleet` are scoped by
[`kind/fixtures.sh`](../kind/fixtures.sh). Desired Deployments come from the
[platform Helm chart](../../../platform/standards/helm/app) and
[demo values](../values/). The
[observed Deployments](../fixtures/observed-deployments.json) are recorded from
local kind (`kind-devops-20261128-1-34`), not live AWS.

## Evidence

- Read-only source probe: `aws eks describe-cluster --name otterworks-dev --query 'cluster.{Name:name,Status:status}' --output json`
  returned `{"Name":"otterworks-dev","Status":"ACTIVE"}`. A namespace GET
  with `kubectl --context otterworks-dev --request-timeout=15s get namespace devops-fleet -o name`,
  using `aws eks update-kubeconfig --dry-run` and an in-memory EKS token from
  `aws eks get-token`, returned
  `Error from server (NotFound): namespaces "devops-fleet" not found`.
  The AWS CLI's old exec-plugin API version required passing the token in memory
  instead. No token or kubeconfig was saved.
- Linux: `python demos/devops/drift_check.py --markdown demos/devops/evidence/drift-output.md --json "$HOME/.cache/otterworks-fleet-drift.json"`.
  [Output](drift-output.md): exit **1**, six Deployments checked, three
  differences. See [fleet board](fleet-board.md) for the per-workload results.
- Windows (Windows Server 2022, PowerShell, Python 3.13.12, Helm v3.16.4,
  revision `19a5459ec018a6081aaa52f371714995f759debb`), from the repository root:

```powershell
python -m pip install -r platform/standards/fleet/requirements.txt
python demos/devops/drift_check.py --markdown drift-windows.md --json drift-windows.json
$LASTEXITCODE
```

  [Output](drift-windows-output.md): exit **1** (RED), six Deployments checked,
  the same three collab-service differences against the same recorded kind
  snapshot. The Markdown report is identical to the Linux output (same Git
  blob `2a9ad5ee0469573e2262d99204bb29bd46924e02`). The recorded replay tests
  in `platform/standards/fleet/test_fleet.py` also pass on Windows (6 OK).
  No Bash, kubectl, AWS credentials or cluster were used.

## Findings and recommended action

- **collab-service — RED / HELD.** Desired CPU request is `100m`; recorded is
  `320m`. Desired owner is `collaboration`, but both recorded owner labels
  are absent. Recommend the Fleet Steward have the collaboration team confirm
  the owner, the intended CPU request, and the restart window before reviewing
  any dev server-side dry run and rollback. No convergence was attempted.
- **api-gateway — rollout RED.** The drift fields match; the recorded Helm rev 2
  has probes at `/healthz` rather than desired `/health`, and ReplicaSet 2
  has zero ready pods while ReplicaSet 1 retains a ready pod. Rev 2 is not a
  rollback target. Leave recovery to the existing recovery work; no drift-side
  change was proposed.
- **Others:** the drift fields and owner labels match. Recorded Helm history
  and healthy ReplicaSets provide the last known-good revisions on the board.
  For collab-service, Helm rev 1 is the pre-overlay release; the
  [kind setup](../kind/up.sh) waits for all Deployments to become available
  before the [overlay](../kind/observed.overlay.sh) patches it outside Helm.
  The recorded Deployment revision 2 is not a Helm revision.
  The [document-service PDB](../kind/controls.yaml) is the only recorded restart
  constraint found for these workloads.
- **Shared add-ons:** no add-on was compared or changed in this drift check.
  Any change to CNI, CoreDNS, kube-proxy or the ingress controller stays held
  for an owner-approved maintenance window and Fleet Steward review.
