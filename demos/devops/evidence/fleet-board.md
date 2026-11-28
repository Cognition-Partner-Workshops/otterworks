# Fleet readiness

Dev fleet, Kubernetes 1.35 sweep. This entry records **API compatibility only**; API PASS is not wave readiness. Drift (including Windows) and bounded load are separate checks.

| Workload | Owner (desired) | Kubernetes 1.35 API status |
| --- | --- | --- |
| api-gateway | platform-edge | PASS: desired and observed Helm renders; recovery tracked separately |
| auth-service | identity | PASS |
| collab-service | collaboration (recorded Deployment owner label missing) | PASS; owner-label remediation held |
| document-service | content | PASS, including `policy/v1` PDB |
| file-service | storage | **RED**: standalone `policy/v1beta1` PDB removed in 1.25; desired Helm render passes |
| search-service | search | PASS, including `autoscaling/v2` HPA |

[Compatibility commands and results, last known-good revisions, restart constraints, and shared add-on recommendations](k8s-1.35-api-compat.md).
