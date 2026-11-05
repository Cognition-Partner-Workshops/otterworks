# Runbook: HighLatencyP99 / HighLatencyP95

**Severity:** critical (P99) / warning (P95) · **Rule file:** `observability/prometheus/alerts.yml` (group `otterworks.http.latency`)

> **Does this page?** Not on its own. The rule has no `page` label, so
> Alertmanager (`observability/alertmanager/alertmanager.yml.tmpl`) sends it to
> the default `sink` receiver only. Only `page: devin` rules
> (`observability/prometheus/incident_alerts.yml`) reach the Devin webhook and
> `#otterworks-alerts`. If you are looking at this at night, either someone
> forwarded it or a paging alert on the same service fired alongside it. Check
> both.

The document list has its own paging version, `DocumentListLatencyHigh` (p95
of `GET /api/v1/documents/` > 1 s for `1m`, `page: devin`). Its runbook is
[`incident/README.md#n-plus-one`](../../incident/README.md#n-plus-one).

## What it means

The slowest 1 % of requests (P99) on one service took longer than 2 s, measured
across all of that service's endpoints, for 5 minutes straight. `HighLatencyP95`
is the earlier warning: the slowest 5 % took longer than 1 s. Users see slow
spinners. The gateway starts returning 504s once its upstream timeout runs out.

## Threshold and why

- P99: `histogram_quantile(0.99, sum by (job, le)(rate(http_request_duration_seconds_bucket[5m]))) > 2` for `5m`.
- P95: the same expression at `0.95` and `> 1`, for `5m`.

Interactive pages should come back well under a second. Above 2 s at P99,
enough requests are slow that users notice. `for: 5m` on a 5-minute window
ignores a single slow export or a cold cache after a restart. The rule
aggregates every handler, so one slow endpoint (an export) can fire it while
everything else is fine. Step 1 separates the two cases.

## First three things to check

1. **Which service, which endpoint, and did traffic change?**
   ```bash
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=histogram_quantile(0.99, sum by (job, le) (rate(http_request_duration_seconds_bucket[5m])))' | jq -r '.data.result[] | "\(.metric | to_entries | map("\(.key)=\(.value)") | join(" ")) \(.value[1])"'
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=histogram_quantile(0.99, sum by (handler, le) (rate(http_request_duration_seconds_bucket{job="<service>"}[5m])))' | jq -r '.data.result[] | "\(.metric | to_entries | map("\(.key)=\(.value)") | join(" ")) \(.value[1])"'
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=sum by (job) (rate(http_requests_total[5m]))' | jq -r '.data.result[] | "\(.metric | to_entries | map("\(.key)=\(.value)") | join(" ")) \(.value[1])"'
   ```
   Grafana **OtterWorks Overview** → *Latency P99 by Service* and *Request Rate
   by Service*. Latency rising with flat traffic points to code or a
   dependency. Latency rising with traffic points to capacity.
2. **Where does a slow request spend its time?** In Jaeger, search
   `service=<service>` with `minDuration=2s`, open the slowest trace and find
   the widest child span. Many identical `SELECT` spans mean N+1 queries. One
   long DB span means a missing index or a lock. A long span on an HTTP call
   to another service means you need that service's latency next.
3. **Is it saturation or injected delay?**
   ```bash
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=rate(process_cpu_seconds_total{job="<service>"}[5m])' | jq -r '.data.result[] | "\(.metric | to_entries | map("\(.key)=\(.value)") | join(" ")) \(.value[1])"'
   docker exec otterworks-redis redis-cli --scan --pattern 'chaos:*'   # e.g. chaos:document-service:slow_queries
   docker stats --no-stream | grep otterworks-                         # Compose
   kubectl -n otterworks-<tenant> top pods                             # EKS
   ```
   CPU near the container limit means scale out or find the hot loop. A slow
   chaos key means the latency was injected on purpose. Check with the person
   running the demo before you clear it.

## Mitigate

- Scale out if it is load: `kubectl -n otterworks-<tenant> scale deploy/<service> --replicas=2`.
  Never do this for document-service on the incident stack, where a second
  replica triggers the planted `double-run` flaw.
- Roll back if a deploy matches when the latency started.

## How to tell it is fixed

- P99 from step 1 is below 1 s (P95 below 0.5 s) for 10 minutes at normal
  traffic, and both alerts have resolved.
- The slowest trace in Jaeger over the last 15 minutes no longer shows the
  span you found in step 2.

## Escalate when

- P99 is above 5 s or the gateway returns 504s (`HighErrorRate` on
  `api-gateway` fires as well).
- It lasts 30 minutes and you have no cause from step 2.
- The cause is the shared RDS instance or the cluster nodes. Those are platform
  concerns, shared by every tenant.

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
