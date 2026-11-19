# High CPU

## Signal
HighCPUUsage measures process CPU seconds per second; confirm core-count interpretation before acting.

## Triage
Compare process CPU, request rate, latency, pod CPU throttling and recent changes. Capture a short low-overhead profile if safe, scoped to the affected tenant.

## Mitigation
Roll back a regression or reduce avoidable work. Change replicas/limits only within tenant quota and normal deployment review; leave planted demo faults intact.

## Verify / escalate
CPU and throttling stabilize, latency/error rates recover for 15 minutes. Escalate to the service/platform owner if the cause is unknown, data durability is at risk or shared infrastructure needs modification.
