# Runbook: HighMemoryUsage / HighMemoryUsageCritical

**Severity:** warning (80 %) / critical (90 %) · **Rule file:** `observability/prometheus/alerts.yml` (group `otterworks.resources`)

> **Does this page?** Not on its own. The rule has no `page` label, so
> Alertmanager (`observability/alertmanager/alertmanager.yml.tmpl`) sends it to
> the default `sink` receiver only. Only `page: devin` rules
> (`observability/prometheus/incident_alerts.yml`) reach the Devin webhook and
> `#otterworks-alerts`. If you are looking at this at night, either someone
> forwarded it or a paging alert on the same service fired alongside it. Check
> both.

The document-service has its own paging version, `DocumentServiceMemoryHigh`
(RSS / container limit > 75 % for `1m`, `page: devin`), driven by
document-service's own `otterworks_process_*` gauges. Its runbook is
[`incident/README.md#cache-leak`](../../incident/README.md#cache-leak).

## What it means

One process's resident memory (`process_resident_memory_bytes`, exported by the
service's Prometheus client) is above 80 % (warning) or 90 % (critical) of
`machine_memory_bytes`. If it keeps growing, the kernel or the kubelet kills
it (`OOMKilled`) and every request in flight fails.

**Read this before you trust the number.** `machine_memory_bytes` comes from
cAdvisor/kubelet, and the Compose stack does not scrape cAdvisor. So on Compose
the expression returns nothing and the alert **cannot fire**. On EKS the
denominator is the whole node's memory, not the pod's limit. A pod can be
OOM-killed at its own limit well before this alert fires. Treat the alert as
"this process is very large relative to the node". Use step 2 to see how close
it is to its own limit.

## Threshold and why

`process_resident_memory_bytes / machine_memory_bytes > 0.80` for `5m`
(warning) and `> 0.90` for `2m` (critical). 80 % leaves time to react before
the node itself is under memory pressure. The critical level gets the shorter
`for` because at 90 % an OOM kill is minutes away.

## First three things to check

1. **Which process, and is it growing or flat?**
   ```bash
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=process_resident_memory_bytes / on (instance) group_left machine_memory_bytes' | jq -r '.data.result[] | "\(.metric | to_entries | map("\(.key)=\(.value)") | join(" ")) \(.value[1])"'
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=deriv(process_resident_memory_bytes{job="<service>"}[30m])' | jq -r '.data.result[] | "\(.metric | to_entries | map("\(.key)=\(.value)") | join(" ")) \(.value[1])"'
   ```
   If the result is empty, cAdvisor is not scraped here (see above), so fall
   back to `process_resident_memory_bytes{job="<service>"}` alone. A steady
   positive `deriv` with flat traffic is a leak. A step change after a deploy
   is a new baseline.
2. **How close is it to the container's own limit, and has it already been
   killed?**
   ```bash
   docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.MemPerc}}' | grep otterworks-   # Compose
   kubectl -n otterworks-<tenant> top pod -l app.kubernetes.io/name=<service>
   kubectl -n otterworks-<tenant> get pod -l app.kubernetes.io/name=<service> \
     -o jsonpath='{range .items[*]}{.metadata.name} {.status.containerStatuses[0].restartCount} {.status.containerStatuses[0].lastState.terminated.reason}{"\n"}{end}'
   ```
   Grafana **OtterWorks Infrastructure** (`/d/otterworks-infrastructure`) →
   *Node Memory Utilization*, *OOMKilled Events (24h)* and *Pod Restarts (1h)*.
3. **What is holding the memory?** For document-service, compare
   `otterworks_render_cache_entries` with RSS. If they climb together, it is
   the unbounded render cache (the planted `cache-leak`, gated by
   `chaos:document-service:render_cache`). For JVM services (auth,
   notification, analytics) look at heap metrics, if exported, before RSS.
   For any service, check the logs for very large payloads or a batch job that
   started when the growth did.

## Mitigate

- Restart the one instance to buy time:
  `kubectl -n otterworks-<tenant> rollout restart deploy/<service>`. Write
  down the growth rate first. A leak comes back at the same rate, so a restart
  does not fix it.
- Roll back if a deploy matches when the growth started.

## How to tell it is fixed

- The ratio is below 70 % and the 30-minute `deriv` is flat (near zero) under
  normal traffic for at least 30 minutes. A leak needs a longer window than a
  spike to rule out.
- No new `OOMKilled` restarts, and both alerts have resolved.

## Escalate when

- `HighMemoryUsageCritical` fires, or the pod has already been OOM-killed more
  than once in an hour.
- More than one service on the same node is high (node pressure, a platform
  concern).
- The growth comes back after a restart. That is a code leak, so hand it to
  the service owner with the growth rate from step 1.

**Where to run the commands**

| | Local Compose stack | Shared EKS cluster (`otterworks-dev`) |
|---|---|---|
| Prometheus | `http://localhost:9090` | `kubectl -n monitoring port-forward svc/prometheus-prometheus 19090:9090` |
| Grafana | `http://localhost:3001` (`admin` / `otterworks`) | `https://grafana.otterworks.app` |
| Alertmanager | `http://localhost:9093` | `kubectl -n monitoring port-forward svc/prometheus-alertmanager 19093:9093` |
| Jaeger | `http://localhost:16686` | `https://jaeger.otterworks.app` |
| Workloads | `docker compose -f docker-compose.yml -f docker-compose.infra.yml ps` | `kubectl -n otterworks-<tenant> get pods` (`otterworks-main` for t-main) |

Pods carry `app.kubernetes.io/name=<service>`. Compose containers are named
`otterworks-<service>`. In the commands below, `$PROM`, `$AM` and `$JAEGER` are the URLs from
the table: on Compose `export PROM=http://localhost:9090 AM=http://localhost:9093 JAEGER=http://localhost:16686`;
on the cluster, with the port-forwards above, `export PROM=http://localhost:19090 AM=http://localhost:19093 JAEGER=https://jaeger.otterworks.app`.
