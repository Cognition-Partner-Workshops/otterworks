# Security detection replay

This lab **observes** the planted DAST weaknesses; it does not remediate them.
An alert means suspicious activity was observed, not that exploitation succeeded.
Probe verdicts remain independent of detection: a `vulnerable` or `secure` result
can both produce a passing detection replay.

## Run locally

Requires Docker Compose, Make and [uv](https://docs.astral.sh/uv/).
Run from the repository root:

```sh
make detect-up
make detect-list
make detect-status
make detect-replay CLASS=identity-forgery
make detect-replay CLASS=cross-customer-access
make detect-replay CLASS=credential-stuffing
make detect-replay CLASS=ib-payment-anonymous
make detect-replay CLASS=ib-payment-amount
make detect-replay CLASS=ib-auth-id-mismatch
make detect-replay CLASS=ib-admin-non-admin
make detect-replay CLASS=ib-failed-logins
make detect-replay CLASS=fin-makerchecker-repeat
make detect-replay CLASS=fin-makerchecker-disabled
make detect-replay CLASS=fin-privileged-endpoint
# Or all eleven, sequentially:
make detect-replay CLASS=all
make detect-test
make detect-rules-test
```

`detect-up` layers the existing application, infrastructure and incident Compose
files, starting only postgres, redis, prometheus, alertmanager, alert-sink,
document-service, auth-service and api-gateway. It builds the three application
images. If already built, use `make detect-up DETECT_BUILD=--no-build`.
Startup waits for service health checks before returning, avoiding probes racing
document-service migrations and tripping the gateway circuit breaker.
The other services are deliberately absent: a full DAST scan can have inconclusive
results for their probes. Do not interpret these as security passes.

Docker Hub rate limits can be worked around by pulling the equivalent
`mirror.gcr.io/library/<image>` and retagging to the original name. Maven Central
429s in the auth build can be worked around locally with a Gradle init script
under `/home/gradle/.gradle/init.d/` that routes plugin/buildscript/dependency
repositories to `https://maven-central.storage-download.googleapis.com/maven2/`.
Build the auth image separately, tag it `otterworks-auth-service:latest`, then use
`DETECT_BUILD=--no-build`; no application source changes are necessary.
Compose's obsolete `version` warning is harmless with current Docker Compose.

### URLs and budgets

| Environment variable | Default |
|---|---|
| `DETECT_GATEWAY_URL` | `http://localhost:8080` |
| `DETECT_PROMETHEUS_URL` | `http://localhost:9090` |
| `DETECT_ALERTMANAGER_URL` | `http://localhost:9093` |
| `DETECT_SINK_URL` | `http://localhost:9095` |

Use only an isolated target you own. Probes create users/documents, try traversal
and forged identities, submit failed logins, and send two bursts of up to 1500
health requests, including rotated X-Forwarded-For. Do not run against t-main or
a shared production environment. Do not configure real on-call webhooks for local
replays. Embedded credentials in URLs are rejected.

`attack-classes.yaml` is the source of class/probe/alert mappings and budgets:
360 seconds to become quiet, 300 seconds for the subprocess, and 180 seconds from
attack start for firing **and delivery**. A three-second poll interval bounds
measurement precision. Rules evaluate every 15 seconds, hold for 15 seconds,
and Alertmanager adds group wait/interval delays.

### What the replay proves

1. **BEFORE:** gateway, Alertmanager and sink are reachable; all expected rules
   exist and are healthy. Wait for every class rule to be inactive (pending is
   not quiet) and for Alertmanager's matching alerts to disappear. Require both
   to stay quiet for 60 seconds (the configured group interval), so a rapid
   refire is not deduplicated as the previous incident. Snapshot the relevant
   scraped counters and sink history length. This is a before-state guard;
   firing thresholds and the 180-second attack/delivery budget are unchanged.
2. **ATTACK:** invoke the existing DAST scanner with repeated `--only`, the
   selected IDs, `--no-baseline` and a unique report directory. Record verdicts;
   scanner exits 0, 1 and 3 are data, not detection failure.
3. **AFTER:** require every expected rule to be firing simultaneously and a new
   `/security` sink delivery for every expected alert, with firing status and the
   matching class. Prior deliveries and resolved messages cannot satisfy the gate.
   Snapshot counters again and record alert instances, `activeAt`, observed
   seconds-to-fire, verdicts and the actual sink payloads.

Prometheus's `activeAt` is when the pending period began. `seconds_to_fire` is
the first observed firing time from attack start, not an estimate derived from
`activeAt`; it includes probe runtime if a rule fired while probes were running.
The sink delivery is evidence of Alertmanager delivery, not just an active alert.

Reports are written to ignored `reports/<class>-<UTC stamp>.{json,md}`.
Raw scanner reports/console logs stay in a unique sibling `*-probes/` directory.
Only compact verdicts and detection evidence are copied into the replay reports,
not raw DAST request/response credentials. Reviewed passing reports can be copied
to `evidence/` for a durable record.

Exit codes from `uv run security/detection/replay.py replay <class>`:

- **0:** every expected alert fired and was delivered.
- **1:** firing/delivery did not complete within budget.
- **2:** before state stayed active, target/telemetry was unreachable, rules or
  scraped counters were missing, or the scanner could not set up.

GNU Make maps any failed recipe to exit 2. Call the Python CLI directly when
distinguishing replay exits 1 and 2. Repeated replays wait for the two-minute
`increase()` window, pending alerts and Alertmanager's resolution/deduplication
state to drain; do not reset counters or delete
sink history just to obtain a passing before-state.

The existing rate-limit probe reuses the same 1500 spoofed addresses on every
run. The gateway retains their buckets until they have been idle for ten minutes,
with cleanup every five minutes. After a full DAST scan or credential replay,
allow **up to 15 minutes without another rate-limit probe** before expecting
`SecurityLimiterClientChurn` to fire again. Quiet alerts alone do not imply fresh
buckets. A replay during that cooldown correctly fails if no new keys were
created; it must not lower the threshold, reset counters or manufacture traffic.

## Identity forgery

**Alerts:** `SecurityJWTRejected`, `SecurityIdentityHeaderInjected`,
`SecurityShareTokenRejected`.

**Signal:** increases over two minutes in gateway JWT rejection reasons
`alg_not_allowed|bad_signature|malformed`, inbound `X-User-*` identity headers,
or rejected document share tokens. One event suffices. Missing/expired gateway
JWTs are counted but excluded from paging to avoid routine login/expiry noise.
Missing/empty share tokens rejected by validation with 422 are counted too; the
current share-forgery probe sends a missing-token control before its forged token.
A successful forgery is not itself a token rejection.

**Triage:**

1. Read the replay's finding IDs and DAST verdicts. Separate attempted attacks
   from successful ones; compare legitimate control requests.
2. Check the reason-labeled counter, gateway responses and document responses.
   Confirm the request went through the gateway rather than a direct backend.
3. Correlate timing with an authorized scan. Review header names and trusted
   proxy boundaries without logging JWTs or token values.
4. Preserve the payload and escalate actual unauthorized access. Remediation
   belongs on its own branch, never by erasing golden-app planted weaknesses.

**False positives:** outdated clients can send malformed tokens or their own
identity headers; broken/bookmarked share links can be invalid. These signals
do not establish that the gateway or backend accepted an asserted identity.

## Cross customer access

**Alerts:** `SecurityCrossOwnerAccess`, `SecurityOwnerOverride`,
`SecurityExportPathTraversal`.

**Signal:** any two-minute increase in document authorization events:
`cross_owner_object{outcome="denied|allowed"}`,
`owner_override{outcome="observed"}`, or
`export_path_traversal{outcome="observed"}`. Traversal observations include
`..`, either path separator, and absolute paths, regardless of the response.
Owner overrides include raw PUT/PATCH bodies even though those schemas currently
ignore the extra field. Observing an override does not imply it was applied.

**Triage:**

1. Distinguish denied object checks from allowed cross-owner lists/search/share
   reads. Identify whether the caller is entitled to shared content.
2. Inspect DAST controls and the owner assignment result. A valid create with a
   different owner is different from an ignored update field.
3. Inspect the export path and response outcome without opening arbitrary
   host paths yourself. Preserve request correlation IDs and scan evidence.
4. Escalate unauthorized reads/writes; do not change the planted behavior while
   investigating detection.

**False positives:** valid share-link reads by another authenticated owner,
deliberate administrative imports, and legitimate nested export paths can match.
The path rule intentionally observes every separator as well as traversal.

## Credential stuffing

**Alerts:** `SecurityLoginFailureBurst`, `SecurityLimiterClientChurn`,
`SecurityRateLimitRejections`.

**Signal:** over two minutes, at least 10 failed login responses, more than 100
new limiter client buckets, or more than 100 rate-limiter HTTP rejections.
The brute-force probe submits 12 bad logins; the rate-limit probe contrasts a
single-client burst with a rotated-XFF burst. Login outcomes separately count
success, failure (4xx except 429), throttled (429), and error.

**Triage:**

1. Compare failure/throttle/error/success counters and auth health. Upstream 5xx
   is not classified as a bad-password failure.
2. Compare new buckets and rejections with ingress traffic and trusted proxy
   configuration. A fresh client key is not necessarily a unique human or IP.
3. Check scan timing, DAST verdicts and whether rotation avoided limiting.
4. Escalate unapproved activity. Avoid putting client IPs, usernames or user IDs
   into metric labels; investigate using access-controlled request logs instead.

**False positives:** load tests, NAT/proxy changes, many new legitimate clients,
or a burst of users retrying passwords can match. These counters are bounded
aggregates and cannot attribute an attack to an individual.

For the single-client failure-only replay and its shared rule, see
[IB failed logins](#ib-failed-logins).

## Script-backed replay classes

An optional manifest `attack_script` selects a Python script inside
`security/detection/attacks/`; absolute, missing and escaping paths are rejected.
It runs as explicit argv: `uv run <script> --target <url> --report-dir <dir>`,
with one `--only <finding-id>` per declared scenario and the same subprocess
timeout as DAST. Existing classes still run DAST with `--no-baseline`.
Scripts must write `dast-report.json` containing `results` with exactly the
declared `finding_id` values, `verdict` and `detail`. Exit codes 0/1 allow
result evaluation; other exits, missing/malformed reports and timeouts fail
closed. The IB script reports **inconclusive** exploitation verdicts: sending
tripwire requests does not establish an IB vulnerability. Detection success
still requires every expected alert firing and a fresh security-sink delivery.
Reports record request paths/statuses, never JWTs, passwords or user identifiers.

The IB script uses one fixed client key (`X-Forwarded-For: 192.0.2.80`) without
rotation, including all twelve bad-password attempts. It creates ordinary
`USER` registrations, not privileged fixtures. The admin observation matches
the auth-service role **ADMIN**, case-insensitively. Nothing here authorizes,
rejects, routes, or changes response status/body/header behavior.

## IB payment anonymous

**Alert:** `SecurityPaymentRouteAnonymous`.

**Signal:** `payment_route_call{reason="anonymous"}` increases over two minutes
on paths containing `/fund-transfer` or `/utility-payment`. A valid bearer
token signed by either gateway or peer secret instead counts `authenticated`,
even on JWT-bypass paths. Invalid, expired and absent tokens count anonymous.

**Triage:** inspect method/path, gateway and IB request correlation IDs and
token-validation outcomes without copying credentials. Compare downstream
access logs and the alert's before/after counters with approved replay timing.
Escalate unexpected payment-path traffic to the IB owner.

**False positives:** discovery scans, old clients, expired credentials and
intentional negative tests can match; this is not proof of accepted payment.

**Visibility limit:** these payment routes **404 in OtterWorks**; alerts are
**edge tripwires**. OtterWorks has **no account-ownership data** for these paths.
The non-owner payment signal is **NOT observable** here: a valid token is not
evidence of ownership. Authoritative ownership and payment authorization checks
belong in the internet-banking services, not this detection middleware.

## IB payment amount

**Alert:** `SecurityPaymentAmountInvalid`.

**Signal:** on POST/PUT/PATCH payment paths only, a top-level JSON `amount`
(number or numeric string) is non-positive or has more than two decimal places.
Decimal strings and exponents are parsed exactly, without float rounding.
Scale includes explicitly supplied trailing decimals (e.g. `10.500` trips
precision; `10.50` does not). Both reasons may count for the same amount.
Only bodies up to 64 KiB are inspected; oversized, unreadable and non-JSON bodies
are ignored, and the body bytes/read error/close are retained downstream.

**Triage:** correlate amounts and paths in access-controlled IB logs;
distinguish `non_positive` from `precision`. Check currency conventions and
whether the actual service accepted a payment. The replay sends 0, -100000 and
0.005 using a valid ordinary user token.

**False positives:** refunds, zero-value checks, currencies with different minor
units and clients emitting extra trailing zeros can match.

**Visibility limit:** these routes **404 here**; alerts are **edge tripwires**,
not payment validation. OtterWorks has **no account-ownership data**. Ownership,
currency-specific amount validation and payment authorization belong in the
internet-banking services. Nested amounts and bodies over the cap are invisible.

## IB auth id mismatch

**Alert:** `SecurityAuthIdMismatch`.

**Signal:** a supplied `X-Auth-Id` differs from a validated JWT `sub` (falling
back to `user_id`), or no valid bearer token is present. Matching IDs do not
count. Observation applies even to public and unmatched paths; it does not
strip, overwrite or trust the header.

**Triage:** inspect trusted-proxy identity propagation and compare authenticated
principals with the asserted header in restricted IB logs. Distinguish mismatch
from unauthenticated events. The replay registers A and B, then sends A's token
and B's header to the normal `/api/v1/documents` route.

**False positives:** stale sessions, proxy misconfiguration and legitimate
delegation using a differently defined header can match.

**Visibility limit:** the IB payment/`bank-users` routes **404 here**, so these
alerts are **edge tripwires**; the documents replay tests header observation,
not IB access. Authoritative identity binding and ownership checks belong in
the internet-banking services. OtterWorks has **no account-ownership data** for
payment routes; header disagreement alone does not prove unauthorized access.

## IB admin non admin

**Alert:** `SecurityAdminRouteNonAdmin`.

**Signal:** paths starting `/api/v1/admin` or containing `/bank-users` are
called without a valid token carrying the `ADMIN` role (case-insensitive).
Reasons are fixed `admin_api` and `bank_users`. Observation happens before
JWT bypass and rate limiting, without imposing a role gate.

**Triage:** separate ordinary-user calls from absent/invalid credentials.
Check intended role grants in the auth service and actual IB admin audit logs.
Correlate the replay's calls to `/api/v1/admin/users` and `/bank-users`;
an upstream admin-service outage is not evidence of successful admin access.

**False positives:** navigation probes, stale role grants, help-desk automation,
and intentionally denied access checks can match.

**Visibility limit:** `/bank-users` and the payment routes **404 here**;
`/api/v1/admin` is mapped but its upstream may be absent or unavailable.
These alerts are **edge tripwires**, not enforcement. Authoritative admin
authorization belongs in the internet-banking services. OtterWorks has **no
account-ownership data** for the IB payment paths.

## IB failed logins

**Alert:** the existing `SecurityLoginFailureBurst`; no duplicate rule.

**Signal:** at least 10 failed login responses within two minutes, held for
15 seconds. Replay sends twelve wrong-password attempts for one registered
ordinary user from one fixed client key, without XFF rotation. HTTP 429 and 5xx
remain distinct throttled/error outcomes rather than password failures.
The existing alert retains `attack_class=credential-stuffing` for compatibility;
the manifest's `alert_attack_class` maps this replay to that label for fresh
delivery verification. The existing credential-stuffing replay is unchanged.

**Triage:** inspect success/failure/throttled/error counters and auth health;
correlate authorized test windows and account-specific audit logs. Investigate
unexpected concentrations, without adding identity/IP metric labels.

**False positives:** mistyped or stale passwords, password-manager retries,
and simultaneous legitimate user failures can trip the global aggregate.

**Visibility limit:** this is a global failure burst, not per-account attack
attribution. The IB payment/`bank-users` routes **404 here**; these detections
are **edge tripwires** and OtterWorks has **no account-ownership data** for
payment paths. Authoritative credential protections, ownership, payment and
admin checks belong in the internet-banking services.

## Fineract edge visibility

No Fineract service is deployed or routed by this stack. These detections
observe method, decoded path, query and capped JSON body only, before JWT
bypass and rate limiting. Paths match at a segment boundary regardless of
prefix: bare paths, `/api/v1/...`, `/fineract-provider/api/v1/...`, and other
prefixes are covered. They never authorize, block or reroute a request.
Run the three Fineract replays **serially** using the commands above.

Every Fineract alert has `source=fineract-edge` and
`confirmation=verified-path`. **Verified-path means a matching request,
not verified exploitation or successful execution.** The actor's office and
permissions are not evaluated. Basic credentials and
`Fineract-Platform-TenantId` do not provide a validated actor to this gateway.
The replay script needs no credentials and reports exploitation as
**inconclusive**. These paths return the existing JSON 404 here.
Authoritative office, permission, maker/checker segregation and audit checks
belong in Fineract itself; no Fineract configuration is actually changed.

## Fin makerchecker repeat

**Alert:** `SecurityFineractMakerCheckerRepeatApprove`.

**Signal:** a POST to `.../makercheckers/{id}?command=approve` repeats the
same ID within 10 seconds of an earlier approve request observed at this
gateway. Single approves, different IDs, GETs and reject commands do not
increment the counter. Approval response status is deliberately not consulted:
here, even both 404 requests are counted as repeated approval *attempts*.

State is process-local, shared across prefixes/callers/tenants, mutex protected
and bounded to 10,000 SHA-256 ID keys. Expired entries are removed on the next
approve; at capacity the oldest observation is evicted. Each approve refreshes
its 10-second sliding expiry. Restarts lose state; replicas do not share it.
No ID, actor, office or tenant is a metric label.

**Triage:** correlate request IDs/timing with Fineract audit records. Verify
whether the first request succeeded, whether retries were idempotent, and
whether the checker is permitted for the actor's office.

**False positives:** browser double-clicks, retries, approved automation, and
the same numeric ID in different tenants can match.

**Visibility limit:** gateway-local attempts only, not an approval audit.
Office and permissions are not evaluated; capacity eviction, restarts and
multi-replica routing can miss repeats. The paths 404 here. Verify actual
approval and segregation-of-duties rules inside Fineract.

## Fin makerchecker disabled

**Alert:** `SecurityFineractMakerCheckerDisabled`.

**Signal:** PUT `.../configurations/name/maker-checker` with top-level JSON
`enabled: false` counts `config_put`; POST
`.../configurations/{id}?command=disable` or
`.../configurations/name/maker-checker?command=disable` counts
`command_disable`. JSON `enabled: true`, string `"false"`, absent fields,
non-JSON and wrong methods do not count. The shared banking body observer
accepts at most 64 KiB, restores body bytes/read errors/close, and ignores
oversized or unreadable JSON.

**Triage:** check the configuration ID/name and approved change window in
Fineract audit logs, then verify the actual resulting configuration and
actor's office/permissions. Restore controls only through authorized Fineract
operations, not by modifying the golden demo's detection behavior.

**False positives:** authorized maintenance and negative tests. A numeric
configuration ID is not resolved here: it may refer to a different setting.

**Visibility limit:** this is a disabling-shaped request, not confirmed loss
of maker-checker enforcement. Office and permissions are not evaluated.
These paths 404 here; authoritative configuration and authorization checks
belong in Fineract. Oversized/unreadable bodies are invisible to body matching.

## Fin privileged endpoint

**Alert:** `SecurityFineractPrivilegedEndpoint`.

**Signal:** POST to `.../datatables/deregister/*` counts
`datatable_deregister`; POST to
`.../creditBureauIntegration/addCreditReport` counts `credit_report_add`.
GET and other methods do not count. These requests are counted regardless of
caller permissions, authentication or downstream success.

**Triage:** correlate with approved datatable administration and credit-report
ingestion jobs, then inspect Fineract audit records for actor office, grants,
target and outcome. Do not copy Basic credentials or sensitive credit data
into metrics, alerts or replay artifacts.

**False positives:** authorized administrators, scheduled imports and
intentional negative probes all match.

**Visibility limit:** a privileged-shaped path is not evidence of permission
bypass. The actor's office and permissions are not evaluated; these paths
404 here. Authoritative grants and outcomes must be checked inside Fineract.
