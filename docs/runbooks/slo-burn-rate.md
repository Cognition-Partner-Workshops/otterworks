# SLO error-budget burn

## Signal
`SLOBurnRateHigh` identifies a service, namespace and SLO. Objectives roll over 30 days:
99.5% availability; 95% of measured requests/operations complete within 500 ms.
Page when **both** 1h/5m windows exceed 14.4x budget burn, or 6h/30m exceed 6x.
Ticket when both 1d/2h exceed 3x, or 3d/6h exceed 1x. These are rate-based
multi-window gates, not independent single-window alarms. No extra `for` delay.

## Triage
1. Open the SLO overview dashboard, filter service and namespace. Compare both
   burn windows, success ratio, request volume, error-budget remaining and recent deploys.
2. Availability excludes 5xx only (4xx counts as served); inspect the selectors
   and source references in `observability/slo/slos.yaml`. Collab availability
   measures persistence success, **not** all WebSocket interactions. Its latency
   covers completed document syncs; missing/failed syncs are not timed.
3. Check Prometheus target/rule health before treating missing series as recovery.
   Zero traffic produces no SLI, not 100% success. Low traffic can produce noisy
   burn; use the paired windows and raw counts rather than changing objectives mid-incident.
4. Follow errors, saturation and traces to the affected dependency. Scope to the
   namespace: do not mitigate an isolated demo by changing shared infrastructure.

## Mitigation and escalation
Restore a failed dependency or roll back a recent regression through the normal
tenant deployment process. For deliberately planted incidents follow
`incident/README.md`; do not fix golden main, silence alerts or lower objectives.
Pages use the existing `page: devin` routing model; tickets go to Slack for human
triage (no ticket-system integration is installed). Preserve a timeline and contact
the service owner for persistent burn or the platform owner for shared failures.

## Verify
Both paired burn windows must recover, along with raw success/latency and target
health. Remaining budget is `1 - error_ratio_30d / (1 - objective)`; negative means
overspent. The 30d ratio is traffic-weighted from raw counters, not an average of
5m ratios. A new Prometheus has only partial history until 30 days have elapsed;
retain at least 35 days and provision durable storage before relying on this for
release decisions. Process downtime without requests is covered separately by
ServiceDown, not counted as served-request failures.
