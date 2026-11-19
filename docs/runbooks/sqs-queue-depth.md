# SQS backlog or dead-letter messages

## Signal
SQSQueueDepthHigh / SQSQueueDepthCritical / SQSDLQNotEmpty require an AWS metrics exporter; no such exporter is installed by this baseline.

## Triage
Check queue identity/tenant, oldest message age, arrival/deletion rate, consumer health, retry count and downstream throttling. Inspect a redacted failed message, never publish its payload in incident notes.

## Mitigation
Restore the consumer/downstream dependency first. Scale only within quotas and with owner approval. Redrive a small reviewed sample after checking idempotency; do not purge queues or mass-redrive blindly.

## Verify / escalate
Backlog and oldest-message age decline, deletion rate catches up and no new DLQ messages appear. Escalate to the service/platform owner if the cause is unknown, data durability is at risk or shared infrastructure needs modification.
