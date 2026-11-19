# Collaboration saturation or sync delay

## Signal
WebSocketConnectionsHigh / CRDTSyncDelayHigh indicate saturation or slow synchronization. The legacy CRDT alert metric may not match current document-sync instrumentation; verify the queried series exists.

## Triage
Compare active connections/rooms, completed document sync latency, persistence errors and Redis health. Check disconnect/reconnect storms and client versions; avoid logging document bodies.

## Mitigation
Restore Redis or roll back a recent regression, rate-limit a reconnect storm if authorized, and scale only within quota. Preserve unpersisted document state before restarting.

## Verify / escalate
Connection count stabilizes, sync latency and persistence errors recover and a test client can edit/reconnect without losing state. Escalate to the service/platform owner if the cause is unknown, data durability is at risk or shared infrastructure needs modification.
