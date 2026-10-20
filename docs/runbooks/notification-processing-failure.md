# Runbook: Notification Processing Failures

**Severity:** Critical

## Alert

`NotificationConsumerProcessingErrors` -- fires when the notification-service SQS consumer is generating sustained processing errors.

## Symptoms

- Users stop receiving notifications (email, in-app) for shared files and document updates.
- The Chaos Scenarios dashboard shows non-zero processing error rate on the notification-service panel.
- SQS queue depth grows unboundedly as failed messages re-enter after visibility timeout.

## Investigation Steps

1. Check notification-service consumer logs for deserialization errors:
   ```
   kubectl logs -l app=notification-service --tail=100 -n otterworks | grep -i "deseriali\|timestamp\|schema"
   ```
2. Check whether the chaos flag `chaos:notification-service:consumer_strict_schema` is set in Redis:
   ```
   redis-cli EXISTS chaos:notification-service:consumer_strict_schema
   ```

3. Check the queue: `ApproximateNumberOfMessagesNotVisible` climbing with
   `ApproximateNumberOfMessages` means the same messages are being received, failing and
   re-entering after the 60 s visibility timeout. Messages that fail three times land in
   `otterworks-notifications-dlq` (redrive policy `maxReceiveCount = 3`, set in
   `infrastructure/terraform/modules/messaging/main.tf` and mirrored for LocalStack in
   `scripts/localstack-init.sh`); inspect them there rather than from consumer logs, which
   carry only the SQS `messageId`.
4. Correlate the error rate with the `notifications_processing_errors_total` counter in
   Prometheus and with the deploy or chaos-injection time.

## Root Cause

`SqsNotificationMessage.timestamp` is declared as a `String`. Current producers send an
RFC 3339 string, but legacy producers send a Unix epoch integer (`"timestamp": 1704067200`).
The default lenient parser silently coerced the integer; the strict parser selected by the
`chaos:notification-service:consumer_strict_schema` flag rejects it with a
`SerializationException`, `parseMessage` returns `null`, and the message is left undeleted
on the queue. Without a redrive policy it re-enters after every visibility timeout, so the
error rate and queue depth grow without bound while the consumer process stays healthy.

## Resolution Steps

1. If the chaos flag is set, clear it (`scripts/inject-bug.sh <tenant> reset`, or
   `redis-cli DEL chaos:notification-service:consumer_strict_schema`). The error rate should
   drop within one poll interval.
2. Deploy a notification-service build that decodes `timestamp` with
   `EventTimestampSerializer` (RFC 3339 string or epoch seconds/milliseconds, normalised to
   ISO-8601 UTC) so the legacy format is handled explicitly rather than by lenient coercion.
3. Make sure the queue has a redrive policy to `otterworks-notifications-dlq`; a message
   that genuinely cannot be parsed must dead-letter after `maxReceiveCount` receives, not
   cycle forever.
4. Redrive the DLQ once the fixed build is running
   (`aws sqs start-message-move-task --source-arn <dlq-arn>`), then confirm
   `notifications_processing_errors_total` is flat and `ApproximateNumberOfMessages` returns
   to zero.

## Post-Incident

- Confirm the `NotificationConsumerProcessingErrors` alert resolved in Grafana and that
  the DLQ is empty after the redrive.
- Add a unit test for any new timestamp shape a producer emits
  (`SqsConsumerTest` covers RFC 3339, epoch seconds and epoch milliseconds).
- Track producers still emitting epoch integers and move them to RFC 3339 so the strict
  schema can eventually become the default.
