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
   kubectl logs -l app=notification-service --tail=100 -n otterworks | grep -i "deseriali\|timestamp\|schema\|unparseable"
   ```
2. Confirm the symptom on the metrics the alert is built from:
   ```
   sum(rate(notifications_processing_errors_total{job="notification-service"}[2m]))   # what pages
   sum(rate(notifications_poison_messages_total{job="notification-service"}[2m]))     # bodies that can never parse
   ```
   Processing errors with **no** poison messages means `NotificationService.processEvent` is
   failing (DynamoDB, SES, downstream service) and messages are being left for SQS to redeliver;
   processing errors **with** poison messages means a producer is publishing bodies the consumer
   cannot read at all.
3. Check the queue: `ApproximateNumberOfMessagesVisible` on the notifications queue and the depth
   of its dead-letter queue (`otterworks-notifications-dlq-<env>`). The main queue redrives to the
   DLQ after `maxReceiveCount = 3` (`infrastructure/terraform/modules/messaging/main.tf`).
4. Look at a failing body. The consumer logs the first 512 characters of every message it drops as
   unparseable, alongside its `messageId`. Compare the fields against `SqsNotificationMessage`
   (`services/notification-service/src/main/kotlin/com/otterworks/notification/model/NotificationEvent.kt`).
5. Check recent deploys of the *producers* (file-service, document-service, collab-service) as
   well as the consumer: a schema change on either side shows up here first.

## Resolution Steps

- **Schema mismatch (the May 2026 incident).** The consumer was switching to a strict
  `kotlinx.serialization` parser (`ignoreUnknownKeys = false`, `isLenient = false`) at runtime,
  which rejected the Unix-epoch integer `timestamp` that legacy producers emit (and any envelope
  carrying extra keys). Nothing deleted the rejected messages, so they re-entered after the
  60 s visibility timeout and the queue grew without bound. Fixed in notification-service by:
  - decoding `timestamp` with `FlexibleTimestampSerializer`, which accepts RFC 3339 strings and
    epoch seconds/milliseconds and normalises them to ISO-8601;
  - using a single tolerant parser — the schema a consumer accepts is never switched at runtime;
  - treating a body that fails to deserialise as a poison message: logged, counted in
    `notifications_poison_messages_total`, and deleted, because it would fail identically on
    every redelivery. Failures *after* parsing still leave the message for SQS to redeliver.
- **Downstream failure (`processEvent` throwing).** Fix or restore the dependency; the messages
  are still on the queue (or in the DLQ after three attempts) and will be processed once it is
  healthy. Redrive the DLQ into the main queue afterwards.
- **Producer regression.** Roll the producer back or forward; messages already dropped as
  poison are recoverable only from the producer's own records or logs.

## Post-Incident

- Add a unit test for any new producer payload shape to
  `services/notification-service/src/test/kotlin/com/otterworks/notification/consumer/SqsConsumerTest.kt`.
- Confirm `NotificationConsumerProcessingErrors` resolved in Grafana and that the DLQ is empty
  (or has been redriven).
- If a producer still emits epoch timestamps, open a ticket to move it to RFC 3339 so the legacy
  path can eventually be retired.
