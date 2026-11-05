# Local detection evidence

Captured on 2026-11-05 against the minimal Docker Compose stack, through
`http://localhost:8080`. These are exact copies of passing replay reports.
Each proves inactive Prometheus rules, drained Alertmanager state, before/after
counter snapshots, all three expected alerts firing, and fresh firing deliveries
to the security sink. Probe findings are intentionally not remediated.

| Class | Passing report (JSON and Markdown) | First observed firing |
|---|---|---|
| Identity forgery | `identity-forgery-20261105T131805108551Z.{json,md}` | All three: 40.2 seconds |
| Cross-customer access | `cross-customer-access-20261105T132443125630Z.{json,md}` | All three: 33.1 seconds |
| Credential stuffing | `credential-stuffing-20261105T133601795171Z.{json,md}` | All three: 47.9 seconds |

The corresponding `<class>-alerts.png` screenshots show the actual Prometheus
`/alerts` page with all three class rules firing. Captured through Chrome CDP at
`localhost:29229`. Unrelated `ServiceDown` alerts reflect deliberately absent
services in this minimal stack.

## Regression comparison and operational findings

`regression-comparison.{json,md}` records all 19 probe verdicts from an
`origin/demo-bank` service build versus the instrumented build, with source SHA,
image IDs and timestamps. All 19 match: nine secure, eight vulnerable, two
inconclusive. The two inconclusive probes require absent file/search services;
this is not proof of their security.

The first instrumented scan raced document-service startup and opened the
gateway circuit breaker. The comparison uses the subsequent health-ready scan;
`detect-up` now waits for service health. Both comparison scans exit nonzero
because the planted findings remain.

The first identity replay fired all rules but missed fresh deliveries after a
rapid refire, consistent with Alertmanager deduplicating the previous incident.
Alertmanager's before-state was not captured in that failed run, so that causal
link remains unverified. The replay now requires both systems to stay quiet for one group interval
(60 seconds); the quiet budget is 360 seconds. Attack thresholds and the
180-second firing/delivery budget are unchanged.

The first credential replay reused the DAST probe's fixed spoofed addresses
from the full scan, creating no new buckets (client counter stayed at 1506).
The passing run followed natural idle expiry and cleanup, without restarting
the gateway, resetting counters, changing instrumentation or tuning rules.
See the cooldown note in the parent runbook before repeating this class.
