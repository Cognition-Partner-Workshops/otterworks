# DynamoDB throttling, latency or errors

## Signal
DynamoDBThrottling / DynamoDBHighLatency / DynamoDBSystemErrors require AWS exporter telemetry. Missing metrics do not mean healthy.

## Triage
Check table/operation, AWS service health, consumed vs provisioned capacity, hot partitions and recent traffic/deploy changes. Separate client retries from DynamoDB system errors.

## Mitigation
Back off producers and restore bounded retries; revert a request amplification regression. Capacity/index changes require the owning infrastructure review; do not alter shared tables ad hoc.

## Verify / escalate
Throttles/system errors clear, request latency and consumer backlog return to baseline for 15 minutes. Escalate to the service/platform owner if the cause is unknown, data durability is at risk or shared infrastructure needs modification.
