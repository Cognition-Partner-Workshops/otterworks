# Fleet readiness board — dev recovery

| Workload | Owner | Deployed revision | Desired revision | API status (1.35) | Add-on status (1.35) | HPA | Requests | Proof | Rollback | Readiness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `devops-fleet/api-gateway` | `platform-edge` | Helm 3 (rollback to 1) | Git `74421355a6b2df82b2f3d984ffdfdfffa9c8aac2`, Helm 1 | Pass: Kubernetes v1.35.0 accepted all three rendered objects in a server dry run | Blocked in the recorded EKS inventory: CoreDNS and kube-proxy list only 1.34 | None targets api-gateway; fixed at 1 replica | 100m CPU, 128Mi memory | [Rollback and six readiness checks](api-gateway-recovery.md) | Roll back to Helm 1 in dev, dry run first | **Recovered on local kind; held for Kubernetes 1.35** |

**Restart constraint:** Use a rolling update that preserves the one available replica in dev;
do not delete the serving pod to recover the rollout. No workload-specific maintenance
window is recorded. Shared add-on work requires an owner-approved maintenance window and
was not performed. The failed revision and pre-rollback capacity result remain red.
