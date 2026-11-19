# Reliability readiness (busy season)

Audit of the `otterworks-dev` EKS cluster and Helm charts, the changes made, and what
is still open. Procedures: [chaos and load testing runbook](runbooks/chaos-and-load-testing.md).

## Findings at audit time

| Area | Finding | Status |
|---|---|---|
| Autoscaling | No HPA anywhere; metrics-server not installed (`kubectl top` failed) | Fixed: metrics-server add-on; HPA template in every chart (opt-in) |
| Disruption | No PodDisruptionBudget for any app; node drains / SPOT reclaims take services fully down | Fixed: PDB (`maxUnavailable: 1`) on by default |
| Redundancy | Every service runs 1 replica, no spread constraints | Fixed: `profiles/high-availability.yaml` (min 2) + node/zone spread |
| Probes | No startup probes; slow JVM/Rails boots rely on fixed `initialDelaySeconds` | Fixed: startup probe (up to 180 s) on every chart |
| Metrics | report-service scraped at `/metrics` (404; actuator is `/actuator/prometheus`) | Fixed |
| Metrics | web-app / admin-dashboard scraped at `/metrics`, which returns the SPA HTML: permanent `TargetDown` | Fixed: scrape disabled; edge metrics cover them |
| Metrics | ingress-nginx (the one entry point) not scraped: no user-facing SLI | Fixed: ServiceMonitor |
| Alerting | No SLO / burn-rate, capacity, unschedulable, HPA-maxed or OOM alerts | Fixed: `otterworks-reliability` PrometheusRule |
| Capacity | One SPOT-only node group (min 1 / max 4, 3 running); CPU requests at ~78% of allocatable | **Open** |
| Prometheus | 1 replica, 3-day retention; Grafana without persistence | **Open** |
| Gateway metrics | `api_gateway_http_requests_total` labels every route `path="other"`, so no per-route SLIs | **Open** |
| t-main | admin-service CrashLoopBackOff (planted bug, left by policy); analytics-service restarting on SQS `InvalidAddressException` | **Open** (analytics needs triage) |

## Game-day results (disposable tenant, 2026-11-19)

Tenant `chaostest` (full profile, golden `:main` images). The core 5 services
(api-gateway, auth, document, file, web-app) ran on the HA profile with HPA min 2 / max 3.
The probe was an authenticated `GET /api/v1/documents/` through the shared ingress, once per second.

| Experiment | Availability during fault | Worst latency | Error window | Result |
|---|---|---|---|---|
| pod-kill api-gateway, **1 replica** (today's default) | 52 % | 0.34 s | 13 s | FAIL |
| pod-kill api-gateway, HA (2 replicas + PDB) | 100 % | 0.24 s | 0 s | PASS |
| dependency-outage redis, 60 s | 100 % | 0.28 s | 0 s | PASS (documents path does not need redis) |
| cpu-stress document-service, 120 s | 100 % | 0.96 s | 0 s | PASS; HPA scaled 2 -> 3 |
| pod-kill document-service during k6 load | 100 % | 0.30 s | 0 s | PASS |

k6 `PROFILE=load` (30 VUs, 4 min steady state): 22,921 requests at 47 req/s, 0 % failed.
Read p95 was 101 ms and p99 109 ms, so every threshold passed. At 30 VUs the gateway sat at 35 %
of its CPU request and document-service at 31 %, with no HPA scale-out. 30 VUs is well
below the knee; use `PROFILE=stress` to find it.

Found during the run:
- With 1 replica (the current default for every tenant), losing one pod is a user-visible outage of about 13 s.
- The ordinary tenant `ResourceQuota` caps `limits.cpu` at 12. The full profile plus HA on 5 services hit it during the game day, blocking HPA scale-out with `exceeded quota`. `scale-for-load.sh ... up` now applies a separate HA quota without raising cheap default tenants' quotas; see the [quota budget](LOAD-TESTING.md#cpu-limit-intervention-and-ha-quota).
- The new chart values originally broke `helm upgrade --reuse-values`, which `inject-bug.sh` uses, on existing releases. Fixed: the templates are nil-safe.
- A tenant created with `deploy-tenant.sh` alone is garbage-collected by the demo-platform reaper within 15 minutes. Use `demo-platform/scripts/tenant.sh checkout`.

## Alert routing

Every `otterworks-reliability` alert carries `team: sre` and goes to the SRE receiver that
the sre-observability chart routes. `page: devin` is reserved for the document-service
incident-responder rules. Critical: t-main (`otterworks-main`) gateway 5xx > 5 % (5 m),
gateway p95 > 1.5 s (10 m), ingress 5xx > 5 %, a core deployment with zero available
replicas, and node NotReady. Demo-tenant and capacity alerts are warnings, because demo
tenants run planted bugs and injected scenarios on purpose.

## Recommended before peak (not done here)

1. Capacity: add an on-demand node group (or install Karpenter, `demo-platform/scripts/install-karpenter.sh`) and raise the node max; at 78 % CPU requests the HA profile does not fit today.
2. Run the runbook's load and chaos suite on a disposable tenant and record the knee (max RPS within SLO) per service.
3. Prometheus: 2 replicas and >= 15-day retention on a PVC; enable Grafana persistence.
4. Gateway: label requests by route template so per-endpoint latency/error alerts are possible.
5. Disable the kube-prometheus-stack scheduler / controller-manager / etcd rules on EKS (control plane is not scrapeable, so they are always firing).
