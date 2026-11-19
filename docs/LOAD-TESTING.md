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
