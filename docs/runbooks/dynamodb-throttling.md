# Runbook: DynamoDBThrottling / DynamoDBHighLatency / DynamoDBSystemErrors

**Severity:** warning (throttling, latency) / critical (system errors) · **Rule file:** `observability/prometheus/alerts.yml` (group `otterworks.aws.dynamodb`)

> **Does this page?** Not on its own. The rule has no `page` label, so
> Alertmanager (`observability/alertmanager/alertmanager.yml.tmpl`) sends it to
> the default `sink` receiver only. Only `page: devin` rules
> (`observability/prometheus/incident_alerts.yml`) reach the Devin webhook and
> `#otterworks-alerts`. If you are looking at this at night, either someone
> forwarded it or a paging alert on the same service fired alongside it. Check
> both.

## What it means

DynamoDB is rejecting requests to one table (`table_name`) with
`ProvisionedThroughputExceededException` or `ThrottlingException`. Throttled
reads and writes come back to the calling service, which either retries
(slower responses) or returns 5xx. In OtterWorks the main caller is
file-service (file metadata, folders, versions, sharing). notification-service
and audit-service also use DynamoDB. Users see slow or failed file listings and
uploads.

**Data source.** `aws_dynamodb_*` metrics come from a CloudWatch exporter,
which is not deployed by the Compose stack or the tenant charts, so the alert
**cannot fire** without it. Tenants share the physical tables with logical
owner prefixes (Tier A, `AGENTS.md`). One tenant's load can therefore throttle
everyone's.

## Threshold and why

`sum by (table_name)(rate(aws_dynamodb_throttled_requests_total[5m])) > 0` for
`2m`. Any sustained throttling counts: a healthy table should throttle nothing,
and two minutes rules out a single burst that the SDK retries absorbed.
`DynamoDBHighLatency` (> 50 ms average on `GetItem|PutItem|Query` for `5m`)
and `DynamoDBSystemErrors` (any 5xx from DynamoDB for `2m`) are its
companions. Single-digit milliseconds is normal for those operations, and
system errors are on AWS's side, not ours.

## First three things to check

1. **Which table and which operation, and is it reads or writes?**
   ```bash
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=sum by (table_name, operation) (rate(aws_dynamodb_throttled_requests_total[5m]))' | jq -r '.data.result[] | "\(.metric.job // .metric.instance // .metric.queue_name // .metric.table_name) \(.value[1])"'
   aws cloudwatch get-metric-statistics --namespace AWS/DynamoDB --metric-name ThrottledRequests \
     --dimensions Name=TableName,Value=<table> Name=Operation,Value=<op> \
     --start-time $(date -u -d '-30 min' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 60 --statistics Sum
   ```
   Grafana **OtterWorks Infrastructure** → *DynamoDB Consumed Capacity*.
2. **What capacity mode is the table in, and what changed?**
   ```bash
   aws dynamodb describe-table --table-name <table> \
     --query 'Table.{mode:BillingModeSummary.BillingMode,rcu:ProvisionedThroughput.ReadCapacityUnits,wcu:ProvisionedThroughput.WriteCapacityUnits,gsi:GlobalSecondaryIndexes[].IndexName}'
   ```
   Provisioned and at its limit means a capacity problem. On-demand and still
   throttling usually means a hot partition (one key taking most of the
   traffic) or a throttled GSI.
3. **Which caller is generating the load?**
   ```bash
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=topk(5, sum by (job, handler) (rate(http_requests_total{job=~"file-service|notification-service|audit-service"}[5m])))' | jq -r '.data.result[] | "\(.metric.job // .metric.instance // .metric.queue_name // .metric.table_name) \(.value[1])"'
   docker logs --since 10m otterworks-file-service 2>&1 | grep -Ei 'throttl|ProvisionedThroughput' | tail -20
   ```
   One handler with a sudden jump in rate, such as a bulk import, a retry
   storm or a scan in a loop, is usually the cause.

## Mitigate

- Stop or slow the job or tenant causing the load, if you can identify one.
- Raise capacity on a provisioned table:
  `aws dynamodb update-table --table-name <table> --provisioned-throughput ReadCapacityUnits=<r>,WriteCapacityUnits=<w>`
  (or switch to `--billing-mode PAY_PER_REQUEST`). These tables are
  Terraform-managed (`infrastructure/terraform/modules/database`), so record
  the change and put it in Terraform the next day. Otherwise the next
  `terraform apply` reverts it.

## How to tell it is fixed

- The throttled-request rate is 0 for 10 minutes, and average latency is back
  under 20 ms.
- The calling service's 5xx rate and P99 are back to normal
  ([high-error-rate](high-error-rate.md), [high-latency](high-latency.md)),
  and the alerts have resolved.

## Escalate when

- `DynamoDBSystemErrors` fires. That is AWS-side: check the AWS Health
  Dashboard and open a support case.
- Throttling continues after a capacity increase (a hot key or design issue,
  so hand it to the file-service owner).
- You would need a capacity change on a shared production table at night. Get
  the platform owner's approval first; it affects every tenant.

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
