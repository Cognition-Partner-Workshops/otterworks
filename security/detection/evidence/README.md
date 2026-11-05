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

## Internet-banking edge tripwires

The gateway-only extension was built and restarted on 2026-11-05. Other stack
containers stayed running; Prometheus loaded the new rules via HTTP reload,
without a restart. The five independent class replays ran concurrently, each
with its own quiet-state guard, before/after snapshots and fresh-delivery gate.
The anonymous-payment snapshot also includes the other replay's three
authenticated payment calls, separately labeled; they do not fire its rule.
No thresholds or vulnerable handlers changed.

| Class | Passing report (JSON and Markdown) | Expected alert | First observed firing |
|---|---|---|---|
| ib-payment-anonymous | `ib-payment-anonymous-20261105T142911348432Z.{json,md}` | SecurityPaymentRouteAnonymous | 33.3 seconds |
| ib-payment-amount | `ib-payment-amount-20261105T142911335771Z.{json,md}` | SecurityPaymentAmountInvalid | 33.8 seconds |
| ib-auth-id-mismatch | `ib-auth-id-mismatch-20261105T142911374645Z.{json,md}` | SecurityAuthIdMismatch | 37.2 seconds |
| ib-admin-non-admin | `ib-admin-non-admin-20261105T142911442526Z.{json,md}` | SecurityAdminRouteNonAdmin | 30.7 seconds |
| ib-failed-logins | `ib-failed-logins-20261105T142911332861Z.{json,md}` | SecurityLoginFailureBurst (existing rule) | 37.7 seconds |

All five reports exit 0 with inactive BEFORE and firing AFTER states and fresh
deliveries to `/security`. The five `ib-<class>-alerts.png` screenshots were
visually checked: each filters the actual Prometheus `/alerts` page to the
expected firing rule. The reused login alert retains its credential-stuffing
label/group; no second login alert was introduced.

Observed counter deltas: four anonymous payment calls; three authenticated
payment calls; two non-positive amounts and one precision violation; one ID
mismatch; one admin-API and one bank-users non-admin call; twelve login failures.
The fixed-client failure replay produced twelve HTTP 400 responses (the auth
service's existing wrong-password behavior), with no XFF rotation or throttling.
The documents request returned 200, payment and bank-users requests returned
404, and the unavailable admin upstream returned 502. These statuses were not
changed to make detection pass.

Script exploitation verdicts are **inconclusive**, not vulnerability claims.
The payment routes 404 and OtterWorks has no IB account-ownership data;
non-owner payment access is **NOT observable**. These are edge tripwires;
authoritative ownership/payment/admin checks belong in the IB services.

`ib-regression-comparison.{json,md}` compares a fresh post-extension 19-probe
scan against both the previously captured actual demo-bank build scan and the
pre-IB instrumented build scan. All 19 verdicts match: 9 secure, 8 vulnerable,
2 inconclusive (absent file/search services). It retains scan timestamps,
baseline SHA and running image IDs. The fresh scan exits 1 because the eight
planted findings remain, not because detection changed application behavior.

## Fineract edge tripwires

The gateway-only extension was rebuilt and restarted on 2026-11-05; all other
stack containers stayed running. Prometheus rules were HTTP-reloaded. Docker
Hub returned HTTP 429, so an external build file used the Google mirror for
the same base images; no repository Dockerfile was changed.

The three replays ran **serially**. Each exited 0 with inactive BEFORE rules,
before/after counters, the expected firing AFTER rule and fresh Alertmanager
delivery to `/security`. Every attack request returned the existing HTTP 404.

| Class | Passing report (JSON and Markdown) | Expected alert | First observed firing |
|---|---|---|---|
| fin-makerchecker-repeat | `fin-makerchecker-repeat-20261105T184704040838Z.{json,md}` | SecurityFineractMakerCheckerRepeatApprove | 36.3 seconds |
| fin-makerchecker-disabled | `fin-makerchecker-disabled-20261105T184853887400Z.{json,md}` | SecurityFineractMakerCheckerDisabled | 36.2 seconds |
| fin-privileged-endpoint | `fin-privileged-endpoint-20261105T185043680830Z.{json,md}` | SecurityFineractPrivilegedEndpoint | 27.2 seconds |

All three `fin-<class>-alerts.png` screenshots were visually checked on the
actual Prometheus `/alerts` page: each shows its expected rule firing.
All three prefixes were exercised: bare paths, `/api/v1` and
`/fineract-provider/api/v1`. Observed counter deltas were three repeat
approvals; three `config_put` and six `command_disable`; three datatable
deregistrations and three credit-report additions.

The alerts carry `source=fineract-edge` and `confirmation=verified-path`.
That confirms path matching, **not** successful execution or authorization
bypass. Actor office and permissions are not evaluated. The script verdicts
are deliberately **inconclusive**: no Fineract is deployed or routed here.

`fin-regression-comparison.{json,md}` compares a fresh post-extension scan
with the retained actual demo-bank service-build scan and the pre-Fineract
internet-banking detection scan. All 19 verdicts match: 9 secure, 8 vulnerable,
2 inconclusive (absent file/search services). It includes baseline SHA,
timestamps and running image IDs. The fresh scan exits 1 because planted
findings remain, not because observation changed vulnerable behavior.
