# Runbook: LowDiskSpace / CriticalDiskSpace

**Severity:** warning (< 15 %) / critical (< 5 %) · **Rule file:** `observability/prometheus/alerts.yml` (group `otterworks.resources`)

> **Does this page?** Not on its own. The rule has no `page` label, so
> Alertmanager (`observability/alertmanager/alertmanager.yml.tmpl`) sends it to
> the default `sink` receiver only. Only `page: devin` rules
> (`observability/prometheus/incident_alerts.yml`) reach the Devin webhook and
> `#otterworks-alerts`. If you are looking at this at night, either someone
> forwarded it or a paging alert on the same service fired alongside it. Check
> both.

The document-service has its own paging version for its request-log volume,
`RequestLogVolumeNearFull` (`page: devin`). Its runbook is
[`incident/README.md#log-flood`](../../incident/README.md#log-flood). That
alert is about one tmpfs volume, not the node's root disk.

## What it means

A node's root filesystem (`mountpoint="/"`) has less than 15 % free
(`CriticalDiskSpace`: less than 5 %). When it fills, the container runtime
cannot write logs or pull images. The kubelet starts evicting pods
(`DiskPressure`), and services that write to local disk start failing.

**Data source.** `node_filesystem_*` comes from node-exporter. The Compose
stack does not run node-exporter, so locally the expression returns nothing and
the alert **cannot fire**. Check the host with `df -h` yourself. On EKS,
node-exporter runs in namespace `monitoring`, and `instance` is the node
exporter's address.

## Threshold and why

`node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} < 0.15`
for `5m`. The critical level is `< 0.05` for `2m`. The kubelet's default
hard-eviction threshold for `nodefs.available` is 10 %, so 15 % warns before
evictions start. 5 % means evictions have already started or are about to.

## First three things to check

1. **Which node, and how fast is it filling?**
   ```bash
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}' | jq -r '.data.result[] | "\(.metric.job // .metric.instance // .metric.queue_name // .metric.table_name) \(.value[1])"'
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[1h], 4*3600) < 0' | jq -r '.data.result[] | "\(.metric.job // .metric.instance // .metric.queue_name // .metric.table_name) \(.value[1])"'
   ```
   Grafana **OtterWorks Infrastructure** → *Node Disk Usage*. A node that
   `predict_linear` says hits zero within 4 hours is urgent even at 14 % free.
2. **Is the kubelet evicting yet?**
   ```bash
   kubectl describe node <node> | grep -A6 Conditions | grep -i DiskPressure
   kubectl get events -A --field-selector reason=Evicted --sort-by=.lastTimestamp | tail -20
   ```
3. **What is using the space?**
   ```bash
   # EKS: debug pod on the node, then inspect the host filesystem
   kubectl debug node/<node> -it --image=busybox -- sh -c 'du -xh -d2 /host/var/lib /host/var/log 2>/dev/null | sort -h | tail -15'
   # Compose host
   df -h / && docker system df && sudo du -xh -d1 /var/lib/docker 2>/dev/null | sort -h | tail
   ```
   Typical causes: container logs from a service logging every request (look
   for one huge `*-json.log` under `/var/lib/docker/containers` or
   `/var/log/pods`), unused images after many deploys, and `emptyDir` volumes.

## Mitigate

- Remove unused images: `docker image prune -af` (Compose host), or
  `crictl rmi --prune` on an EKS node via `kubectl debug`.
- If one pod is writing a flood of logs, restart it and fix the logging. Do
  not delete live log files under a running container.
- EKS: cordon and drain the node if it cannot be cleaned
  (`kubectl cordon <node>`, `kubectl drain <node> --ignore-daemonsets --delete-emptydir-data`).
  The SPOT node group replaces it.

## How to tell it is fixed

- More than 20 % free on `/`, and `predict_linear` over 1 hour no longer
  predicts zero within 24 hours.
- The node has no `DiskPressure` condition, no new `Evicted` events, and both
  alerts have resolved.

## Escalate when

- `CriticalDiskSpace` fires, or pods are already being evicted.
- More than one node is low at the same time, or the disk refills within an
  hour of cleanup.
- The disk is on a stateful host (a database). Do not delete anything there
  yourself.

**Where to run the commands**

| | Local Compose stack | Shared EKS cluster (`otterworks-dev`) |
|---|---|---|
| Prometheus | `http://localhost:9090` | `kubectl -n monitoring port-forward svc/prometheus-prometheus 19090:9090` |
| Grafana | `http://localhost:3001` (`admin` / `otterworks`) | `https://grafana.otterworks.app` |
| Alertmanager | `http://localhost:9093` | `kubectl -n monitoring port-forward svc/prometheus-alertmanager 19093:9093` |
| Jaeger | `http://localhost:16686` | `https://jaeger.otterworks.app` |
| Workloads | `docker compose -f docker-compose.yml -f docker-compose.infra.yml ps` | `kubectl -n otterworks-<tenant> get pods` (`otterworks-main` for t-main) |

Pods carry `app.kubernetes.io/name=<service>`. Compose containers are named
`otterworks-<service>`. In the commands below, `$PROM` is whichever Prometheus
URL applies (`export PROM=http://localhost:9090`).
