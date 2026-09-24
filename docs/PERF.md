# Report-service performance notes (Phase 2, section C)

## What changed

| # | Change | Where |
|---|--------|-------|
| C1 | Guava `LoadingCache` → Caffeine (`recordStats()`, bound to Micrometer as cache `report-data`); user-activity fetches are now cached too | `ReportDataFetcher` |
| C2 | `@Async` generation runs on a named, bounded `ThreadPoolTaskExecutor` (`report-gen-*`, core/max/queue from `otterworks.report.executor.*`, `CallerRunsPolicy`, executor metrics) instead of Spring's default unbounded `SimpleAsyncTaskExecutor` | `AsyncConfig`, `ReportGenerationWorker` |
| C3 | `COMPLIANCE` reports fetch analytics **and** audit concurrently on a bounded fetch pool (`otterworks.report.fetch.parallelism`); `GET /{id}/download` streams a `FileSystemResource` instead of reading the whole file into a `byte[]` | `ReportDataFetcher#fetchAnalyticsAndAuditData`, `ReportController` |
| C4 | `local` profile (H2 in-memory, no upstreams) + this measurement | `application-local.properties`, `scripts/` |

## How it was measured

Everything below was produced with the two scripts committed under `scripts/`:

* `scripts/fake-upstreams.py 9099 200 200` — a threaded HTTP stub for the analytics / audit / auth
  services. Every request sleeps **200 ms** (simulated upstream latency) and returns 200 rows.
  Without it the app falls back to synthetic sample data and there is nothing to cache/parallelise.
* `scripts/perf-report-latency.sh <requests> <concurrency> <category> <type>` — fires `POST
  /api/v1/reports`, then polls `GET /api/v1/reports/{id}` every 50 ms until `COMPLETED`/`FAILED`.
  Latency = wall-clock from just before the POST to the first poll that sees a terminal status
  (`date +%s%N`, ms resolution). Percentiles are nearest-rank over the 50 samples.
  * `UNIQUE_RANGE=1` gives every request a distinct `dateFrom`, so the data cache never hits
    ("cold" — measures upstream fetch + render).
  * default (`UNIQUE_RANGE=0`) uses the same date range for every request ("warm" — the cache is
    populated by 5 discarded warm-up requests first).

Both builds ran on the same machine, same JVM (Temurin 21.0.7), fresh JVM for every cold run
(the cache holds max 100 entries, so a second cold run against the same JVM would be partially warm):

```bash
# upstream stub, once
python3 scripts/fake-upstreams.py 9099 200 200 &

# BEFORE = commit b9ca8a5 (branch start). It has no local profile and H2 is test-scoped, so H2 was
# added to the classpath via PropertiesLauncher and the datasource overridden through the environment:
SPRING_DATASOURCE_URL='jdbc:h2:mem:reportsdb;DB_CLOSE_DELAY=-1' SPRING_DATASOURCE_USERNAME=sa \
SPRING_DATASOURCE_PASSWORD= SPRING_DATASOURCE_DRIVER_CLASS_NAME=org.h2.Driver \
SPRING_JPA_HIBERNATE_DDL_AUTO=create-drop SPRING_JPA_PROPERTIES_HIBERNATE_DIALECT=org.hibernate.dialect.H2Dialect \
ANALYTICS_SERVICE_URL=http://localhost:9099 AUDIT_SERVICE_URL=http://localhost:9099 AUTH_SERVICE_URL=http://localhost:9099 \
java -cp target/report-service.jar -Dloader.path=$HOME/.m2/repository/com/h2database/h2/2.3.232/h2-2.3.232.jar \
     org.springframework.boot.loader.launch.PropertiesLauncher

# AFTER = this branch
SPRING_PROFILES_ACTIVE=local ANALYTICS_SERVICE_URL=http://localhost:9099 AUDIT_SERVICE_URL=http://localhost:9099 \
AUTH_SERVICE_URL=http://localhost:9099 java -jar target/report-service.jar

# runs (50 requests each)
UNIQUE_RANGE=1 scripts/perf-report-latency.sh 50 1 COMPLIANCE CSV
UNIQUE_RANGE=1 scripts/perf-report-latency.sh 50 5 COMPLIANCE CSV
UNIQUE_RANGE=1 scripts/perf-report-latency.sh 50 5 USER_ACTIVITY CSV
scripts/perf-report-latency.sh 5 5 USAGE_ANALYTICS CSV >/dev/null   # warm-up
scripts/perf-report-latency.sh 50 5 USAGE_ANALYTICS CSV
scripts/perf-report-latency.sh 50 5 USER_ACTIVITY CSV
scripts/perf-report-latency.sh 50 5 COMPLIANCE PDF
```

## Results (ms, 50 requests each)

### C1 — user-activity cache (the one fetch that was never cached before)

| Scenario | before p50 | before p95 | after p50 | after p95 |
|----------|-----------:|-----------:|----------:|----------:|
| `USER_ACTIVITY` CSV, warm cache, concurrency 5 | 235 | 305 | **37** | 262 * |
| `USER_ACTIVITY` CSV, cold cache, concurrency 5 | 238 | 619 | 244 | 612 |
| `USAGE_ANALYTICS` CSV, warm (already cached before) | 38 | 45 | 41 | 50 |

Before, every user-activity report paid the full upstream round-trip (p50 ≈ upstream latency). After,
only the first request per date range does; the rest are served from Caffeine. Cold numbers are
unchanged, as expected — the cache cannot help a miss.

\* The after-p95 is the 5 requests that arrive while the single miss is still in flight (Caffeine
`Cache.get`/`put` here is not a loading cache, so concurrent misses on the same key each fetch once).

### C3 — analytics + audit in parallel for `COMPLIANCE`

At `b9ca8a5` a `COMPLIANCE` report fetched **only the audit source** (`case AUDIT_LOG: case
COMPLIANCE:` fell through), so a before/after against the old commit compares different work. The
isolating measurement is therefore the same phase-2 jar with the fetch pool sized 1 (both fetches
end up serial) vs the default:

| `COMPLIANCE` CSV, cold cache | serial (`REPORT_FETCH_PARALLELISM=1`) p50 / p95 | parallel (default 16) p50 / p95 |
|------------------------------|-----------------:|------------------:|
| concurrency 1 | 437 / 453 | **235 / 246** |
| concurrency 5 | 1992 / 2053 | **242 / 635** |

Two 200 ms sources now cost one round-trip. For reference, the old single-source `COMPLIANCE` at
`b9ca8a5` measured 236 / 245 (c=1) and 241 / 582 (c=5) — i.e. the report now contains both data sets
at the same latency as before.

The fetch pool default was raised from 4 to 16 during this measurement: with 4 threads and 5
concurrent compliance reports (10 fetch tasks) the pool itself queued (p50 475 ms). Rule of thumb
kept in `application.properties`: `fetch.parallelism ≥ 2 × executor.max-size`.

### C2 — bounded executor (behavioural, not a latency change)

Not a latency optimisation; measured for regressions only. `USAGE_ANALYTICS` warm p50 38 → 41 ms,
`COMPLIANCE` PDF warm p50 52 → 108 ms. The PDF delta is the report now rendering both sources
(400 rows, union of columns) instead of 200 — not the executor. What C2 buys is a hard bound
(`core 4 / max 8 / queue 100`, then `CallerRunsPolicy`) instead of one new thread per POST, and
`executor.*{name=report-gen}` metrics to see it.

### C3 — streaming download

Not measured with this script (it does not download). The change is structural: `FileUtils.
readFileToByteArray` → `FileSystemResource` with `Content-Length`, so heap usage per download is a
buffer, not the file.

## Caveats

* Single machine, stub upstreams with a fixed 200 ms sleep, H2 in-memory — the absolute numbers say
  nothing about production; the *ratios* (cache hit vs miss, serial vs parallel) are what matter.
* Percentiles over 50 samples are coarse; p95 is effectively the 48th-slowest sample.
* Poll interval 50 ms bounds resolution of the fast (~35 ms) cases.
