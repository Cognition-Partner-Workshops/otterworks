# Low disk space

## Signal
LowDiskSpace / CriticalDiskSpace monitor the root filesystem; document request-log volume has its own incident runbook.

## Triage
Identify the affected node/mount and largest growth source using read-only filesystem and log-retention checks. Check whether telemetry exists: node-exporter is required.

## Mitigation
Rotate/archive approved logs or remove verified disposable data; never delete database files or evidence. Expand storage only through the owning infrastructure change process. For planted request-log faults follow incident/README.md.

## Verify / escalate
Free-space trend remains above 15%, writes succeed and user error rates recover. Escalate to the service/platform owner if the cause is unknown, data durability is at risk or shared infrastructure needs modification.
