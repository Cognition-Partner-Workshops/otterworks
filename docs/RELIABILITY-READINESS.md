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
