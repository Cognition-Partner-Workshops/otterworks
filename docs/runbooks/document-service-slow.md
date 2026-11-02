# Runbook: Document Service Slow Queries

**Severity:** High

## Alert

`DocumentServiceHighLatency` -- fires when document-service P95 latency exceeds 3s over a 1-minute window
(`observability/grafana/provisioning/alerting/alert-rules.yml`, uid `document-service-high-latency`).

> **Check the alert name first.** If the page says `DatasourceError` or `DatasourceNoData`, Grafana could
> not evaluate the rule (Prometheus unreachable, scrape gap). The labels and annotations are copied from
> the rule, so the text still reads "P95 latency spike" even though no latency was measured. Fix the
> datasource / scrape, do not treat it as a document-service incident. admin-service's alert ingest
> (`AlertsController::DATASOURCE_ALERT_NAMES`) skips these instead of opening an incident.

## Symptoms

- Document CRUD operations take 3-5 seconds instead of the usual sub-second response times.
- The Incident Overview dashboard shows elevated P95 latency on the document-service panel.
- Upstream timeouts may cascade to the web app, causing loading spinners or error messages.

## Investigation Steps

1. Confirm the latency is real and where it is spent. One request already shows the split between
   wall time and database work:
   ```bash
   curl -s -D - -o /dev/null -H 'X-User-ID: <uuid>' 'http://localhost:8083/api/v1/documents/?page=1&size=20' \
     | grep -iE 'x-request-duration-ms|x-db-queries'
   ```
   `X-Request-Duration-Ms` in the thousands with `X-DB-Queries` in the single digits means the time is
   **not** in SQL.
2. Check whether the chaos flag `chaos:document-service:slow_queries` is set in Redis:
   ```bash
   redis-cli PTTL chaos:document-service:slow_queries     # -2 absent, otherwise ms until it expires
   # on the cluster: kubectl -n otterworks-<tenant> exec deploy/redis -- redis-cli PTTL chaos:document-service:slow_queries
   ```
   The same answer is in Prometheus without a Redis shell:
   `otterworks_chaos_flag_active{flag="chaos:document-service:slow_queries"} == 1`, and the service logs
   `chaos_flag_active` once when the flag turns on and `chaos_latency_injected` (with `delay_seconds`) on
   every request it slows down. The flag is written by `POST /api/v1/admin/chaos` (admin-service,
   10 min TTL), `scripts/inject-bug.sh <tenant> document-slow` (1 h TTL) or the incident harness.
   A key written without an expiry is ignored and logged as `chaos_flag_without_expiry_ignored`.
3. If the flag is **not** set, look at the database:
   - Jaeger: Service `document-service` → Min Duration `3s`; expand the `SELECT` spans. Many short
     spans per request is query fan-out (see `DocumentListQueryFanout` and the n-plus-one scenario in
     `.agents/skills/incident-responder/SKILL.md`); a few long spans is a slow query or lock wait.
   - Pool pressure: `otterworks_db_query_duration_seconds` (per-statement wall time) versus
     `http_request_duration_seconds`. Statements fast but requests slow with
     `http_requests_inprogress` pinned at `db_pool_size + db_max_overflow` (10 + 20 by default,
     `DOC_SVC_DB_POOL_SIZE` / `DOC_SVC_DB_MAX_OVERFLOW`) is pool exhaustion.
   - Postgres: `SELECT pid, state, wait_event_type, now() - query_start AS age, left(query, 80) FROM pg_stat_activity WHERE datname = current_database() AND state <> 'idle' ORDER BY age DESC;`

## Resolution Steps

1. Chaos flag set → clear it. Latency drops within the 2 s in-process flag cache; no restart needed.
   ```bash
   redis-cli DEL chaos:document-service:slow_queries
   # or every chaos flag at once:
   scripts/inject-bug.sh <tenant> reset                    # cluster tenant
   curl -X DELETE -H "X-Chaos-Secret: $CHAOS_SECRET" http://admin-service:8089/api/v1/admin/chaos   # admin API
   ```
   Then confirm: `otterworks_chaos_flag_active{...} == 0`, `X-Request-Duration-Ms` back to tens of ms.
2. Query fan-out → follow the n-plus-one fix shape in the incident-responder skill (batched query,
   indexes, test pinning the query count).
3. Pool exhaustion → find the holder (long transaction, missing `await session.close()`, upstream
   retry storm) before raising `DOC_SVC_DB_POOL_SIZE`; a larger pool only moves the queue to Postgres.
4. Verify the alert clears in Grafana / Alertmanager and that the incident in the admin dashboard is
   resolved (Grafana's `resolved` notification does this automatically for real alerts).

## Post-Incident

- Record who set the flag and why (admin-service logs `CHAOS TRIGGERED`, `inject-bug.sh` output).
  Chaos flags belong on `workshop-<id>` / `demo-<id>` tenants, never on `t-main` or any tenant
  holding real data (`AGENTS.md`).
- If the page was a `DatasourceError`, the action item is the Prometheus datasource or scrape target,
  not document-service.
- Attach the before/after `X-Request-Duration-Ms` and the `otterworks_chaos_flag_active` panel to the
  incident.
