# Runbook: Notification Processing Failures

**Severity:** Critical

## Alert

`NotificationConsumerProcessingErrors` -- fires when the notification-service SQS consumer is generating sustained processing errors (`rate(notifications_processing_errors_total[2m]) > 0` for 2 minutes).

## Symptoms

- Users stop receiving notifications (email, in-app) for shared files and document updates.
- The Chaos Scenarios dashboard shows non-zero processing error rate on the notification-service panel.
- SQS queue depth (`ApproximateNumberOfMessagesVisible`) grows while the consumer reports it is healthy.

## Investigation Steps

1. Check notification-service consumer logs for deserialization errors:
   ```
   kubectl logs -l app=notification-service --tail=100 -n otterworks | grep -i "parse\|deseriali\|timestamp\|dead-letter"
   ```
   `Failed to parse message body as an event (...)` names the field that did not match the schema.
2. Compare the error counter with the dead-letter counter on `/metrics`:
   - `notifications_processing_errors_total` rising **and** `notifications_messages_deadlettered_total` rising at the same rate: poison messages are being removed from the queue as designed; find the producer sending them (step 3).
   - `notifications_processing_errors_total` rising with the queue depth also rising: messages are being redelivered. Check whether the consumer can reach SQS (`Error processing SQS message`) or whether downstream processing (DynamoDB, SES) is failing -- those messages are intentionally left for retry.
3. Identify the producer. Peek at a message without consuming it (the `sourceQueueUrl` / `sourceMessageId` attributes are set on dead-lettered copies):
   ```
   aws sqs receive-message --queue-url "$SQS_DLQ_URL" --max-number-of-messages 1 --message-attribute-names All --visibility-timeout 0
   ```
   Current producers (`file-service/src/events.rs`, `document-service/app/services/event_publisher.py`) send RFC 3339 `timestamp` strings; older producers send Unix epoch numbers. Both are accepted. Anything else (an object, a missing `eventType`) is a producer bug.

## Resolution Steps

1. The consumer accepts both timestamp formats (`model/EventTimestampSerializer.kt`) and ignores undeclared fields, so a schema difference between producers does not stop processing. If a new producer sends a shape the schema rejects, fix the producer or extend `SqsNotificationMessage`.
2. Messages that cannot be parsed are deleted from the source queue after one attempt. Set `SQS_DLQ_URL` on the deployment (`--set-string config.SQS_DLQ_URL=<dlq url>` for Helm) to keep a copy on the dead-letter queue instead of dropping it; the Terraform-managed queue also redrives after 3 receives.
3. If messages are redelivered because downstream processing fails, fix the dependency (DynamoDB table, SES identity) rather than the consumer; redelivery is the intended behaviour for transient failures.
4. Redrive dead-lettered messages once the cause is fixed:
   ```
   aws sqs start-message-move-task --source-arn <dlq arn> --destination-arn <queue arn>
   ```

## Post-Incident

- Confirm `notifications_processing_errors_total` is flat and the alert has resolved.
- Add a `SqsConsumerTest` case for any new message shape the incident exposed.
- If a producer was at fault, link its fix to the incident and update the `SqsNotificationMessage` contract comment in `model/NotificationEvent.kt` if the schema changed.
