# Runbook: HighErrorRate

**Severity:** critical · **Rule file:** `observability/prometheus/alerts.yml` (group `otterworks.http.errors`)

> **Does this page?** Not on its own. The rule has no `page` label, so
> Alertmanager (`observability/alertmanager/alertmanager.yml.tmpl`) sends it to
> the default `sink` receiver only. Only `page: devin` rules
> (`observability/prometheus/incident_alerts.yml`) reach the Devin webhook and
> `#otterworks-alerts`. If you are looking at this at night, either someone
> forwarded it or a paging alert on the same service fired alongside it. Check
> both.

The document-service has its own paging version of this alert,
`DocumentServiceErrorRateHigh` (5 % for `1m`, `page: devin`). Its runbook is
[`incident/README.md`](../../incident/README.md). Most often the cause there is
the request-log volume filling up (`log-flood`).

## What it means

More than 5 % of the HTTP responses one service (`job`) returned over the last
5 minutes were 5xx, and it stayed that way for 2 minutes. Users see failed
saves, uploads or searches on that service's feature.

## Threshold and why

`sum by (job)(rate(http_requests_total{status=~"5.."}[5m])) / sum by (job)(rate(http_requests_total[5m])) > 0.05`
for `2m`. One request in twenty failing is clearly broken, and a single
retried call does not reach it. The 5-minute rate window plus `for: 2m` keeps a
short burst during a deploy from firing it. On a service with very little
traffic, a handful of errors can cross 5 %. Check the absolute rate (step 1)
before treating it as an outage.

## First three things to check

1. **Which service, how many requests, which endpoint and which status code?**
   ```bash
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=sum by (job) (rate(http_requests_total{status=~"5.."}[5m])) / sum by (job) (rate(http_requests_total[5m]))' | jq -r '.data.result[] | "\(.metric.job // .metric.instance // .metric.queue_name // .metric.table_name) \(.value[1])"'
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=sum by (handler, status) (rate(http_requests_total{job="<service>", status=~"5.."}[5m]))' | jq -r '.data.result[] | "\(.metric.job // .metric.instance // .metric.queue_name // .metric.table_name) \(.value[1])"'
   ```
   Grafana **OtterWorks Overview** → *Error Rate by Service*. Then
   **OtterWorks Service Detail** (`/d/otterworks-service-detail`) with
   `service=<service>`. One handler failing points to a code path. Every
   handler failing points to a dependency.
2. **Is a chaos flag or a planted scenario armed?** Most 5xx spikes on demo
   stacks come from these. Read them before you touch any code:
   ```bash
   docker exec otterworks-redis redis-cli --scan --pattern 'chaos:*'          # Compose
   kubectl -n otterworks-<tenant> exec deploy/redis -- redis-cli --scan --pattern 'chaos:*'
   ```
   Clear a flag with `scripts/inject-bug.sh <tenant> reset` (tenants) or
   `make disarm` (local incident stack). Do this only if you or the demo owner
   armed it. Do not clear another person's demo.
3. **What do the failing requests say?**
   ```bash
   docker logs --since 10m otterworks-<service> 2>&1 | grep -Ei 'error|exception|traceback' | tail -30
   kubectl -n otterworks-<tenant> logs -l app.kubernetes.io/name=<service> --since=10m | grep -Ei 'error|exception' | tail -30
   ```
   Jaeger: `$JAEGER/search?service=<service>&tags=%7B%22error%22%3A%22true%22%7D`.
   The span that failed names the downstream call (Postgres, Redis, S3,
   DynamoDB or another service).

## Mitigate

- A recent deploy matches the start of the errors: roll back
  (`kubectl -n otterworks-<tenant> rollout undo deploy/<service>`).
- The cause is a dependency: follow that dependency's alert or runbook
  ([service-down](service-down.md), [dynamodb-throttling](dynamodb-throttling.md),
  [sqs-queue-depth](sqs-queue-depth.md)).

## How to tell it is fixed

- The error ratio from step 1 is below 1 % for 10 minutes, and request volume
  is back to normal. A ratio that falls because traffic stopped is not a fix.
- The alert has resolved in Alertmanager.

## Escalate when

- The ratio stays above 5 % for 15 minutes after a rollback, or above 50 % at
  any point.
- The service is `auth-service`, `api-gateway` or `file-service` and users
  cannot log in or upload.
- The logs show data errors (constraint violations, corrupt rows) and not just
  timeouts.

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
