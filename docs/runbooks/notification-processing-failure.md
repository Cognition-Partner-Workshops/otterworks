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

3. Check the queue is accumulating messages rather than draining:
   ```
   aws sqs get-queue-attributes --queue-url "$SQS_QUEUE_URL" \
     --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
   ```
4. Peek at a stuck message without consuming it (`--visibility-timeout 0`) and look at the
   `timestamp` field. Legacy producers emit a Unix epoch integer (`"timestamp": 1704067200`)
   while current producers emit an RFC 3339 string (`"timestamp": "2024-01-01T00:00:00Z"`).
   Messages may also carry fields the consumer does not model (`name`, `mimeType`,
   `sizeBytes`, ...).

## Root Cause

`SqsConsumer.parseMessage` could switch to a strict `kotlinx.serialization` `Json`
(`isLenient = false`, `ignoreUnknownKeys = false`) at runtime. In strict mode an
epoch-integer `timestamp` cannot be bound to the `String` field on
`SqsNotificationMessage`, and any unmodelled field is an error. Parsing returned `null`,
the `notifications.processing.errors` counter incremented, and because the message was
never deleted it re-entered the queue after the visibility timeout. Every poll re-failed
the same messages, so the error rate stayed up and queue depth grew.

## Resolution Steps

1. Deploy a notification-service build that contains the schema fix:
   - the consumer always uses the lenient parser (`ignoreUnknownKeys = true`), and
   - `SqsNotificationMessage.timestamp` is decoded by `FlexibleTimestampSerializer`, which
     accepts an RFC 3339 string, epoch seconds or epoch milliseconds (as a number or a
     numeric string) and normalises them to an ISO-8601 UTC string.
2. Confirm the error rate drops to zero on the Chaos Scenarios dashboard
   (`rate(notifications_processing_errors_total{job="notification-service"}[2m])`) and that
   `ApproximateNumberOfMessages` on the queue starts falling.
3. If messages already reached the dead-letter queue (`otterworks-notifications-dlq-*`,
   `maxReceiveCount = 3`), redrive them once the fixed build is running:
   ```
   aws sqs start-message-move-task --source-arn "$DLQ_ARN" --destination-arn "$QUEUE_ARN"
   ```
4. If the chaos flag was set, it expires on its own (10 minute TTL); it can be cleared early
   with `redis-cli DEL chaos:notification-service:consumer_strict_schema`.

## Post-Incident

- Unit tests in `SqsConsumerTest` and `FlexibleTimestampSerializerTest` cover epoch-second,
  epoch-millisecond, numeric-string and SNS-wrapped legacy payloads so the regression cannot
  return unnoticed.
- Producers should converge on RFC 3339 strings; track the remaining epoch-emitting
  publishers and retire the epoch path once none are left.
- Consider alerting on `ApproximateAgeOfOldestMessage` for the notifications queue as an
  early signal of a stuck consumer, independent of the error counter.
