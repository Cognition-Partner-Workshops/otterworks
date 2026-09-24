# Phase 2 — Beyond the Upgrade

## What Was Built

### A. Datadog Observability

**A1. DogStatsD Metrics Export**
- Added `micrometer-registry-statsd` with Datadog flavor.
- Host/port configurable via `DD_AGENT_HOST` (default `localhost`) and `DD_DOGSTATSD_PORT` (default `8125`).
- Enabled by `management.statsd.metrics.export.enabled` (default `true`, `false` in test profile).
- Common tags on every metric: `service`, `env`, `version` (from `DD_SERVICE`/`DD_ENV`/`DD_VERSION`).
- Prometheus registry preserved alongside StatsD.

**A2. Business Metrics**
- Counter `reports.generated` with tags `report_type`, `format`, `outcome` (success/failure).
- Timer `reports.generation.duration` with tags `report_type`, `format`.
- Gauge `reports.queue.depth` tracking active + queued tasks in the executor.
- Cache hit/miss metrics via `CaffeineCacheMetrics` on `reportDataCache`.

**A3. APM**
- Dockerfile downloads `dd-java-agent.jar` (v1.37.1) in a separate build stage.
- ENTRYPOINT uses `-javaagent:/app/dd-java-agent.jar`.
- Honors `DD_SERVICE`, `DD_ENV`, `DD_VERSION`, `DD_AGENT_HOST`, `DD_TRACE_AGENT_PORT`, `DD_LOGS_INJECTION=true`.
- App starts normally when no agent is reachable.

**A4. Structured Logs**
- `logback-spring.xml` with `LogstashEncoder` for JSON output (non-local profiles).
- MDC keys `dd.trace_id` / `dd.span_id` included when present.
- Human-readable pattern preserved under the `local` profile.

**A5. Docker Compose**
- `docker-compose.datadog.yml` with `datadog/agent:7` (DogStatsD UDP 8125, APM 8126).
- `DD_API_KEY` from environment (never committed).
- Report-service container wired to the agent.

**A6. Monitors-as-Code**
- `observability/datadog/monitors.json`: 3 monitors (failure rate, p95 latency, queue depth).
- `observability/datadog/dashboard.json`: dashboard with reports generated, duration, queue depth, cache hit/miss.
- `DatadogConfigValidationTest` validates both files parse correctly and reference known metric names.

### B. Scheduled (Recurring) Reports

**B1. Entity**
- `ReportSchedule` JPA entity with id, name, cron expression, time zone, template (JSON), requestedBy, enabled, createdAt, lastRunAt, nextRunAt, version (optimistic locking).

**B2. Endpoints** (`/api/v1/reports/schedules`)
- `POST` (201; 400 on invalid cron / missing fields)
- `GET` list
- `GET /{id}` (404 when absent)
- `DELETE /{id}` (204 / 404)
- Jakarta validation, springdoc annotations, RFC 7807 problem details on errors.

**B3. Scheduler Poller**
- `ReportSchedulePoller` with `@Scheduled(fixedDelayString)` polling every `otterworks.report.schedule.poll-interval` (default 60s).
- Creates reports via existing `ReportService.createReport`.
- Advances `nextRunAt` using Spring's `CronExpression`.
- Safe for multi-instance: `@Version` optimistic locking on `ReportSchedule`; `ObjectOptimisticLockingFailureException` caught and logged.

**B4. Tests**
- `ReportScheduleControllerTest`: happy path (201), invalid cron (400), missing fields (400), 404 on get/delete, full CRUD lifecycle.
- `ReportSchedulePollerTest`: verifies poller creates report and advances `nextRunAt`.

### C. Performance Engineering

**C1. Caffeine Cache**
- Replaced Guava `LoadingCache` with Caffeine `Cache` in `ReportDataFetcher`.
- `recordStats()` enabled, bound to Micrometer via `CaffeineCacheMetrics`.
- User-activity fetches now cached too.
- `ReportDataFetcherCacheTest` proves second identical fetch does not call `RestTemplate`.

**C2. Bounded Executor**
- Named `ThreadPoolTaskExecutor` bean (`reportGenerationExecutor`).
- Core/max/queue from properties, `CallerRunsPolicy`, thread prefix `report-gen-`.
- Executor metrics registered via `ExecutorServiceMetrics.monitor()`.

**C3. Parallel Fetch + Streaming Download**
- COMPLIANCE category fetches analytics and audit data in parallel via `CompletableFuture.supplyAsync`.
- Download endpoint uses `InputStreamResource` instead of `ByteArrayResource`.

**C4. Local Profile + Performance Measurement**
- `application-local.properties`: H2 in-memory, StatsD enabled.
- `docs/PERF.md` with before/after measurement description.
- `scripts/perf-test.sh` for reproducible benchmarking.

## Design Decisions

1. **Caffeine over Spring @Cacheable**: Direct Caffeine API gives us `recordStats()` and cache-level metrics without configuring a CacheManager. The existing code used LoadingCache directly so this was a minimal change.

2. **Optimistic locking for schedule safety**: `@Version` on `ReportSchedule` is simpler than pessimistic locking or conditional UPDATE and works well for the expected low-contention scenario.

3. **Record DTOs for schedules**: Used Java records for new `ReportScheduleRequest`/`ReportScheduleResponse` since we're on Java 21. Existing DTOs left as classes to avoid unnecessary churn.

4. **Separate build stage for dd-java-agent**: Avoids adding curl to the runtime image and keeps the agent version pinned.

## Intentionally Not Done

- **WebClient migration**: RestTemplate works and the spec didn't require it. Would be a separate effort.
- **Full pagination on schedule list**: Not needed for current scale; can be added later.
- **Datadog API key rotation / secrets management**: Out of scope; the compose file reads from environment.

## Runtime Acceptance

### Boot with local profile
```bash
SPRING_PROFILES_ACTIVE=local /usr/lib/jvm/java-21-openjdk-amd64/bin/java -jar target/report-service.jar
```
Output confirms successful startup:
```
Started ReportApplication in 5.445 seconds (process running for 5.852)
```
The `local` profile activates H2 in-memory and human-readable log format.

### Health check
```bash
$ curl -s http://localhost:8091/actuator/health
{"status":"UP"}
```

### DogStatsD verification
```bash
# Terminal 1: listen for UDP on 8125
timeout 15 nc -lu 8125

# Terminal 2: create a report
curl -s -X POST http://localhost:8091/api/v1/reports \
  -H "Content-Type: application/json" \
  -d '{"reportName":"DogStatsD Test","category":"USAGE_ANALYTICS","reportType":"CSV","requestedBy":"acceptance-test"}'
```

Captured DogStatsD UDP lines (excerpt):
```
reports.generated:1|c|#statistic:count,env:local,format:CSV,outcome:success,report_type:USAGE_ANALYTICS,service:report-service,version:0.1.0
reports.generation.duration:209.151372|ms|#env:local,format:USAGE_ANALYTICS,report_type:CSV,service:report-service,version:0.1.0
reports.queue.depth:0|g|#statistic:value,env:local,service:report-service,version:0.1.0
cache.gets:1|c|#statistic:count,cache:reportDataCache,env:local,result:miss,service:report-service,version:0.1.0
cache.puts:1|c|#statistic:count,cache:reportDataCache,env:local,service:report-service,version:0.1.0
executor.completed:0|c|#statistic:count,env:local,name:reportGenerationExecutor,service:report-service,version:0.1.0
```

All business metrics (`reports.generated`, `reports.generation.duration`, `reports.queue.depth`, cache metrics) are present with correct tags.
