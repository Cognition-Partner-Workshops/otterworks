# Busy-season load testing

## Safety and prerequisites

Use a dedicated, disposable tenant. Never load-test or mutate golden `t-main` /
`otterworks-main`, and do not fix the intentionally broken admin service.
The JS guard rejects recognizable main hosts unless `READ_ONLY=1`, `PROFILE=smoke`
and `ALLOW_MAIN=1` are all supplied; this is an explicit escape hatch, not permission
to use main. Do not point alternate DNS aliases or proxies at main. CI never
sets that opt-in; the cluster runner refuses main entirely.

Install k6 1.7.1. From the repository root:

```sh
# Requires provisioned AWS credentials, DB_PASSWORD, helm, terraform, jq and kubectl.
# Register direct deploys just as demo-platform/runner/entrypoint.sh does.
# Otherwise the platform reaper treats the namespace as an orphan despite TTL.
source demo-platform/lib/control-common.sh
if ctl_tenant_exists loadtest; then echo 'Choose a fresh tenant id'; exit 1; fi
ctl_update_status loadtest deploying
JWT_SECRET="$(openssl rand -hex 24)" scripts/deploy-tenant.sh loadtest --ttl 24h --profile full --host-suffix demo.otterworks.app
ctl_set_active loadtest https://t-loadtest.demo.otterworks.app \
  https://api-t-loadtest.demo.otterworks.app otterworks_loadtest otterworks-loadtest \
  "$(( $(date +%s) + 86400 ))"
make loadtest-smoke BASE_URL=https://api-t-loadtest.demo.otterworks.app
make loadtest-baseline TARGET=https://api-t-loadtest.demo.otterworks.app
```

Deployment compatibility: the deploy script's generated 64-character JWT key
causes auth's JJWT library to issue HS512, while document-service accepts only
HS256/HS384. For this disposable fixture, explicitly supply a randomly generated
48-character `JWT_SECRET` **at initial deployment** so auth issues HS384. Keep it
in the environment only and reuse the tenant's stored secret on later deploys.
Do not alter application JWT validation or another tenant's secrets. Changing an
existing tenant's key invalidates its outstanding sessions.

Full is necessary: core omits search and notifications. Deployment creates a
dedicated Postgres database, Redis and MeiliSearch; physical AWS backing stores
and compute are shared. Coordinate high-rate runs; an isolated namespace is not
an isolated cluster. Leave the TTL in place; teardown via the tenant runbook.
The control record and namespace TTL must both be valid. Pinning exempts expiry,
not orphan detection, and pinned tenants can still idle to zero after an hour.
At the end, run `scripts/teardown-tenant.sh loadtest` with `DB_PASSWORD` available,
then `ctl_delete_tenant loadtest` to remove the control record and lock.

## Profiles and configuration

| PROFILE | Default shape | Purpose |
|---|---|---|
| smoke | 2 VUs, 60s | Abort-on-correctness-failure gate; report latency |
| load | 2m ramp to TARGET_VUS (50), 10m hold, 2m down | Original closed-loop VU model |
| baseline | 30s up, 4m at 10 journeys/s, 30s down | Provisional normal traffic model |
| peak | Same timing, 30 journeys/s | Sustained 3x busy season |
| stress | 2m to TARGET_VUS, then 3m each to 2x/3x/4x; 2m down | Original ramp past peak to find the knee |
| spike | 1m to 0.1x TARGET_VUS, 20s to full, 3m burst, recovery | Original 10x burst model |
| soak | 5m up, 60m at TARGET_VUS, 5m down | Original one-hour sustained plateau (70m total) |

These are workload hypotheses, not observed production rates. Arrival profiles
start at zero. `RATE` multiplies baseline/peak journey arrival rates (not HTTP
request rates). `VUS` multiplies their 30 preallocated / 150 maximum VU budgets;
it does **not** change arrival rates. For the original closed-loop profiles,
`TARGET_VUS` (default 50) times `VUS` controls the VU target.
`USERS` defaults to 10 (integer 1..200).
`DURATION=5m` rescales all stages; `DURATION=1h` makes soak one hour total.
`HOLD=2m` changes the load profile's steady-state length (default 10m);
`DURATION`, if supplied, rescales the resulting full profile including that hold.
`RUN_ID` optionally sets a unique alphanumeric/hyphen identifier.

```sh
DURATION=5m RATE=1 USERS=10 make loadtest-peak BASE_URL=https://api-t-loadtest.demo.otterworks.app
```

## Journey and fixtures

Setup registers unique `loadtest-<run>-<n>@example.test` users, receives real JWTs,
and seeds three markdown documents/user. Each run uses a fresh pool. Tokens and
passwords remain in k6 memory, never in result files. Setup then probes every
journey action, including actual signed-S3 download bytes, before starting load.
A failed preflight aborts rather than silently omitting a hot path.
Existing `LOADTEST_EMAIL` / `LOADTEST_PASSWORD` credentials are still supported;
they select a single-user pool and seed that dedicated account. `READ_ONLY=1`
skips all setup, registration, authentication and writes and only probes health.

The repeating 21-iteration mix is: document list 6/21, get 4/21, create+update
2/21, document search 2/21, search-service search 2/21, and login, file list,
folder list, upload+download, unread-count each 1/21. Writes delete their newly
created document/file after use; three seed documents and user accounts remain
for diagnosis. Document deletion is soft: long soak runs still accumulate
history/tombstones. Shared-store teardown must follow the tenant runbook.
Search-service may return an empty valid result because tenant eventing is off;
the SQL document search has seeded data. This is a small-file (~1KiB), small-user-
corpus model, not a large-upload or 400-document N+1 benchmark.

Paths come from gateway `ServiceRoutes`, auth registration DTOs, FastAPI document
schemas, Rust file multipart handlers, Flask search and Ktor notification routes.
Login refreshes a pool entry's token in the local VU; access tokens default to
one hour. Each iteration retains the original health probe, then one weighted
action. Smoke sleeps 0.5s/action; original VU profiles sleep 1–3s, while
baseline/peak arrival profiles use no artificial sleep.

## SLOs and results

Overall: `http_req_failed < 1%`, p95 < 500ms, p99 < 1500ms. The original paging
SLOs remain: reads p95 < 800ms / p99 < 1500ms, health p95 < 300ms.
Per-endpoint writes use p95 < 500ms / p99 < 1500ms, except login p95 < 1000ms
across profiles because password hashing deliberately
costs more than ordinary reads. Expected status checks must exceed 99%.
Smoke aborts only on correctness (checks, HTTP failure rates and transport/5xx
rate), after a 10s evaluation delay. Latency thresholds still fail the final
result but do not abort on a handful of early samples. Non-smoke tests keep
running to expose failure/recovery.
`rate_limited` counts 429s separately; `server_errors` measures the fraction of
transport/5xx failures, excluding 429s. Read this custom Rate's `rate` value:
its `fails` field counts false (non-error) samples, not HTTP failures.
429s still count toward the HTTP failure SLO.
Baseline/peak also fail if iterations are dropped (insufficient VUs).

Every request has stable `name` and `endpoint` tags, no dynamic IDs or signed
URLs in metric labels; `phase` distinguishes setup, preflight and journey.
Latency/failure SLOs select `phase:journey`, excluding setup and preflight;
each endpoint must have at least one journey sample, so missing traffic cannot
produce a false green. Write/upload cleanup requests are part of the journey.
The S3 byte transfer is `file_content`; its time is external storage latency.
JSON and Markdown summaries are written to gitignored `tests/load/k6/results/` with
profile/run IDs. Exit code 99 indicates breached thresholds; never interpret a
completed run as a passing gate. Inspect per-endpoint percentiles, 429 count,
dropped iterations, achieved request rate and monitoring together. For stepwise
stress analysis, add `--out json=tests/load/k6/results/stress-timeseries.json` to k6.
Raw JSON may be large; summaries contain no individual response bodies.

**Gateway caveat:** default is 100 requests/second **per client IP**, per gateway
replica. Several requests can occur per journey (upload includes signed URL and
S3 transfer); HTTP RPS is not journey RPS. A single VM or ingress-preserved source
IP can hit the limiter before the backend saturates. Count 429s; do not spoof
forwarded headers or weaken the limiter to manufacture capacity. Distributed
sources or an explicitly approved tenant-only limit are separate experiments.

## In-cluster execution

Use an existing isolated tenant namespace; the script never creates namespaces,
LoadBalancers or RBAC. It mounts the suite from a per-run ConfigMap into the
pinned k6 image, uses no service-account token, and exports results before the
Job exits with k6's status. kubectl and `envsubst` are required locally.

```sh
BASE_URL=https://api-t-loadtest.demo.otterworks.app PROFILE=peak DURATION=5m \
  NAMESPACE=otterworks-loadtest bash tests/load/k6/k8s/run.sh
```

The default 3h Job deadline includes result collection; override `DEADLINE` for
longer soaks. Finished Jobs expire after 24h; ConfigMaps are removed after a
successful collection. If interrupted, retrieve `/work/results.tar.gz` with
kubectl exec, touch `/work/collected`, and delete that run's ConfigMap manually.
The generator consumes shared cluster resources; check its CPU limit and dropped
iterations before attributing saturation to the application. It still uses the
external tenant API host so ingress and the IP limiter remain in the test path.

For CPU/memory/throttling/restart evidence, port-forward Prometheus, note the run's
Unix start/end times, then export its existing 15s-resolution samples:

```sh
kubectl -n monitoring port-forward svc/prometheus-prometheus 19090:9090
python3 tests/load/k6/capture.py --start "$START" --end "$END" \
  --output tests/load/k6/results/stress-monitor.json
```

The exporter is read-only and namespace-scoped. Missing series are not zero;
verify that Prometheus scrapes the service before drawing conclusions.

## CI and local checks

`loadtest.yml` inspects every profile on relevant PRs without contacting a tenant,
and runs configuration safety tests. Workflow dispatch accepts a profile and
tenant API origin, then uploads summaries even when SLOs fail. It does not deploy
tenants or obtain AWS credentials. There is no automatic load on pushes/PRs.

```sh
node --test tests/load/k6/tests/*.test.mjs
for profile in smoke load baseline peak stress spike soak; do
  k6 inspect -e BASE_URL=https://api-t-inspect.demo.otterworks.app -e PROFILE=$profile tests/load/k6/otterworks.js
done
```

## Findings

### Lifecycle diagnosis (2026-11-19 UTC)

The original direct-deployed `loadtest` tenant was deleted by platform job
`demo-platform-reaper-29918685`: `orphan namespace otterworks-loadtest (no TENANT# item) -> GC`,
followed by namespace and database deletion. Namespace TTL was valid: the
independent system TTL reaper logged `expires at epoch 1795207308 -> keeping`.
Platform expiry reaped zero tenants, and idle-suspend only scales deployments.
The verified cause was missing control-table registration, not expiry or idle
suspension; no other local deletion process appeared in the process listing.

The recreated `loadbench` tenant was registered using `control-common.sh`
before direct deployment, then marked active with a 24h expiry. No pin was
necessary. The 21:15 platform job logged zero expired tenants and completed
its orphan sweep without deleting it. A fresh MeiliSearch must be ready before
search-service initializes its indexes; restarting only this tenant's search
service after readiness resolved the initial missing-index HTTP 400.

### Consolidated suite measurements

Target: `https://api-t-loadbench.demo.otterworks.app`, original service images,
one replica each of gateway/auth/documents/files/search/notifications, plus
Redis/MeiliSearch. Full deployment was used for route coverage, then unused
analytics/audit/collab/report/web/admin-dashboard deployments were scaled to
zero to conserve shared capacity. The planted admin crash was not fixed.
PgBouncer was absent (`resolve_db_endpoint` logged its direct-RDS fallback);
the document connection URL's host was the RDS instance. No shared pooler was
installed or changed for these runs.
All ten distinct business actions passed live preflight, including actual
signed-S3 download bytes and write cleanup. Smoke/baseline used a temporary
k6 hosts override to the shared ingress while DNS propagated; peak/stress
used normal DNS. Neither path bypassed ingress, authentication or rate limiting.

| Run ID | Journey duration / target | HTTP requests / wall-average RPS | Journey p95 / p99 (ms) | Login p95 (ms) | Result |
|---|---|---|---|---|---|
| `smoke-1795122076` | 60s, 2 VUs | 457 / 6.29 | 142.20 / 398.57 | 405.78 | Exit 0; all thresholds passed |
| `baseline-1795122159` | 300s, 10 journeys/s plateau | 6,351 / 20.35 | 133.72 / 403.13 | 435.96 | Exit 0; zero dropped iterations |
| `peak-1795122479` | 300s, 30 journeys/s plateau | 18,895 / 60.67 | 140.37 / 439.10 | 476.15 | Exit 99; document-create p99 1560.57ms; 24 dropped iterations |
| `stress-vm-1795122812` | 299s, original VU ramp rescaled to 5m, 0→50→100→150→200→0 | 26,580 / 84.90 | 1692.39 / 2896.15 | 539.63 | Exit 99; document endpoint and read/overall latency thresholds failed |
| `loadtest-1795123184` (in-cluster stress) | Same 299s VU ramp | 26,305 / 85.21 | 1778.29 / 6565.31 | 13082.46 | Exit 99; document/login latency and login failure SLOs failed |

HTTP counts/RPS include setup/preflight and the full wall time. Journey
percentiles exclude setup/preflight and include the retained per-iteration
health probe. Smoke/baseline/peak/VM stress had **zero HTTP failures, 429s and
transport/5xx errors**, and 100% checks. Baseline completed 2,699 iterations,
peak 8,075, VM stress 11,368. Peak is not a clean capacity pass: aggregate
percentiles conceal its failing write tail and the generator's missed arrivals.
The preliminary, now-retired standalone suite's runs are not mixed into this table.

### Bottleneck evidence and limits of inference

VM stress raw samples locate the first clear latency knee at approximately
150–165s after the first journey response (21:16:17–21:16:32 UTC), as VUs rose
from about 125 to 136. The preceding 135–150s window achieved 123.8 gateway
requests/s, overall p95 250ms and document-create p99 359ms. In the next window
achieved gateway throughput fell to 100.2/s while overall p95 rose to 2179ms
and document-create p99 to 3023ms. No 429s or 5xxs occurred in either window.

The running document container had a **500m CPU limit**. Prometheus one-minute
CPU rates rose to **0.4994 cores**, with **88.24% throttled CFS periods**; its
working set peaked at **117,473,280 bytes (~112MiB)**, below the 256MiB limit,
and its restart counter stayed zero. Its get/list/search/create/update/delete
latency SLOs all failed. In contrast, gateway CPU peaked at 0.1128 cores with
zero throttling, auth at 0.8705 cores / 17.01% throttled periods, and files at
0.0322 cores. All tested service restart counters stayed zero; only the known
admin crash-loop restarted. **Document-service CPU quota is the observed
limiting resource**, not memory exhaustion or an observed gateway rate cap.
Shared RDS and concurrent tenant activity remain possible contributors, not
excluded causes; replica/CPU-limit intervention was not measured.

The in-cluster Job reproduced the document knee at 150–165s: document-create
p99 3054ms and overall p95 1631ms. Document CPU reached 0.4993 cores with
95.16% throttled periods; memory reached 122,257,408 bytes (~117MiB), no restarts.
It also exposed **auth CPU saturation**: 0.9937 of its 1-core limit and 96.03%
throttled periods, working set 323,907,584 bytes (~309MiB), no restarts. Login
p95 first exceeded 1000ms in the 105–120s window (~103 VUs maximum, 106.3 gateway
requests/s), earlier than the document knee. Final login p95/p99 were
13082/15000ms, with **11 client timeouts out of 535 logins (2.06%)**. The raw
request statuses were zero for all eleven, and k6 logged `request timeout`;
there were **zero 429s and zero HTTP 5xxs**. Overall journey HTTP failure rate
was 0.0419%, but the per-login <1% SLO correctly failed. Checks were 99.959%.

The Job generator used at most 0.1279 of its 1-core limit, 156,676,096 bytes
(~149MiB) of 512MiB, 4.69% throttled periods and zero restarts. S3/file/search
p95s stayed below 121ms, health p95 was 20ms, and document/login tails failed
selectively. This argues against VM bandwidth or sustained generator CPU
saturation as the primary explanation. The different auth tail between runs
also shows why a short run on shared infrastructure is not a stable capacity
estimate. Auth/document logs contained no error/exception/timeout lines in the
checked ten-minute window; that does not prove database headroom.

No HA comparison was attempted. The phase-filtered recording rule
`cluster:cpu_requests:ratio` was 81.38% during the Job and 80.53% after it exited
(three nodes, 11.76 allocatable cores). Default `scale-for-load.sh ... up` would
add 600m requests: four services from one to two replicas, and the previously
disabled web frontend from zero to two. Including the 100m generator brings
the projected ratio to **86.48%**, above this runbook's ~85% headroom guardrail,
before any HPA growth to six. Two nodes already had 95%/98% CPU requested.
Do not force shared capacity expansion or take golden-tenant resources for a
comparison. The unfiltered request sum includes completed Jobs and is not the
scheduler-headroom measurement.

Monitoring artifacts and raw step samples are in ignored `tests/load/k6/results/`:
`stress-vm-{monitor.json,timeseries.json,pods-before.txt,pods-after.txt}`,
`peak-monitor.json`, `stress-cluster-{monitor.json,timeseries.json}`, the collected
`loadtest-1795123184.tar.gz`, per-run JSON/Markdown summaries and run logs.
Prometheus CPU/throttling are one-minute rates sampled every 15s, not instantaneous
CPU peaks. These short, small-corpus runs are not a production capacity guarantee.

### Recommendations

1. **Baseline passes; peak does not.** Treat 10 journeys/s as the demonstrated
   five-minute plateau, not 30. Repeat peak with `RATE=1 VUS=2` (60 preallocated
   VUs) to separate generator allocation drops from backend write tails; still
   require zero dropped arrivals and the existing per-endpoint SLOs.
2. Reserve cluster headroom, then compare **two replicas each of document and
   auth** using `scripts/scale-for-load.sh loadtest up document-service auth-service`.
   Plan capacity for its HPA 2..6 maximum and PostgreSQL pool growth, not only
   minimum replicas. Consider initial CPU requests of **250m/doc and 500m/auth**
   instead of 100m so a 70%-CPU HPA target is meaningful; validate under load
   before adopting these provisional values. Metrics-server is now available.
3. To isolate CPU-quota causality, separately test document-service's limit
   **500m → 1 core at one replica**, keeping the journey unchanged. Do not change
   limits and replicas simultaneously and claim a measured scaling benefit.
   No memory increase is indicated by these peaks or restart counters.
4. Do **not raise gateway rate limits** based on these runs: no 429s occurred
   from either source. Keep the per-IP caveat for larger/distributed tests.
5. Repeat sustained peak, spike and soak with a representative corpus before
   recommending production capacity. Their short-run throughput knee is an
   observation, not a guaranteed RPS ceiling or a tested HA improvement.

### CPU-limit intervention and HA quota

The measured CPU saturation motivates two sequential interventions: document-service
**500m → 1 core**, then auth-service **1 → 1.5 cores**. The service-specific
`infrastructure/helm/profiles/high-availability-{document-service,auth-service}.yaml`
overlays change only CPU limits. CPU requests and memory remain unchanged.
`scripts/scale-for-load.sh <id> up` applies these after the shared HA overlay;
direct Helm upgrades must include the matching service overlay explicitly.
Default chart values and single-replica tenant deployment are unchanged.
Both limits have now been applied to chaostest and the paired peaks passed
after the tenant-local JWT compatibility workaround below.

The default HA profile has HPA min 2 / **max 6**, not chaostest's experimental
max 3. The original tenant quota (12 CPU limits, 4 CPU requests, 8Gi requested
memory, 40 pods) cannot accommodate a full tenant with all five core HPAs at
max. Before HA upgrades, the scaling script applies
`infrastructure/k8s/tenant-ha-quota.yaml` to that tenant only:

This larger quota is applied **only through `scale-for-load.sh ... up`** (or
an explicit operator apply), not by `deploy-tenant.sh` or direct Helm upgrades.

| Resource | Full tenant, five core HPAs at max 6 + auth rollout surge + k6 Job | HA quota |
|---|---:|---:|
| CPU limits | `6.25 + 6 × 4 + 2 × 1.5 + 1 = 34.25` cores | 35 cores |
| CPU requests | `0.95 + 6 × 0.5 + 2 × 0.1 + 0.1 = 4.25` cores | 5 cores |
| Memory limits | `5120 + 6 × 2048 + 2 × 1024 + 512 = 19968` Mi | 20Gi |
| Memory requests | `2496 + 6 × 1024 + 2 × 512 + 128 = 9792` Mi | 10Gi |
| Pods | `10 + 6 × 5 + 2 + 1 = 43` | 43 |

The fixed contribution includes all non-core services at one replica plus Redis
and MeiliSearch; it does not assume optional services have been scaled down.
The surge allowance is for **one service rollout at a time** (the script waits
sequentially). The existing 25% maxSurge rounds up to **two pods at max 6**,
so the quota covers two extra auth pods, rather than only one.
Terminating pods can temporarily consume additional quota: wait for them to
exit before proceeding if admission is blocked. Custom workloads, simultaneous
rollouts, additional HPAs and changed Job resources require recalculation.

Quota is an admission ceiling, **not reserved cluster capacity**: these settings
do not make the shared cluster capable of scheduling the maximum. Check node
request headroom and DB connections before using HA. Non-HA tenants retain
their existing quota. `down` does not shrink quota or reset CPU limits; it only
disables the HPA and sets one replica. A fresh tenant deployment restores the
ordinary deployment defaults.

For the chaostest experiment, retain max 3 and upgrade only the selected release
with `--reuse-values -f <matching-service-overlay>`; do not run the scaling
script or reapply the shared max-6 overlay. With the four auxiliary deployments
at zero, all-core-max totals are 13.75 CPU after document and 15.25 after auth;
one auth surge plus the k6 Job brings the final total to 17.75, within an
18-core quota. The owning chaos session approved this experiment and its
18-core quota patch; no lifecycle changes or node additions were authorized.

#### Chaostest document-first attempt: blocked before journey traffic

At 21:50Z on 2026-11-19, the tenant's CPU-limit quota was patched to 18 and
document-service was upgraded to 1 core; rollout succeeded with three replicas.
Auth remained at 1 core. The four auxiliary deployments (admin-service,
admin-dashboard, report-service, analytics-service) remained at zero.

The in-cluster run `loadtest-1795125098` requested `PROFILE=peak RATE=1 VUS=2
DURATION=5m USERS=10`: the normal **3× baseline peak**, 30 journeys/s, with
60 preallocated VUs to avoid repeating the earlier allocation shortfall.
It exited **107** during document seeding, before any journey iteration:

```text
Error: Setup failed: status 401, missing id
checks: 10 pass / 1 fail (90.91%)
http_req_failed: 1 / 11 (9.09%)
K6_EXIT_CODE=107
```

All endpoint-coverage thresholds failed because journey request counts were
zero. Journey RPS was zero; journey p95/p99 are **not measurable**, not passing
zero-latency observations. Prometheus evidence was collected, but its brief
setup/rollout window does not establish a CPU or database capacity bottleneck.

The reachable compatibility blocker was verified independently: a real login
for the dedicated test user returned an **HS512** access token; document create
with that token and valid payload returned HTTP 401, requiring `owner_id` or
JWT authentication. The running document image's validator accepts only
`HS256` and `HS384`. Both services' JWT secrets have identical hashes and
64-byte lengths, ruling out differing stored keys as the explanation. No
secret or token values are recorded here. At this point, no auth upgrade or
second peak was attempted pending authorization for a tenant-scoped correction;
changing the shared JWT key would invalidate the chaos session's existing
tokens and requires coordination. The tenant was not torn down or reconfigured
beyond the approved CPU changes.

Ignored evidence: `tests/load/k6/results/chaostest-doc{.log,-monitor.json,
-before.txt,-after.txt,-start.txt,-end.txt}`, the run's JSON/Markdown summary,
raw k6 metrics and `loadtest-1795125098.tar.gz`.

#### Chaostest reruns after tenant-local JWT rotation

With the owning session's approval, a fresh value from `openssl rand -hex 24`
was applied to all five runtime Secrets holding `JWT_SECRET`: auth, document,
gateway, collab and admin. No ConfigMap held that key. Their deployments were
restarted sequentially; admin remained at zero replicas. Real login then
returned **HS384**, document creation returned **201**, and deletion of the
preflight document returned **204**. No application code or image was changed.

The subsequent auth CPU upgrade supplied the current JWT value to Helm through
stdin along with the CPU overlay, preserving the rotation despite
`--reuse-values`. **The other releases still have old JWT values in their Helm
release configuration:** future Helm upgrades must explicitly preserve the
current tenant Secret value or they can restore the incompatible key. Do not
print the key or commit it to a values file. Existing tokens were invalidated;
new test users/tokens were created for each run.

Both in-cluster runs used the same `PROFILE=peak RATE=1 VUS=2 DURATION=5m
USERS=10`: a 30-journey/s plateau (3× baseline), with 60 preallocated VUs.
Document and auth had three replicas throughout both runs; gateway, files and
web had two. The four auxiliary deployments remained at zero. Their CPU
requests and memory resources were not changed.

| Run | Document/auth CPU limits | HTTP count / wall-average RPS | Plateau journey HTTP RPS | Journey p95 / p99 | Login p95 / p99 | Exit / failing thresholds |
|---|---|---|---:|---|---|---|
| `loadtest-1795125530` (21:59–22:04Z) | 1 / 1 cores | 18,953 / 61.14 | 69.99 | 59.53 / 391.74ms | 664.03 / 1187.20ms | 0 / none |
| `loadtest-1795125987` (22:06–22:11Z) | 1 / 1.5 cores | 18,953 / 61.22 | 70.00 | 50.86 / 356.69ms | 432.38 / 521.48ms | 0 / none |

Wall averages use k6's full test duration (309.97s / 309.60s), including setup;
plateau RPS counts journey HTTP requests in the 240-second plateau and includes
health and signed S3 downloads. Each run completed 8,099 iterations and 18,898
journey HTTP requests. Both had **zero failed checks, HTTP errors, 429s, server
errors, dropped arrivals and interrupted iterations**. All per-endpoint latency
and coverage thresholds passed; thresholds were not relaxed.

Maximum per-pod CPU / throttled-period fraction over each capture window:

| Service | Document-first | Auth raised |
|---|---:|---:|
| Document | 0.2470 core / 0% | 0.2825 core / 0% |
| Auth | 0.3567 core / 17.91% | 0.5946 core / 70.77% |
| Gateway | 0.0353 core / 0% | 0.0342 core / 0% |
| Files | 0.0196 core / 0% | 0.0095 core / 0% |
| Search | 0.0164 core / 0% | 0.0160 core / 0% |
| Notifications | 0.0119 core / 0% | 0.0181 core / 0.94% |
| Collab | 0.0182 core / 5.70% | 0.0054 core / 0% |
| Audit | 0.00094 core / 0% | 0.00088 core / 0% |
| Web | 0.00008 core / 0% | 0.00007 core / 0% |
| Redis | 0.0066 core / 0% | 0.0060 core / 0% |
| MeiliSearch | 0.0073 core / 0% | 0.0072 core / 0% |
| Generator | 0.0940 core / 1.15% | 0.0930 core / 0.93% |

CPU and throttling are one-minute rates sampled every 15 seconds; maxima can
belong to different pods/times. The second auth throttle peak was at capture
start, **before journey traffic**, and its trailing-minute window includes the
fresh JVM rollout. To exclude setup/ramp and trailing-window overlap, the
steady slice from 90 to 270 seconds after first journey request had auth
maxima of **0.2983 core / 9.60%** before versus **0.5159 core / 3.77%** after.
Generator throttling was zero in that slice in both runs. Auth memory peaked
at 276/284MiB, document at 79/81MiB, generator at 56/56MiB; all pod restart
counters remained zero. The latency improvement is an observed pair, not proof
that CPU limits alone caused it: the auth rollout also changed JVM warm-up and
pod placement, and node contention differed.

**No next SLO-breaking bottleneck was demonstrated at this peak.** Auth remains
the slowest endpoint and the next headroom candidate: its HPA was observed
`ScalingLimited=True / TooManyReplicas` during the second run. Both auth and
document stayed at the experimental max of three, but a maxed HPA with 100m
requests (70m CPU target) is not itself evidence of CPU-limit saturation.
Further load would be needed to establish the next breaking point; it was not
generated beyond the approved 30-journey/s peaks.

Checks against alternative capacity explanations:

- **Generator/scheduling:** generator used <0.095 of its 1-core limit and
  <57MiB of 512MiB, with no dropped arrivals. Sampled Pending pod count was zero
  in both runs. Cluster CPU requests were 60.12–61.39% / 60.12–66.58% of 11.76
  allocatable cores. One node briefly reached 87.56% busy in the first run
  while the other two stayed below 33%; the second run's highest node was
  58.33% busy. Minimum node available-memory fraction was 41.24% across runs.
- **Shared RDS (`otterworks-postgres-dev`, db.t3.small):** CloudWatch one-minute
  CPU maxima were 9.91% / 9.72%, connections 50 / 55, read latency maxima
  1.76 / 0.80ms, write latency 2.91 / 1.92ms, disk queue <0.05, CPU credits 576
  and burst balance 99%. Freeable memory stayed above 814MiB. These argue
  against CPU/IO exhaustion, not all possible DB locks or connection-pool waits;
  internal wait/pool instrumentation was not collected.
- **Redis/MeiliSearch/gateway:** low observed CPU, no HTTP errors, no search
  latency failures and zero gateway 429s. No evidence makes them the next
  bottleneck at this traffic level.

**Additional nodes indicated for this demonstrated peak: zero.** Three existing
t3.xlarge nodes scheduled the experiment. If a future experiment needs more
request headroom, the permitted fourth node adds roughly 3.92 allocatable CPU
at the supplied spot estimate of $0.032–0.055/hour; it would not increase HPA
maxima or fix application/DB constraints automatically. No node was added.

Tenant state left for the chaos session: document 1 core, auth 1.5 cores,
HPA min 2 / max 3, CPU quota 18 (13.75 used after Job completion), four auxiliary
deployments at zero, and the new matching 48-character JWT values. No lifecycle,
TTL, pin, control-table or image changes were made; **chaostest was not torn
down**. Completed load Jobs retain their normal TTL; the runners removed their
ConfigMaps. The general 35-core / 43-pod HA quota was **not** applied here.

Evidence remains ignored under `tests/load/k6/results/`:
`chaostest-{doc48,auth48}-{monitor.json,supplement.json,raw.json,before.txt,
after.txt,start.txt,end.txt}`, the two `.log` files, per-run JSON/Markdown
summaries and the two Job tarballs. Supplemental captures include HPA/current
and desired replicas, Pending/available pods, cluster/node metrics and the
RDS CloudWatch datapoints.

### Cleanup

After collecting the last Job's artifacts, `scripts/teardown-tenant.sh loadbench`
deleted the namespace and reported `database otterworks_loadbench dropped.`
It completed legacy IRSA trust cleanup; `ctl_delete_tenant loadbench` then
removed the control record/lock. A subsequent namespace read returned no object,
and `ctl_tenant_exists loadbench` returned false. No pin had been set, so none
needed removal. No load-generator or tenant compute was left running.
The teardown script does not itself purge shared S3/DynamoDB content; residual
shared-store test data was not audited. Follow the platform lifecycle runbook
for any required shared-store retention cleanup rather than broad table/bucket deletion.
