# Phase 2 — observability, scheduled reports, performance

Branch `eval/devin-report-service-phase2`, built on `b9ca8a5` (Java 21 / Spring Boot 3.5.0 tree).
Verification: `mvn -B clean verify` → **83 tests, 0 failures, 0 errors, 1 skipped** (the 50 original
tests incl. the pre-existing skip in `DependencyTranscriptEmitterTest`, plus 33 new).

## A. Datadog observability

| Item | What was built |
|------|----------------|
| A1 Metrics export | `micrometer-registry-statsd`, flavor `datadog`. `management.statsd.metrics.export.{host,port}` come from `DD_AGENT_HOST`/`DD_DOGSTATSD_PORT` (defaults `localhost`/`8125`); `enabled` is `${DD_METRICS_ENABLED:true}` and forced to `false` in `application-test.properties`. Common tags `service`/`env`/`version` from `DD_SERVICE`/`DD_ENV`/`DD_VERSION` (defaults `report-service`/`local`/`0.1.0`) via `management.metrics.tags.*`, so they apply to the Prometheus registry too, which is unchanged. Step is 10 s. |
| A2 Business metrics | `ReportMetrics`: counter `reports.generated{report_type,format,outcome}`, timer `reports.generation.duration{report_type,format}` (percentile histogram on), gauge `reports.queue.depth` = `count(PENDING) + count(GENERATING)` from the repository. `report_type` is the report **category** (usage_analytics, compliance, …) and `format` the output type (pdf/csv/excel) — the spec names both "type", this split keeps them distinguishable. Cache metrics come from `CaffeineCacheMetrics` (`cache.gets{cache=report-data,result=hit|miss}`, `cache.size`, `cache.evictions`, …). |
| A3 APM | Dockerfile builder stage downloads `com.datadoghq:dd-java-agent:1.44.0` with `mvn dependency:copy` (same mirror/proxy rules as the build; version pinned via `ARG`), runtime stage copies it to `/app/dd-java-agent.jar` and the entrypoint is `java -javaagent:/app/dd-java-agent.jar -jar app.jar`. `DD_SERVICE/ENV/VERSION/AGENT_HOST/TRACE_AGENT_PORT/LOGS_INJECTION` are `ENV` defaults, overridable at run time. The tracer buffers and warns when no agent answers; the app starts regardless. |
| A4 Structured logs | `logback-spring.xml`: `LogstashEncoder` for every profile except `local`, which keeps a human-readable pattern (with `trace=/span=` from MDC so the local pattern shows correlation too). JSON output includes MDC `dd.trace_id`, `dd.span_id`, `dd.service/env/version` (injected by the tracer when `DD_LOGS_INJECTION=true`) plus our own `reportId`/`scheduleId`. The old `logging.pattern.console` property was removed since Logback config owns the format now. |
| A5 Compose | `docker-compose.datadog.yml`: `datadog/agent:7`, `DD_API_KEY: ${DD_API_KEY:?…}` (compose fails fast if unset; nothing committed), DogStatsD 8125/udp with `DD_DOGSTATSD_NON_LOCAL_TRAFFIC`, APM 8126 with `DD_APM_NON_LOCAL_TRAFFIC`, and `report-service` built from the Dockerfile with `DD_AGENT_HOST=datadog-agent` and unified-service-tagging labels. |
| A6 Monitors as code | `observability/datadog/monitors.json` (4 monitors: failure rate, p95 generation latency, queue depth, no reports generated for 1 h) and `dashboard.json` (ordered layout, 3 groups: throughput/outcome, latency/backlog, cache). `DatadogAssetsTest` parses both, checks the shapes the Datadog API requires (`type`, `query`, `message`, `options.thresholds.critical`; `layout_type`, `widgets[].definition.type/requests`) and extracts every `agg:metric.name{` reference; each must be either a constant on `ReportMetrics` or a meter present in the live `MeterRegistry` after startup (so the Caffeine/executor binder names are verified against what Micrometer really registers, not a hard-coded list). |

## B. Scheduled reports

* **Entity** `ReportSchedule` (`report_schedules`): id, name, cronExpression, timeZone, `template`
  (`@Lob` JSON of a `ReportRequest`), requestedBy, enabled, createdAt, lastRunAt, nextRunAt, and a
  `@Version` column. `requestedBy` is copied from the template's `requestedBy` — the schedule owner is
  whoever the generated reports are for.
* **API** `/api/v1/reports/schedules` — `POST` 201 + `Location`; `GET` list; `GET /{id}`; `DELETE /{id}`
  204. DTOs are records (`ReportScheduleRequest`, `ReportScheduleResponse`), validated with Jakarta
  (`@NotBlank`, `@Size`, `@Valid` on the nested template), documented with springdoc. Errors are RFC 7807
  `ProblemDetail`s from `ApiExceptionHandler` (extends `ResponseEntityExceptionHandler`, so
  `MethodArgumentNotValidException` → the standard 400 problem detail; `InvalidScheduleException`
  → 400; `ScheduleNotFoundException` → 404). This advice only covers the new exceptions; the existing
  `ReportController` behaviour is untouched.
* **Cron** — Spring `CronExpression.parse` (6 fields, macros allowed); the next fire time is computed
  in the schedule's zone (`ZoneId`) and stored as UTC `Instant`. Unknown zones are 400.
* **Scheduler** `ReportSchedulePoller` — `@Scheduled(fixedDelayString =
  "${otterworks.report.schedule.poll-interval:60s}")` (initial delay 10 s, `1h` in tests so it never
  interferes). For every enabled schedule with `nextRunAt <= now` it runs a **conditional UPDATE**
  (`claimRun`: `SET nextRunAt = :next, lastRunAt = :now, version = version + 1 WHERE id = :id AND
  version = :expected AND nextRunAt = :expectedNext AND enabled = true`). Only the instance whose update
  hits 1 row calls `ReportService.createReport`; the other instance sees 0 rows and skips. The claim is
  committed *before* the report is created, so a template that always fails cannot re-fire every poll
  (at-most-once per slot; the failure is visible in the report's `FAILED` status and metrics). The
  next run is computed from *now*, not from the missed slot, so an outage yields one catch-up run rather
  than a burst. A cron with no future occurrence is parked 100 years out (`Instant.MAX` does not fit a
  SQL timestamp).
* **Tests** — `ReportScheduleControllerIntegrationTest` (201 with Location and computed `nextRunAt`,
  400 for bad cron / bad zone / missing fields as problem details, 404, 204 then 404),
  `ReportSchedulePollerTest` (due schedule → report created & `nextRunAt` advanced; disabled/future
  schedules ignored; two "instances" holding the same stale row → exactly one claim, one report),
  `ReportScheduleServiceTest` (cron accept/reject matrix, zone handling, next-run in Tokyo vs UTC).

## C. Performance

See `docs/PERF.md` for method and numbers. Summary of the decisions:

* Caffeine cache in `ReportDataFetcher` with `recordStats()`, one `Cache<String, List<…>>` for analytics,
  audit **and** user activity; `CaffeineCacheMetrics.monitor(registry, cache, "report-data")`. Upstream
  failures fall back to sample data and are **not** cached (same intent as before). Side effect: at
  `b9ca8a5` the Guava fallback never fired — `LoadingCache.get` wraps `RestClientException` in
  `UncheckedExecutionException`, which the `catch (ExecutionException)` didn't match, so reports failed
  whenever an upstream was down. That is fixed by construction now (`ReportDataFetcherCacheTest`
  covers it).
* `AsyncConfig`: `reportGenerationExecutor` (`ThreadPoolTaskExecutor`, `report-gen-`, core 4 / max 8 /
  queue 100 from `otterworks.report.executor.*`, `CallerRunsPolicy`, `ExecutorServiceMetrics` as
  `executor.*{name=report-gen}`) used via `@Async(REPORT_GENERATION_EXECUTOR)`; a separate bounded
  `reportFetchExecutor` (`otterworks.report.fetch.parallelism`, default 16) for source fan-out.
* `COMPLIANCE` now fetches analytics + audit concurrently (`fetchAnalyticsAndAuditData`) and returns the
  union of columns with a `source` column. At `b9ca8a5` `COMPLIANCE` shared the `AUDIT_LOG` branch and
  fetched audit only; "report types that need both" was read as compliance, which is the only category
  whose name implies both.
* Download returns a `FileSystemResource` with `Content-Length` — no `byte[]` of the file.
* `local` profile: H2 in-memory, `create-drop`, upstream URLs default to `http://localhost:1` (refused
  instantly → sample data), output dir `/tmp/reports`. Boots with no external services.

## D. Acceptance (as run)

* `mvn -B clean verify` → BUILD SUCCESS, 83 tests / 0 failures / 0 errors / 1 skipped.
* `SPRING_PROFILES_ACTIVE=local java -jar target/report-service.jar`; `curl -s localhost:8091/actuator/health`
  → `{"status":"UP"}`; `POST /api/v1/reports` (USAGE_ANALYTICS/CSV) → 200, id 1, later `COMPLETED`;
  a Python UDP socket bound to 0.0.0.0:8125 received, within the 10 s step:
  `reports.generated:1|c|#statistic:count,env:local,format:csv,outcome:success,report_type:usage_analytics,service:report-service,version:0.1.0`.

## Deviations, and things intentionally not done

* **JDK path.** `/usr/lib/jvm/java-21-openjdk-amd64` does not exist on the build machine; the only JDK 21
  is SDKMAN's Temurin `21.0.7-tem` at `~/.sdkman/candidates/java/current`, which is what `JAVA_HOME`
  pointed to for every build. Maven Central returned 403, so the GCS mirror from the brief was configured
  in `~/.m2/settings.xml` (not committed — it is a machine setting, not a project one).
* **Docker image not built.** `docker build` on the build machine failed pulling the base image
  (`docker.io/library/maven:3.9.9-eclipse-temurin-21` → `429 Too Many Requests` from Docker Hub), so the
  Dockerfile and compose file were reviewed but not executed. The `dd-java-agent` coordinates/version
  resolve on Maven Central. The compose stack needs a real `DD_API_KEY`, which this environment does not
  have by design.
* **Datadog payloads not pushed to Datadog.** Monitors/dashboard follow the public API shapes
  (`type/query/message/options.thresholds`, `layout_type/widgets/definition`), and the test enforces
  those shapes and metric names, but nothing was validated against a live Datadog account (no API key
  in this environment, by design).
* **No `PUT`/`PATCH` for schedules** — the brief asks for POST/GET/GET-by-id/DELETE only. Enabling or
  editing is delete + re-create for now.
* **Poller runs on Spring's default single-threaded scheduler** and creates reports sequentially; each
  create is a fast insert and generation is async, so no pool was added.
* **Schedule template is stored as opaque JSON** (`@Lob`), not columns, per the brief ("serialized as
  JSON"); it is deserialized on read and validated again on create so the API never returns a template it
  cannot use.
* **Streaming download not covered by the perf script**, which measures POST-to-COMPLETED. The change is
  structural (see PERF.md).
* **Guava removed from the POM** — the cache was its only user in this tree.
