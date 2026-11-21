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

3. Confirm the error rate and its shape on the `notifications_processing_errors_total`
   and `notifications_messages_malformed_total` counters (`/metrics` on port 8086).
   Malformed-message errors are deterministic and never succeed on retry; errors
   without a malformed count are downstream (DynamoDB / SES / WebSocket) and do retry.
4. Inspect a failing body. The consumer logs `Malformed SQS message <id>; removing from
   queue. body=...`. Historically the mismatch was `"timestamp": 1704067200` (Unix
   epoch integer, emitted by legacy publishers) against a consumer that only accepted
   RFC 3339 strings.
5. Check queue depth and the dead-letter queue (`ApproximateNumberOfMessagesVisible`
   on `otterworks-notifications` and `otterworks-notifications-dlq`).

## Resolution Steps

- If the chaos flag is set, clear it (`redis-cli DEL chaos:notification-service:consumer_strict_schema`
  or `DELETE /api/v1/admin/chaos`); it also expires on its own after 10 minutes.
- The consumer (`services/notification-service/.../consumer/SqsConsumer.kt`) now uses a
  single tolerant parser: unknown fields are ignored and `timestamp` accepts either an
  RFC 3339 string or an epoch number (seconds or milliseconds), normalised to RFC 3339
  by `EventTimestampSerializer`. A body that still cannot be parsed is counted, logged
  with its body and deleted so it cannot re-enter the queue after the visibility timeout.
- Messages that failed while the strict parser was active were redelivered, not lost;
  once a fixed build is running they drain on their own. Anything that reached the DLQ
  can be redriven back to the main queue (`aws sqs start-message-move-task`).
- If a new publisher introduces another encoding, extend `EventTimestampSerializer` and
  add a case to `SqsConsumerTest` rather than tightening the parser.

## Post-Incident

- Confirm `NotificationConsumerProcessingErrors` resolved and queue depth returned to ~0.
- Verify end-to-end delivery by sharing a file and checking the recipient's in-app
  notifications.
- If the legacy epoch publisher can be identified, schedule it to move to RFC 3339 so
  the queue carries one timestamp encoding; the consumer keeps accepting both meanwhile.
