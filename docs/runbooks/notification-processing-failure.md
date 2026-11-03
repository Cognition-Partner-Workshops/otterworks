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
2. Look at the failing message bodies in the log lines (`Failed to parse SQS message <id>`,
   `Discarding unparseable SQS message <id> ... : <body>`) and compare them with
   `SqsNotificationMessage` in `services/notification-service/.../model/NotificationEvent.kt`.
   A legacy producer that sends `timestamp` as a Unix epoch number is expected and handled by
   `FlexibleTimestampSerializer`; anything else is a producer contract change.
3. Check queue depth and the dead-letter queue:
   ```
   aws sqs get-queue-attributes --queue-url "$SQS_QUEUE_URL" \
     --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible RedrivePolicy
   ```
   If `RedrivePolicy` is empty the queue has no DLQ; the consumer then drops a message it cannot
   parse once it has been received more than `SQS_MAX_RECEIVE_COUNT` (default 3) times and
   increments `notifications_processing_discarded_total`.

## Resolution Steps

1. Parse failures (`Failed to parse SQS message`): the producer is sending a shape the consumer
   does not accept. Fix or extend the consumer model (`SqsNotificationMessage`) rather than the
   parser settings; the consumer must keep ignoring unknown fields and accepting both timestamp
   formats. Messages that already reached the DLQ can be redriven once the fix is deployed.
2. Processing failures (`Error processing SQS message ...; leaving it for redelivery`): a
   downstream dependency (DynamoDB, SES) is failing. Messages are retried automatically after
   the visibility timeout; fix the dependency and the backlog drains on its own.
3. Confirm recovery: `rate(notifications_processing_errors_total[2m])` returns to zero and
   `ApproximateNumberOfMessages` on the queue falls.

## Post-Incident

- Record which producer emitted the rejected shape and whether its contract changed.
- If messages were discarded (`notifications_processing_discarded_total` > 0), recover them from
  the error log lines, which include the message body, and replay them if they matter.
