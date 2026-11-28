# Fleet readiness

Dev fleet, Kubernetes 1.35 sweep. API PASS is not wave readiness. Drift (including Windows) and bounded load are separate checks.

| Workload | Owner (desired) | Kubernetes 1.35 API status |
| --- | --- | --- |
| api-gateway | platform-edge | PASS: desired and observed Helm renders; **HELD for 1.35** per owner decision below |
| auth-service | identity | PASS |
| collab-service | collaboration (recorded Deployment owner label missing) | PASS; owner-label remediation held |
| document-service | content | PASS, including `policy/v1` PDB |
| file-service | storage | **RED**: standalone `policy/v1beta1` PDB removed in 1.25; desired Helm render passes |
| search-service | search | PASS, including `autoscaling/v2` HPA |

## Owner decision: defer shared add-ons

CoreDNS and kube-proxy stay at 1.34 this cycle, and api-gateway stays held for 1.35. No shared add-on changes until platform-runtime confirms 1.35-compatible versions and books the maintenance window with platform-edge before the next sweep.

| Owners' follow-up | Owner | Due | Status |
| --- | --- | --- | --- |
| Confirm 1.35-compatible CoreDNS and kube-proxy versions and book the maintenance window | platform-runtime with platform-edge | Before the next weekly sweep | Open |

[Compatibility commands and results, last known-good revisions, restart constraints, and shared add-on recommendations](k8s-1.35-api-compat.md).
