# Runbook: SQSQueueDepthHigh / SQSQueueDepthCritical / SQSDLQNotEmpty

**Severity:** warning (> 1000) / critical (> 5000) · **Rule file:** `observability/prometheus/alerts.yml` (group `otterworks.aws.sqs`)

> **Does this page?** Not on its own. The rule has no `page` label, so
> Alertmanager (`observability/alertmanager/alertmanager.yml.tmpl`) sends it to
> the default `sink` receiver only. Only `page: devin` rules
> (`observability/prometheus/incident_alerts.yml`) reach the Devin webhook and
> `#otterworks-alerts`. If you are looking at this at night, either someone
> forwarded it or a paging alert on the same service fired alongside it. Check
> both.

## What it means

An SQS queue (`queue_name` label) has more than 1000 visible messages
(`SQSQueueDepthCritical`: more than 5000) for 5 minutes. Consumers are not
keeping up, or not consuming at all. Because consumers are behind, users see
stale effects: notifications arrive late or never
(`otterworks-notifications` → notification-service), search results miss new
documents (`otterworks-search-events` → search-service), and the audit trail
lags (`otterworks-audit-events-queue` → audit-service).

**Data source.** `aws_sqs_*` metrics come from a CloudWatch exporter. Neither
the Compose stack nor the tenant charts deploy one, and SNS/SQS eventing is
disabled for tenants (`AGENTS.md`). So the alert **cannot fire** without that
exporter. Do not take silence as proof the queues are healthy: query SQS
directly (step 1).

## Threshold and why

`aws_sqs_approximate_number_of_messages_visible > 1000` for `5m`. The critical
level is `> 5000` for `2m`. Normal depth on these queues is near zero, so a
backlog of 1000 that lasts 5 minutes means consumers have stopped or are much
slower than producers. It is not a burst. At 5000 the lag is long enough that
users notice.

## First three things to check

1. **Is the backlog growing or draining?**
   ```bash
   # Compose (LocalStack)
   for q in otterworks-notifications otterworks-search-events otterworks-audit-events-queue; do
     aws --endpoint-url http://localhost:4566 sqs get-queue-attributes \
       --queue-url http://localhost:4566/000000000000/$q \
       --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
       --query "Attributes" --output text | sed "s/^/$q /"
   done
   # AWS: same command without --endpoint-url, with the real queue URL
   ```
   Run it twice a minute apart. A high `NotVisible` count means consumers
   receive messages but never delete them: they fail and the messages come back
   after the visibility timeout. Grafana **OtterWorks Infrastructure** → *SQS
   Queue Depth*.
2. **Is the consumer up and erroring?**
   ```bash
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=up{job=~"notification-service|search-service|audit-service"}' | jq -r '.data.result[] | "\(.metric.job // .metric.instance // .metric.queue_name // .metric.table_name) \(.value[1])"'
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=rate(notifications_processing_errors_total[5m])' | jq -r '.data.result[] | "\(.metric.job // .metric.instance // .metric.queue_name // .metric.table_name) \(.value[1])"'
   docker logs --since 10m otterworks-notification-service 2>&1 | grep -Ei 'deseriali|error|exception' | tail -20
   ```
   The Grafana alert `NotificationConsumerProcessingErrors` covers the same
   symptom from the consumer's side. Its runbook is
   [notification-processing-failure](notification-processing-failure.md).
3. **Is a chaos flag making the consumer reject messages?**
   ```bash
   docker exec otterworks-redis redis-cli EXISTS chaos:notification-service:consumer_strict_schema
   ```
   If it is set, every legacy-format message fails to parse and re-enters the
   queue. Clear it only if you own the demo.

`SQSDLQNotEmpty` (any `*-dlq` queue > 0 for 1 m) means messages have already
failed `maxReceiveCount` times. Read a few with
`aws sqs receive-message --queue-url <dlq-url> --max-number-of-messages 5`
before you redrive them, so you know which bad payload you would be replaying.

## Mitigate

- Fix or roll back the consumer first. Scaling up a consumer that fails every
  message only fails them faster.
- Once it is healthy, scale it out to drain the backlog faster:
  `kubectl -n otterworks-<tenant> scale deploy/<consumer> --replicas=2`.
- Do not purge a queue to clear the alert. Purging loses user notifications
  and audit events permanently.

## How to tell it is fixed

- `ApproximateNumberOfMessages` falls each minute and settles below 100.
  `NotVisible` returns to near zero.
- The consumer's error rate is zero, and the alerts have resolved.

## Escalate when

- `SQSQueueDepthCritical` fires, or the backlog keeps growing 15 minutes after
  the consumer is healthy.
- The audit queue is backing up. Audit events are compliance data, so tell the
  service owner even if it drains on its own.
- You would need to purge or redrive a DLQ. Get the owner's agreement first.

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
