# High process memory

## Signal
HighMemoryUsage / HighMemoryUsageCritical compare RSS against machine memory. First verify both series share labels; container limits differ from host RAM.

## Triage
Inspect RSS trend, container memory limit, OOMKilled events and recent deploys. Compare heap/cache growth against traffic; capture a bounded heap/profile only in an isolated tenant.

## Mitigation
Roll back a recent regression or reduce load/cache pressure in the affected tenant with owner approval. Do not repeatedly restart without preserving evidence; never change the planted golden-app flaws.

## Verify / escalate
RSS stabilizes below the threshold, restarts stop and error/latency rates recover for at least 15 minutes. Escalate to the service/platform owner if the cause is unknown, data durability is at risk or shared infrastructure needs modification.
