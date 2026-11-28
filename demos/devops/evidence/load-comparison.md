# Bounded load vs request envelope (dev, local kind 1.34)

Scope: capacity envelope only (fleet-readiness-standard check 6). 1.35 API compatibility and drift are reported separately.

- Cluster: `kind-devops-20261128-1-34` (Kubernetes v1.34.3, local kind, dev only), namespace `devops-fleet`, brought up with `demos/devops/kind/up.sh` at `demo-devops` 95273d7c5.
- Profile: `demos/devops/fixtures/load-profile.json` for both phases (48 requests, 3/s, concurrency 2, p95 limit 200 ms, 0 failures allowed) against `/work` through `kubectl port-forward`.
- Before and after are two captures of the same profile on the same context, 30 s apart, with no change to the cluster in between. Nothing was changed on the cluster.
- Commands: `demos/devops/evidence/load/run.sh`; console output in `load/run.log`; per-workload JSON and Markdown in `load/`.
- Envelope = CPU peak within requests.cpu x replicas, no restarts, all replicas ready, replicas and HPA unchanged, p95 and failures inside the profile.
- Port-forward sends every request to one pod, so multi-replica workloads (api-gateway, document-service) were loaded through a single pod.

## Result

| Workload | p95 ms before / after | CPU peak m before / after | CPU envelope m | Restarts during load | Ready / pods | Replicas / HPA | Load gate | Envelope |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| api-gateway | 20.6 / 17.7 | 27.3 / 53.3 | 100 (1 x 100m) | 0 / 1 | 1 / 2 | 2 / no HPA | pass | **red** |
| auth-service | 23.4 / 18.1 | 24.3 / 14.9 | 100 | 0 / 0 | 1 / 1 | 1 / no HPA | pass | green |
| collab-service | 20.5 / 27.1 | 17.0 / 14.7 | 320 observed (100 desired) | 0 / 0 | 1 / 1 | 1 / no HPA | pass | green (held: no owner observed) |
| document-service | 21.6 / 20.0 | 8.4 / 24.6 | 200 (2 x 100m) | 0 / 0 | 2 / 2 | 2 / no HPA | pass | green |
| file-service | 19.3 / 18.1 | 16.3 / 35.3 | 100 | 0 / 0 | 1 / 1 | 1 / no HPA | pass | green |
| search-service | 2300.5 / 1899.8 | 24.8 / 25.0 | 20 (limit 25m) | 0 / 0 | 1 / 1 | 1 / HPA 1-1 | **fail** | **red** |

- search-service: red in both phases. p95 is 9-11x the 200 ms limit and CPU sits at its 25m limit, above its 20m request; the HPA (min 1, max 1) cannot add replicas. Blocks its wave.
- api-gateway: red. Helm revision 2 (`api-gateway-observed.yaml`, probes on `/healthz`, which the workload answers 404) never became ready; that pod restarted during the after phase (7 restarts by the end of the run) while the revision-1 pod served the load. The p95 gate passing does not clear it. The api-gateway recovery PR is separate; this run predates it.
- collab-service: inside its envelope, but the observed Deployment has no `owner` label and a 320m CPU request against 100m desired, so it is held for the owner, not converged here.

## Owner, last known-good, restart constraint (as found)

| Workload | Owner (desired values) | Last known-good (Git SHA, Helm revision) | Restart constraint |
| --- | --- | --- | --- |
| api-gateway | platform-edge | 74421355a6b2df82b2f3d984ffdfdfffa9c8aac2, Helm rev 1 (rev 2 at b80e6fb71b52 is deployed but unhealthy) | None declared; RollingUpdate 25%/25% |
| auth-service | identity | 74421355a6b2df82b2f3d984ffdfdfffa9c8aac2, Helm rev 1 | None declared; RollingUpdate 25%/25% |
| collab-service | collaboration in desired; none observed | 74421355a6b2df82b2f3d984ffdfdfffa9c8aac2, Helm rev 1 (live object patched outside Helm) | None declared; RollingUpdate 25%/25% |
| document-service | content | 74421355a6b2df82b2f3d984ffdfdfffa9c8aac2, Helm rev 1 | Restart only in an approved maintenance window (PDB minAvailable 2 of 2, 0 disruptions allowed) |
| file-service | storage | 74421355a6b2df82b2f3d984ffdfdfffa9c8aac2, Helm rev 1 | None declared; RollingUpdate 25%/25% |
| search-service | search | 74421355a6b2df82b2f3d984ffdfdfffa9c8aac2, Helm rev 1 | None declared; RollingUpdate 25%/25% |

No shared add-on (CNI, CoreDNS, kube-proxy, ingress controller) was touched. All data above is from the local kind cluster; no recorded AWS snapshot or alarm payload was used.
