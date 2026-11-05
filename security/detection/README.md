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
# Or all three, sequentially:
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
