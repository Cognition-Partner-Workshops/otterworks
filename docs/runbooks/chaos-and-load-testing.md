# Runbook: Chaos and load testing

Run both against a **disposable tenant**, never t-main (`otterworks-main`).
The chaos script refuses t-main; the load script only allows `READ_ONLY=1` there.

## 0. One-time cluster prerequisites

```bash
./scripts/install-cluster-addons.sh   # metrics-server, ingress-nginx ServiceMonitor, reliability alerts
```

## 1. Stand up a test tenant at busy-season shape

```bash
# Register through the dashboard: a tenant made with deploy-tenant.sh alone is
# reaped as an orphan within 15 minutes.
./demo-platform/scripts/tenant.sh checkout loadtest main 6h
./scripts/scale-for-load.sh loadtest up          # HPA 2..6, PDB, node + zone spread
```

The tenant ResourceQuota caps limits.cpu at 12: on the full profile, scale unused
services to 0 or raise the quota, or HPA scale-out fails with `exceeded quota`.
Check headroom first: `cluster:cpu_requests:ratio` in Prometheus must stay under ~0.85
after scaling, or HPA scale-ups will go Pending (`OtterworksPodsUnschedulable`).

## 2. Load test (k6)

```bash
BASE=https://api-t-loadtest.<domain>
k6 run -e BASE_URL=$BASE -e PROFILE=smoke  tests/load/k6/otterworks.js   # sanity, 1 min
k6 run -e BASE_URL=$BASE -e PROFILE=load   -e TARGET_VUS=50  tests/load/k6/otterworks.js
k6 run -e BASE_URL=$BASE -e PROFILE=stress -e TARGET_VUS=50  tests/load/k6/otterworks.js
k6 run -e BASE_URL=$BASE -e PROFILE=spike  -e TARGET_VUS=200 tests/load/k6/otterworks.js
```

Thresholds match the paging SLOs: <1% errors, read p95 < 800 ms, p99 < 1.5 s.
While it runs, watch Grafana *OtterWorks Overview* and `kubectl get hpa -n otterworks-loadtest -w`.
Record for each profile: max sustained VUs/RPS within SLO, first service to saturate,
replica count at peak, and whether any pod restarted or OOMKilled.

## 3. Chaos experiments

Each prints baseline vs fault availability, worst latency, error window and time to
recover, and exits non-zero when availability drops below `SLO_AVAILABILITY` (0.99).

| Experiment | Command | Expected with HA profile |
|---|---|---|
| Pod loss | `scripts/chaos/chaos-experiment.sh loadtest pod-kill api-gateway` | No errors (second replica serves) |
| Cache outage | `scripts/chaos/chaos-experiment.sh loadtest dependency-outage redis` | Degraded, no 5xx on reads |
| Search outage | `scripts/chaos/chaos-experiment.sh loadtest dependency-outage meilisearch` | Search fails, rest serves |
| CPU saturation | `scripts/chaos/chaos-experiment.sh loadtest cpu-stress document-service` | HPA scales out, p95 recovers |
| App fault | `scripts/chaos/chaos-experiment.sh loadtest scenario document-slow` | Latency alert fires (warning) |
| Node / SPOT loss | `scripts/chaos/chaos-experiment.sh loadtest node-drain --allow-cluster-impact` | PDB keeps 1 replica up; reschedules |

`node-drain` evicts every tenant's pods on that node: run it only in an agreed window.
Run a chaos experiment while `PROFILE=load` is running to test failure under load.

## 4. Clean up

```bash
./scripts/inject-bug.sh loadtest reset
./scripts/scale-for-load.sh loadtest down
./demo-platform/scripts/tenant.sh checkin loadtest
```
